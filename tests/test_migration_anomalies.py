import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

from sirs_postgre.cli import main
from sirs_postgre.migration.anomalies import (
    ACTIONABLE_CATEGORIES,
    Anomaly,
    FAMILY_BY_CATEGORY,
    collect_anomalies,
    load_anomalies,
    is_actionable,
    make_anomaly_id,
    merge_previous_status,
    resolve_anomaly,
    update_anomaly_register,
    write_anomalies_csv,
    write_anomalies_json,
)
from sirs_postgre.migration.vegetation import MANUAL_REVIEW


DATABASE = "test_source"


def coverage_row(class_name, status, *, known=True, unanalysed=()):
    return {
        "class": class_name,
        "total": 1,
        "status": status,
        "destination": None,
        "comment": "test",
        "known": known,
        "unanalysed": tuple(unanalysed),
    }


def source_doc(class_name, source_id, **values):
    return {
        "_id": source_id,
        "@class": f"fr.sirs.core.model.{class_name}",
        **values,
    }


class AnomalyIdentityAndHistoryTest(unittest.TestCase):
    def test_id_is_stable_and_does_not_depend_on_message(self):
        values = dict(
            source_database=DATABASE,
            source_class="Desordre",
            source_id="id-1",
            category="MISSING_REFERENCE_VALUE",
            source_field="typeDesordreId",
        )
        first = make_anomaly_id(**values)
        second = Anomaly.create(
            **values,
            severity="WARNING",
            message="Nouveau texte sans effet sur l'identité",
        ).anomaly_id
        self.assertEqual(first, second)
        self.assertEqual(first, "REF-6FF9A91D83FFF5C6EBE4")
        self.assertFalse(first.isdigit())

    def test_new_anomaly_is_open(self):
        anomaly = Anomaly.create(
            category="UNKNOWN_CLASS",
            severity="ERROR",
            source_database=DATABASE,
            source_class="Future",
        )
        self.assertEqual(anomaly.status, "OPEN")
        self.assertTrue(anomaly.active)

    def test_manual_status_is_preserved_across_regeneration(self):
        current = Anomaly.create(
            category="UNKNOWN_CLASS",
            severity="ERROR",
            source_database=DATABASE,
            source_class="Future",
            message="message v2",
        )
        previous = Anomaly(
            **{
                **current.to_dict(),
                "message": "message v1",
                "status": "ACCEPTED_AS_IS",
                "resolution_comment": "Décision validée",
                "first_detected_at": "2026-01-01T00:00:00Z",
                "last_detected_at": "2026-01-01T00:00:00Z",
            }
        )
        merged = merge_previous_status(
            [current], [previous], detected_at="2026-02-01T00:00:00Z"
        )[0]
        self.assertEqual(merged.status, "ACCEPTED_AS_IS")
        self.assertEqual(merged.resolution_comment, "Décision validée")
        self.assertEqual(merged.first_detected_at, "2026-01-01T00:00:00Z")
        self.assertEqual(merged.last_detected_at, "2026-02-01T00:00:00Z")
        self.assertEqual(merged.message, "message v2")

    def test_disappeared_then_reappeared_anomaly_keeps_identity_and_history(self):
        anomaly = Anomaly.create(
            category="UNKNOWN_CLASS",
            severity="ERROR",
            source_database=DATABASE,
            source_class="Future",
        )
        first = merge_previous_status(
            [anomaly], [], detected_at="2026-01-01T00:00:00Z"
        )
        disappeared = merge_previous_status(
            [], first, detected_at="2026-02-01T00:00:00Z"
        )
        self.assertFalse(disappeared[0].active)
        self.assertEqual(disappeared[0].status, "OPEN")
        self.assertEqual(
            disappeared[0].resolved_detected_at, "2026-02-01T00:00:00Z"
        )
        reappeared = merge_previous_status(
            [anomaly], disappeared, detected_at="2026-03-01T00:00:00Z"
        )
        self.assertTrue(reappeared[0].active)
        self.assertEqual(reappeared[0].anomaly_id, anomaly.anomaly_id)
        self.assertEqual(
            reappeared[0].first_detected_at, "2026-01-01T00:00:00Z"
        )


class AnomalySerializationTest(unittest.TestCase):
    def test_json_and_csv_are_valid_and_complete(self):
        anomaly = Anomaly.create(
            category="INVALID_GEOMETRY",
            severity="ERROR",
            source_database=DATABASE,
            source_class="AmenagementHydraulique",
            source_id="id-1",
            source_document_id="raw-id-1",
            source_field="geometry",
            details={"reason": "auto-intersection"},
        )
        with tempfile.TemporaryDirectory() as directory:
            json_path = Path(directory) / "anomalies.json"
            csv_path = Path(directory) / "anomalies.csv"
            write_anomalies_json(json_path, [anomaly])
            write_anomalies_csv(csv_path, [anomaly])
            decoded = json.loads(json_path.read_text(encoding="utf-8"))
            with csv_path.open(encoding="utf-8", newline="") as stream:
                reader = csv.DictReader(stream)
                header = reader.fieldnames
                rows = list(reader)
        self.assertEqual(decoded[0]["anomaly_id"], anomaly.anomaly_id)
        self.assertEqual(decoded[0]["source_document_id"], "raw-id-1")
        self.assertEqual(rows[0]["category"], "INVALID_GEOMETRY")
        self.assertEqual(rows[0]["source_document_id"], "raw-id-1")
        self.assertIn("auto-intersection", rows[0]["details"])
        self.assertEqual(rows[0]["actionable"], "TRUE")
        self.assertEqual(rows[0]["family"], "DATA")
        self.assertNotIn("actionable", decoded[0])
        self.assertNotIn("family", decoded[0])
        self.assertEqual(
            header[:10],
            [
                "anomaly_id",
                "active",
                "actionable",
                "status",
                "severity",
                "family",
                "category",
                "source_class",
                "source_id",
                "source_document_id",
            ],
        )

    def test_source_document_id_does_not_change_anomaly_identity(self):
        values = dict(
            category="INVALID_GEOMETRY",
            severity="WARNING",
            source_database=DATABASE,
            source_class="Vegetation",
            source_id="ca7792c0-6baa-3f90-9d82-ec3731153d53",
            source_field="geometry",
        )
        without_document = Anomaly.create(**values)
        with_document = Anomaly.create(
            **values,
            source_document_id="ca7792c06baa3f909d82ec3731153d53",
        )
        self.assertEqual(without_document.anomaly_id, with_document.anomaly_id)

    def test_old_register_without_source_document_id_keeps_resolution(self):
        current = Anomaly.create(
            category="MISSING_GEOMETRY",
            severity="WARNING",
            source_database=DATABASE,
            source_class="Vegetation",
            source_id="ca7792c0-6baa-3f90-9d82-ec3731153d53",
            source_document_id="ca7792c06baa3f909d82ec3731153d53",
            source_field="geometry",
        )
        old_payload = current.to_dict()
        old_payload.pop("source_document_id")
        old_payload.update(
            status="ACCEPTED_AS_IS",
            resolution_comment="Décision historique",
            first_detected_at="2026-01-01T00:00:00Z",
        )
        previous = Anomaly.from_dict(old_payload)
        merged = merge_previous_status(
            [current], [previous], detected_at="2026-02-01T00:00:00Z"
        )[0]
        self.assertEqual(merged.anomaly_id, previous.anomaly_id)
        self.assertEqual(merged.status, "ACCEPTED_AS_IS")
        self.assertEqual(merged.resolution_comment, "Décision historique")
        self.assertEqual(merged.first_detected_at, "2026-01-01T00:00:00Z")
        self.assertEqual(
            merged.source_document_id,
            "ca7792c06baa3f909d82ec3731153d53",
        )

    def test_csv_actionable_view_uses_exactly_the_shared_cli_rule(self):
        anomalies = [
            Anomaly.create(
                category="INVALID_GEOMETRY",
                severity="WARNING",
                source_database=DATABASE,
                source_class="Geometry",
                source_id="actionable",
            ),
            replace(
                Anomaly.create(
                    category="MISSING_GEOMETRY",
                    severity="WARNING",
                    source_database=DATABASE,
                    source_class="Geometry",
                    source_id="inactive",
                ),
                active=False,
            ),
            replace(
                Anomaly.create(
                    category="BROKEN_REFERENCE",
                    severity="ERROR",
                    source_database=DATABASE,
                    source_class="Relation",
                    source_id="accepted",
                ),
                status="ACCEPTED_AS_IS",
            ),
            Anomaly.create(
                category="DEFERRED_FEATURE",
                severity="WARNING",
                source_database=DATABASE,
                source_class="Coverage",
                source_id="coverage",
            ),
            Anomaly.create(
                category="SOURCE_OVERRIDE",
                severity="INFO",
                source_database=DATABASE,
                source_class="Decision",
                source_id="decision",
            ),
        ]
        expected_ids = {
            anomaly.anomaly_id for anomaly in anomalies if is_actionable(anomaly)
        }
        with tempfile.TemporaryDirectory() as directory:
            json_path = Path(directory) / "anomalies.json"
            csv_path = Path(directory) / "anomalies.csv"
            write_anomalies_json(json_path, anomalies)
            canonical_json = json.loads(json_path.read_text(encoding="utf-8"))
            write_anomalies_csv(csv_path, anomalies)
            with csv_path.open(encoding="utf-8", newline="") as stream:
                csv_rows = list(csv.DictReader(stream))
            output = io.StringIO()
            with (
                patch("sirs_postgre.cli.DEFAULT_JSON_PATH", json_path),
                patch("sirs_postgre.cli.DEFAULT_CSV_PATH", csv_path),
                redirect_stdout(output),
            ):
                self.assertEqual(main(["anomalies", "--actionable"]), 0)

        csv_ids = {
            row["anomaly_id"] for row in csv_rows if row["actionable"] == "TRUE"
        }
        cli_ids = {
            line.split(" | ", 1)[0]
            for line in output.getvalue().splitlines()
            if line.startswith(tuple(expected_ids))
        }
        self.assertEqual(csv_ids, expected_ids)
        self.assertEqual(cli_ids, expected_ids)
        self.assertEqual(sum(row["actionable"] == "TRUE" for row in csv_rows), 1)
        self.assertEqual(
            [row["actionable"] for row in csv_rows],
            ["TRUE", "FALSE", "FALSE", "FALSE", "FALSE"],
        )
        self.assertTrue(all("actionable" not in item for item in canonical_json))
        self.assertTrue(all("family" not in item for item in canonical_json))

    def test_register_update_preserves_manual_resolution(self):
        anomaly = Anomaly.create(
            category="UNKNOWN_FIELD",
            severity="WARNING",
            source_database=DATABASE,
            source_class="Digue",
            source_field="nouveauChamp",
        )
        with tempfile.TemporaryDirectory() as directory:
            json_path = Path(directory) / "anomalies.json"
            csv_path = Path(directory) / "anomalies.csv"
            update_anomaly_register(
                [anomaly],
                json_path=json_path,
                csv_path=csv_path,
                detected_at="2026-01-01T00:00:00Z",
            )
            resolve_anomaly(
                anomaly.anomaly_id,
                status="RESOLVED_BY_MIGRATOR",
                comment="Mapping ajouté",
                json_path=json_path,
                csv_path=csv_path,
            )
            update_anomaly_register(
                [anomaly],
                json_path=json_path,
                csv_path=csv_path,
                detected_at="2026-02-01T00:00:00Z",
            )
            loaded = load_anomalies(json_path)[0]
        self.assertEqual(loaded.status, "RESOLVED_BY_MIGRATOR")
        self.assertEqual(loaded.resolution_comment, "Mapping ajouté")


class AnomalyCollectionTest(unittest.TestCase):
    def collect(self, documents, rows, *, database=DATABASE, prepared=None):
        return collect_anomalies(
            documents,
            source_database=database,
            coverage_rows=rows,
            prepared_core=prepared,
        )

    def test_detects_invalid_geometry(self):
        source_id = UUID(int=1).hex
        anomalies = self.collect(
            [
                source_doc(
                    "ArbreVegetation",
                    source_id,
                    geometry="POLYGON ((0 0, 1 0, 0 0, 0 0))",
                )
            ],
            [coverage_row("ArbreVegetation", "PARTIELLE")],
        )
        self.assertIn("INVALID_GEOMETRY", {item.category for item in anomalies})

    def test_does_not_report_invalid_geometry_already_handled_by_preparation(self):
        source_id = UUID(int=1)
        prepared = SimpleNamespace(
            vegetation=SimpleNamespace(
                vegetation=[
                    SimpleNamespace(
                        id=source_id,
                        source_class="ArbreVegetation",
                        geometry_method="DEGENERATE_LINE_TO_POINT",
                    )
                ]
            )
        )
        anomalies = self.collect(
            [
                source_doc(
                    "ArbreVegetation",
                    source_id.hex,
                    geometry="LINESTRING (0 0, 0 0)",
                )
            ],
            [coverage_row("ArbreVegetation", "PARTIELLE")],
            prepared=prepared,
        )
        self.assertNotIn("INVALID_GEOMETRY", {item.category for item in anomalies})

    def test_amenagement_polygon_is_not_checked_by_the_vegetation_parser(self):
        source_id = "bb404c68-6144-992f-f4ec-d939ea005d75"
        anomalies = self.collect(
            [
                source_doc(
                    "AmenagementHydraulique",
                    source_id,
                    geometry="POLYGON ((0 0, 1 0, 0 0, 0 0))",
                )
            ],
            [coverage_row("AmenagementHydraulique", "PARTIELLE")],
            database="cabbalr",
        )
        self.assertNotIn("INVALID_GEOMETRY", {item.category for item in anomalies})
        historical_false_positive = Anomaly.create(
            category="INVALID_GEOMETRY",
            severity="WARNING",
            source_database="cabbalr",
            source_class="AmenagementHydraulique",
            source_id=source_id,
            source_field="geometry",
        )
        merged = merge_previous_status(
            anomalies,
            [historical_false_positive],
            detected_at="2026-02-01T00:00:00Z",
        )
        historical = next(
            item
            for item in merged
            if item.anomaly_id == historical_false_positive.anomaly_id
        )
        self.assertFalse(historical.active)
        self.assertEqual(historical.status, "OPEN")

    def test_detects_broken_reference(self):
        anomalies = self.collect(
            [source_doc("Digue", UUID(int=1).hex, systemeEndiguementId=UUID(int=2).hex)],
            [coverage_row("Digue", "MIGREE")],
        )
        broken = next(item for item in anomalies if item.category == "BROKEN_REFERENCE")
        self.assertEqual(broken.severity, "BLOCKING")
        self.assertEqual(broken.source_field, "systemeEndiguementId")

    def test_direct_document_keeps_exact_compact_and_hyphenated_ids(self):
        compact_id = UUID(int=101).hex
        hyphenated_id = str(UUID(int=102))
        anomalies = self.collect(
            [
                source_doc(
                    "Desordre",
                    compact_id,
                    categorieDesordreId="RefCategorieDesordre:1",
                    typeDesordreId=None,
                ),
                source_doc(
                    "Desordre",
                    hyphenated_id,
                    categorieDesordreId="RefCategorieDesordre:1",
                    typeDesordreId=None,
                ),
            ],
            [coverage_row("Desordre", "MIGREE")],
        )
        by_source_id = {
            item.source_id: item
            for item in anomalies
            if item.category == "MISSING_REFERENCE_VALUE"
        }
        compact = by_source_id[str(UUID(compact_id))]
        hyphenated = by_source_id[hyphenated_id]
        self.assertEqual(compact.source_document_id, compact_id)
        self.assertEqual(hyphenated.source_document_id, hyphenated_id)

    def test_global_coverage_anomaly_has_no_source_document(self):
        anomalies = self.collect(
            [source_doc("Future", "future-1")],
            [coverage_row("Future", "NON_MIGREE", known=False)],
        )
        unknown = next(item for item in anomalies if item.category == "UNKNOWN_CLASS")
        self.assertIsNone(unknown.source_document_id)

    def test_migrated_technical_access_needs_no_parent_or_spatial_inference(self):
        for database in ("cabbalr", "another_sirs_database"):
            with self.subTest(database=database):
                anomalies = self.collect(
                    [
                        source_doc(
                            "CheminAccesDependance",
                            UUID(int=42).hex,
                            geometry="LINESTRING (0 0, 1 1)",
                        )
                    ],
                    [
                        coverage_row(
                            "CheminAccesDependance",
                            "MIGREE",
                            known=True,
                        )
                    ],
                    database=database,
                )
                categories = [anomaly.category for anomaly in anomalies]
                self.assertNotIn("DEFERRED_FEATURE", categories)
                self.assertNotIn("AMBIGUOUS_RELATION", categories)

    def test_real_ambiguous_relation_category_remains_actionable_data(self):
        anomaly = Anomaly.create(
            category="AMBIGUOUS_RELATION",
            severity="ERROR",
            source_database=DATABASE,
            source_class="FutureRelationSource",
            source_id="relation-1",
            source_field="parentIds",
        )
        self.assertEqual(anomaly.category, "AMBIGUOUS_RELATION")
        self.assertEqual(FAMILY_BY_CATEGORY[anomaly.category], "DATA")
        self.assertIn(anomaly.category, ACTIONABLE_CATEGORIES)

    def test_detects_unknown_class_and_actionable_unknown_fields(self):
        anomalies = self.collect(
            [source_doc("Future", "future-1"), source_doc("Digue", UUID(int=1).hex)],
            [
                coverage_row("Future", "NON_MIGREE", known=False),
                coverage_row("Digue", "MIGREE", unanalysed=("nouveauChamp", "_attachments")),
            ],
        )
        categories = {item.category for item in anomalies}
        self.assertIn("UNKNOWN_CLASS", categories)
        field = next(item for item in anomalies if item.category == "UNMIGRATED_FIELD")
        self.assertEqual(field.details["fields"], ["nouveauChamp"])

    def test_detects_unmigrated_media_and_photo_without_date(self):
        future_photo_id = UUID(int=10).hex
        migrated_photo_id = UUID(int=11).hex
        anomalies = self.collect(
            [
                source_doc(
                    "Future",
                    "future-1",
                    photos=[{"id": future_photo_id, "chemin": "future.jpg", "valid": True}],
                ),
                source_doc(
                    "OuvrageParticulier",
                    UUID(int=2).hex,
                    photos=[{"id": migrated_photo_id, "chemin": "ouvrage.jpg", "valid": True}],
                ),
            ],
            [
                coverage_row("Future", "NON_MIGREE", known=False),
                coverage_row("OuvrageParticulier", "PARTIELLE"),
            ],
        )
        by_category = {item.category: item for item in anomalies}
        self.assertEqual(by_category["UNMIGRATED_MEDIA"].source_id, str(UUID(future_photo_id)))
        self.assertEqual(by_category["PHOTO_WITHOUT_DATE"].source_id, str(UUID(migrated_photo_id)))
        self.assertEqual(by_category["UNMIGRATED_MEDIA"].source_document_id, "future-1")
        self.assertEqual(
            by_category["PHOTO_WITHOUT_DATE"].source_document_id,
            UUID(int=2).hex,
        )

    def test_detects_duplicate_and_missing_photo_identifiers(self):
        duplicate_id = UUID(int=30).hex
        anomalies = self.collect(
            [
                source_doc(
                    "OuvrageParticulier",
                    UUID(int=2).hex,
                    photos=[{"id": duplicate_id}, {}],
                ),
                source_doc(
                    "TronconDigue",
                    UUID(int=3).hex,
                    observations=[{"photos": [{"id": duplicate_id}]}],
                ),
            ],
            [
                coverage_row("OuvrageParticulier", "PARTIELLE"),
                coverage_row("TronconDigue", "MIGREE"),
            ],
        )
        blocking_media = [
            anomaly
            for anomaly in anomalies
            if anomaly.category == "UNMIGRATED_MEDIA"
            and anomaly.severity == "BLOCKING"
        ]
        self.assertEqual(len(blocking_media), 2)
        self.assertIn(
            str(UUID(duplicate_id)),
            {anomaly.source_id for anomaly in blocking_media},
        )

    def test_nested_photo_points_to_exact_containing_document(self):
        parent_id = UUID(int=40).hex
        photo_id = UUID(int=41).hex
        anomalies = self.collect(
            [
                source_doc(
                    "TronconDigue",
                    parent_id,
                    observations=[
                        {"photos": [{"id": photo_id}, {"id": photo_id}]}
                    ],
                )
            ],
            [coverage_row("TronconDigue", "MIGREE")],
        )
        duplicate = next(
            anomaly
            for anomaly in anomalies
            if anomaly.category == "UNMIGRATED_MEDIA"
            and anomaly.source_id == str(UUID(photo_id))
        )
        self.assertEqual(duplicate.source_document_id, parent_id)

    def test_detects_source_overrides_and_manual_review(self):
        amenagement_id = "496d26f14278405a4172bf66ec000321"
        vegetation_id = UUID(int=20)
        prepared = SimpleNamespace(
            vegetation=SimpleNamespace(
                vegetation=[
                    SimpleNamespace(
                        id=vegetation_id,
                        source_class="PeuplementVegetation",
                        geometry_method=MANUAL_REVIEW,
                    )
                ]
            )
        )
        anomalies = self.collect(
            [
                source_doc("AmenagementHydraulique", amenagement_id),
                source_doc(
                    "PeuplementVegetation",
                    vegetation_id.hex,
                    geometry="POLYGON ((0 0, 1 0, 0 0, 0 0))",
                ),
            ],
            [
                coverage_row("AmenagementHydraulique", "PARTIELLE"),
                coverage_row("PeuplementVegetation", "PARTIELLE"),
            ],
            database="cabbalr",
            prepared=prepared,
        )
        categories = [item.category for item in anomalies]
        self.assertIn("SOURCE_OVERRIDE", categories)
        self.assertIn("MANUAL_REVIEW", categories)


class AnomalyCliTest(unittest.TestCase):
    def make_register(self, directory):
        json_path = Path(directory) / "anomalies.json"
        csv_path = Path(directory) / "anomalies.csv"
        anomalies = [
            Anomaly.create(
                category="INVALID_GEOMETRY",
                severity="WARNING",
                source_database=DATABASE,
                source_class="Vegetation",
                source_id="id-geometry",
            ),
            Anomaly.create(
                category="UNMIGRATED_MEDIA",
                severity="ERROR",
                source_database=DATABASE,
                source_class="Photo",
                source_id="id-photo",
            ),
        ]
        update_anomaly_register(anomalies, json_path=json_path, csv_path=csv_path)
        return json_path, csv_path, anomalies

    def make_category_register(self, directory):
        json_path = Path(directory) / "anomalies.json"
        csv_path = Path(directory) / "anomalies.csv"
        categories = (
            ("MANUAL_REVIEW", "WARNING"),
            ("UNMIGRATED_MEDIA", "ERROR"),
            ("MISSING_REFERENCE_VALUE", "WARNING"),
            ("AMBIGUOUS_RELATION", "ERROR"),
            ("PARTIALLY_MIGRATED_CLASS", "INFO"),
            ("DEFERRED_FEATURE", "WARNING"),
            ("SOURCE_OVERRIDE", "INFO"),
        )
        anomalies = [
            Anomaly.create(
                category=category,
                severity=severity,
                source_database=DATABASE,
                source_class=f"Class{index}",
                source_id=f"id-{index}",
            )
            for index, (category, severity) in enumerate(categories)
        ]
        write_anomalies_json(json_path, anomalies)
        write_anomalies_csv(csv_path, anomalies)
        return json_path, csv_path, anomalies

    def test_filters_open_category_and_source_id(self):
        with tempfile.TemporaryDirectory() as directory:
            json_path, csv_path, _ = self.make_register(directory)
            for arguments, expected, excluded in (
                (["anomalies", "--open"], "INVALID_GEOMETRY", None),
                (["anomalies", "--category", "UNMIGRATED_MEDIA"], "UNMIGRATED_MEDIA", "INVALID_GEOMETRY"),
                (["anomalies", "--source-id", "id-photo"], "id-photo", "id-geometry"),
            ):
                output = io.StringIO()
                with (
                    patch("sirs_postgre.cli.DEFAULT_JSON_PATH", json_path),
                    patch("sirs_postgre.cli.DEFAULT_CSV_PATH", csv_path),
                    redirect_stdout(output),
                ):
                    self.assertEqual(main(arguments), 0)
                self.assertIn(expected, output.getvalue())
                if excluded:
                    self.assertNotIn(excluded, output.getvalue())

    def test_summary_distinguishes_active_inactive_and_active_statuses(self):
        with tempfile.TemporaryDirectory() as directory:
            json_path, csv_path, anomalies = self.make_register(directory)
            register = [
                replace(anomalies[0], active=False),
                replace(anomalies[1], status="ACCEPTED_AS_IS"),
            ]
            write_anomalies_json(json_path, register)
            write_anomalies_csv(csv_path, register)
            output = io.StringIO()
            with (
                patch("sirs_postgre.cli.DEFAULT_JSON_PATH", json_path),
                patch("sirs_postgre.cli.DEFAULT_CSV_PATH", csv_path),
                redirect_stdout(output),
            ):
                self.assertEqual(main(["anomalies"]), 0)
        text = output.getvalue()
        self.assertIn("ACTIVE : 1", text)
        self.assertIn("INACTIVE : 1", text)
        self.assertIn("ACTIVE OPEN : 0", text)
        self.assertIn("ACTIVE ACCEPTED : 1", text)
        self.assertIn("ACTIVE RESOLVED : 0", text)

    def test_actionable_includes_data_and_excludes_coverage_and_decisions(self):
        with tempfile.TemporaryDirectory() as directory:
            json_path, csv_path, _ = self.make_category_register(directory)
            output = io.StringIO()
            with (
                patch("sirs_postgre.cli.DEFAULT_JSON_PATH", json_path),
                patch("sirs_postgre.cli.DEFAULT_CSV_PATH", csv_path),
                redirect_stdout(output),
            ):
                self.assertEqual(main(["anomalies", "--actionable"]), 0)
        text = output.getvalue()
        for category in (
            "MANUAL_REVIEW",
            "UNMIGRATED_MEDIA",
            "MISSING_REFERENCE_VALUE",
            "AMBIGUOUS_RELATION",
        ):
            self.assertIn(category, text)
        for category in (
            "PARTIALLY_MIGRATED_CLASS",
            "DEFERRED_FEATURE",
            "SOURCE_OVERRIDE",
        ):
            self.assertNotIn(category, text)

    @patch("sirs_postgre.cli.connect_couchdb")
    def test_resolve_only_updates_the_local_register(self, connect_source):
        with tempfile.TemporaryDirectory() as directory:
            json_path, csv_path, anomalies = self.make_register(directory)
            output = io.StringIO()
            with (
                patch("sirs_postgre.cli.DEFAULT_JSON_PATH", json_path),
                patch("sirs_postgre.cli.DEFAULT_CSV_PATH", csv_path),
                redirect_stdout(output),
            ):
                result = main(
                    [
                        "anomalies",
                        "resolve",
                        anomalies[0].anomaly_id,
                        "--status",
                        "ACCEPTED_AS_IS",
                        "--comment",
                        "Décision locale",
                    ]
                )
            self.assertEqual(result, 0)
            connect_source.assert_not_called()
            resolved = {item.anomaly_id: item for item in load_anomalies(json_path)}
            self.assertEqual(resolved[anomalies[0].anomaly_id].status, "ACCEPTED_AS_IS")
            self.assertEqual(
                resolved[anomalies[0].anomaly_id].resolution_comment,
                "Décision locale",
            )
            self.assertIsNotNone(
                resolved[anomalies[0].anomaly_id].resolved_detected_at
            )


if __name__ == "__main__":
    unittest.main()
