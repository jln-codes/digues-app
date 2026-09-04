import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from digues_app.migration.crs import (
    CRSInfo,
    CRSResolutionError,
    crs_hint_is_consistent,
    geometry_sql,
    parse_srid,
    resolve_source_crs,
    validate_crs,
)
from digues_app.migration.anomalies import collect_anomalies
from digues_app.migration.coverage import diagnose_documents
from digues_app.source import CouchDBDatabaseInfo


def metadata(epsg_code=None, *, wkt=None, proj4=None, found=True):
    return CouchDBDatabaseInfo(
        source_database="test",
        epsg_code=epsg_code,
        crs_wkt=wkt,
        proj4=proj4,
        document_found=found,
    )


class CRSResolutionTest(unittest.TestCase):
    def resolve_without_environment(self, info, fallback=None):
        with patch.dict(os.environ, {}, clear=True):
            return resolve_source_crs(info, fallback=fallback)

    def test_parses_numeric_and_epsg_formats(self):
        self.assertEqual(parse_srid(3950), 3950)
        self.assertEqual(parse_srid("3950"), 3950)
        self.assertEqual(parse_srid("EPSG:3950"), 3950)

    def test_sirs_epsg_code_is_authoritative(self):
        info = self.resolve_without_environment(metadata("EPSG:3950"))
        self.assertEqual(info.source_srid, 3950)
        self.assertEqual(info.source, "$sirs")
        self.assertFalse(info.transformation_required)

    def test_absent_metadata_uses_explicit_fallback(self):
        info = self.resolve_without_environment(metadata(found=False), fallback="3950")
        self.assertEqual(info.source_srid, 3950)
        self.assertEqual(info.source, "SIRS_SOURCE_SRID")
        self.assertTrue(info.warnings)

    def test_absent_metadata_without_fallback_is_blocking(self):
        with self.assertRaisesRegex(CRSResolutionError, "absent") as raised:
            self.resolve_without_environment(metadata(found=False))
        self.assertEqual(raised.exception.category, "MISSING_SOURCE_CRS")

    def test_invalid_metadata_can_use_non_conflicting_fallback(self):
        info = self.resolve_without_environment(metadata("not-an-epsg"), fallback=2154)
        self.assertEqual(info.source_srid, 2154)
        self.assertIn("invalide", info.warnings[0])

    def test_metadata_and_fallback_conflict_is_blocking(self):
        with self.assertRaises(CRSResolutionError) as raised:
            self.resolve_without_environment(metadata(3950), fallback=2154)
        self.assertEqual(raised.exception.category, "CONFLICTING_SOURCE_CRS")

    def test_wkt_authority_conflict_is_blocking(self):
        with self.assertRaises(CRSResolutionError):
            self.resolve_without_environment(
                metadata(3950, wkt='PROJCS["x",AUTHORITY["EPSG","2154"]]')
            )

    def test_same_srid_does_not_transform(self):
        self.assertEqual(
            geometry_sql(CRSInfo(source_srid=3950)),
            "ST_GeomFromText(%s, 3950)",
        )

    def test_different_srid_reprojects(self):
        expression = geometry_sql(CRSInfo(source_srid=2154))
        self.assertEqual(
            expression,
            "ST_Transform(ST_GeomFromText(%s, 2154), 3950)",
        )

    def test_crs_name_is_only_a_consistency_hint(self):
        info = CRSInfo(
            source_srid=3950,
            crs_wkt='PROJCS["RGF93 / CC50",AUTHORITY["EPSG","3950"]]',
        )
        self.assertTrue(crs_hint_is_consistent(None, info))
        self.assertTrue(crs_hint_is_consistent("EPSG:RGF93 / CC50", info))
        self.assertFalse(crs_hint_is_consistent("EPSG:4326", info))

    def test_postgis_resolution_is_required_for_source_and_target(self):
        class Cursor:
            def __init__(self):
                self.srid = None

            def execute(self, _query, params):
                self.srid = params[0]

            def fetchone(self):
                return (self.srid,) if self.srid == 3950 else None

        with self.assertRaisesRegex(CRSResolutionError, "absent de spatial_ref_sys"):
            validate_crs(Cursor(), CRSInfo(source_srid=999999))

    def test_only_contradictory_crs_name_creates_anomaly(self):
        info = CRSInfo(
            source_srid=3950,
            crs_wkt='PROJCS["RGF93 / CC50",AUTHORITY["EPSG","3950"]]',
        )
        documents = [
            {"@class": "x.ArbreVegetation", "_id": "a"},
            {
                "@class": "x.ArbreVegetation",
                "_id": "b",
                "crsName": "EPSG:RGF93 / CC50",
            },
            {
                "@class": "x.ArbreVegetation",
                "_id": "c",
                "crsName": "EPSG:4326",
            },
        ]
        anomalies = collect_anomalies(
            documents,
            source_database="test",
            coverage_rows=(),
            crs_info=info,
        )
        conflicts = [
            anomaly
            for anomaly in anomalies
            if anomaly.category == "OBJECT_CRS_HINT_CONFLICT"
        ]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].source_document_id, "c")
        self.assertIsNone(conflicts[0].source_object_id)

    def test_diagnostic_writes_compact_crs_section(self):
        documents = [
            {
                "_id": "$sirs",
                "epsgCode": "EPSG:3950",
                "crsWkt": 'PROJCS["RGF93 / CC50",AUTHORITY["EPSG","3950"]]',
                "proj4": "+proj=lcc",
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bilan.md"
            result = diagnose_documents(
                documents,
                output_path=path,
                source_database="test",
            )
            report = path.read_text(encoding="utf-8")
        self.assertEqual(result.crs_info.source_srid, 3950)
        self.assertIn("## H. CRS", report)
        self.assertIn("CRS source détecté : `EPSG:3950`", report)
        self.assertIn("Transformation nécessaire : non", report)

    @patch("digues_app.migration.coverage.validate_crs_with_postgis")
    def test_diagnostic_registers_unresolvable_postgis_srid(self, validate):
        validate.side_effect = CRSResolutionError(
            "CRS source EPSG:999999 absent de spatial_ref_sys",
            category="INVALID_SOURCE_CRS",
        )
        documents = [{"_id": "$sirs", "epsgCode": "EPSG:999999"}]
        with tempfile.TemporaryDirectory() as directory:
            result = diagnose_documents(
                documents,
                output_path=Path(directory) / "bilan.md",
                source_database="test",
                validate_postgis=True,
            )
        active = result.anomaly_register.active
        self.assertTrue(
            any(anomaly.category == "INVALID_SOURCE_CRS" for anomaly in active)
        )


if __name__ == "__main__":
    unittest.main()
