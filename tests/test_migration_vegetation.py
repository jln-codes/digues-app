import unittest
from pathlib import Path
from uuid import UUID

from digues_app.migration.source_overrides import SourceMigrationOverrides
from digues_app.migration.vegetation import (
    DEGENERATE_LINE_TO_POINT,
    KEEP_GEOMETRY,
    KEEP_NULL,
    MANUAL_REVIEW,
    POSITION_DEBUT_TO_POINT,
    RECONSTRUCT_FROM_EXPLICIT_GEOMETRY,
    TARGET_REFERENCES,
    VegetationMigrationError,
    inspect_wkt,
    prepare_vegetation_migration,
)


PLAN_ID = "00000000-0000-0000-0000-000000000001"
PARCELLE_ID = "00000000-0000-0000-0000-000000000002"
TRONCON_ID = UUID("00000000-0000-0000-0000-000000000003")
SECOND_TRONCON_ID = UUID("00000000-0000-0000-0000-000000000004")
OBJECT_ID = "00000000-0000-0000-0000-000000000010"
PARCELLE_LINE = "LINESTRING (0 0, 20 0)"
VALID_POLYGON = "POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))"


def physical_document(**updates):
    document = {
        "_id": OBJECT_ID,
        "designation": "Nom libre sans effet sur la règle",
        "date_debut": "2026-08-30",
        "parcelleId": PARCELLE_ID,
        "valid": True,
    }
    document.update(updates)
    return document


def source_fixture(source_class, document, *, parcelle_updates=None):
    parcelle = {
        "_id": PARCELLE_ID,
        "planId": PLAN_ID,
        "linearId": TRONCON_ID.hex,
        "designation": "Parcelle test",
        "date_debut": "2026-08-30",
        "geometry": PARCELLE_LINE,
        "valid": True,
    }
    parcelle.update(parcelle_updates or {})
    source = {
        "PlanVegetation": [
            {
                "_id": PLAN_ID,
                "libelle": "Plan test",
                "anneeDebut": 2025,
                "anneeFin": 2030,
                "valid": True,
            }
        ],
        "ParcelleVegetation": [parcelle],
        "ArbreVegetation": [],
        "PeuplementVegetation": [],
        "InvasiveVegetation": [],
    }
    source[source_class] = [document]
    return source


def prepare(source, *, database="autre_base", troncons=None, overrides=None):
    return prepare_vegetation_migration(
        source,
        troncon_ids=troncons or {TRONCON_ID},
        source_database=database,
        overrides=overrides,
    )


class VegetationGeometryTest(unittest.TestCase):
    def test_point_geometry_is_kept(self):
        prepared = prepare(
            source_fixture(
                "ArbreVegetation",
                physical_document(
                    geometry="POINT (2 3)",
                    explicitGeometry="POINT (2 3)",
                ),
            )
        )
        row = prepared.vegetation[0]
        self.assertEqual(row.geometry_method, KEEP_GEOMETRY)
        self.assertEqual(row.geometry_wkt, "POINT (2 3)")

    def test_degenerate_tree_line_becomes_its_stored_point(self):
        prepared = prepare(
            source_fixture(
                "ArbreVegetation",
                physical_document(
                    geometry="LINESTRING (7 8, 7.0 8.00)",
                    positionDebut="POINT (100 200)",
                    positionFin="POINT (100 200)",
                ),
            )
        )
        row = prepared.vegetation[0]
        self.assertEqual(row.geometry_method, DEGENERATE_LINE_TO_POINT)
        self.assertEqual(row.geometry_wkt, "POINT (7 8)")

    def test_tree_without_geometry_uses_equal_positions(self):
        prepared = prepare(
            source_fixture(
                "ArbreVegetation",
                physical_document(
                    positionDebut="POINT (4 5)",
                    positionFin="POINT (4.0 5.00)",
                ),
            )
        )
        row = prepared.vegetation[0]
        self.assertEqual(row.geometry_method, POSITION_DEBUT_TO_POINT)
        self.assertEqual(row.geometry_wkt, "POINT (4 5)")

    def test_object_without_geometry_or_alternative_keeps_null(self):
        prepared = prepare(
            source_fixture("PeuplementVegetation", physical_document())
        )
        row = prepared.vegetation[0]
        self.assertEqual(row.geometry_method, KEEP_NULL)
        self.assertIsNone(row.geometry_wkt)
        self.assertEqual(prepared.manual_review_warnings, ())

    def test_invalid_geometry_with_compatible_explicit_is_reconstructed(self):
        prepared = prepare(
            source_fixture(
                "PeuplementVegetation",
                physical_document(
                    geometry="POLYGON ((0 0, 1 0, 0 0, 0 0))",
                    explicitGeometry=VALID_POLYGON,
                ),
            )
        )
        row = prepared.vegetation[0]
        self.assertEqual(row.geometry_method, RECONSTRUCT_FROM_EXPLICIT_GEOMETRY)
        self.assertEqual(row.geometry_wkt, VALID_POLYGON)

    def test_invalid_geometry_without_alternative_requires_review(self):
        prepared = prepare(
            source_fixture(
                "PeuplementVegetation",
                physical_document(geometry="POLYGON ((0 0, 1 0, 0 0, 0 0))"),
            )
        )
        row = prepared.vegetation[0]
        self.assertEqual(row.geometry_method, MANUAL_REVIEW)
        self.assertIsNone(row.geometry_wkt)
        self.assertEqual(len(prepared.manual_review_warnings), 1)

    def test_two_valid_disjoint_geometries_require_review(self):
        prepared = prepare(
            source_fixture(
                "InvasiveVegetation",
                physical_document(
                    geometry=VALID_POLYGON,
                    explicitGeometry=(
                        "POLYGON ((20 20, 30 20, 30 30, 20 30, 20 20))"
                    ),
                ),
            )
        )
        self.assertEqual(prepared.vegetation[0].geometry_method, MANUAL_REVIEW)
        self.assertIsNone(prepared.vegetation[0].geometry_wkt)

    def test_make_valid_is_never_used_by_the_migrator(self):
        module = Path("digues_app/migration/vegetation.py").read_text()
        self.assertNotIn("ST_MakeValid(", module)


class VegetationStructureTest(unittest.TestCase):
    def test_references_use_readable_stable_ids(self):
        self.assertEqual(
            [row.id for row in TARGET_REFERENCES["ref_natures_vegetation"]],
            ["ARB", "PEU", "INV", "IND"],
        )
        for rows in TARGET_REFERENCES.values():
            self.assertTrue(all(row.id == row.abrege and row.valid for row in rows))

    def test_source_classes_map_to_structural_natures_without_names(self):
        expected = {
            "ArbreVegetation": "ARB",
            "PeuplementVegetation": "PEU",
            "InvasiveVegetation": "INV",
        }
        for source_class, nature in expected.items():
            with self.subTest(source_class=source_class):
                prepared = prepare(
                    source_fixture(source_class, physical_document(geometry="POINT (1 1)"))
                )
                self.assertEqual(prepared.vegetation[0].nature_id, nature)

    def test_explicit_parcelle_troncon_relation_creates_link(self):
        prepared = prepare(
            source_fixture("ArbreVegetation", physical_document(geometry="POINT (1 1)"))
        )
        self.assertEqual(len(prepared.links), 1)
        self.assertEqual(prepared.links[0].troncon_id, TRONCON_ID)

    def test_schema_input_can_represent_multiple_explicit_troncons(self):
        source = source_fixture(
            "ArbreVegetation",
            physical_document(geometry="POINT (1 1)"),
            parcelle_updates={
                "linearId": TRONCON_ID.hex,
                "linearIds": [SECOND_TRONCON_ID.hex],
            },
        )
        prepared = prepare(
            source, troncons={TRONCON_ID, SECOND_TRONCON_ID}
        )
        self.assertEqual(
            {row.troncon_id for row in prepared.links},
            {TRONCON_ID, SECOND_TRONCON_ID},
        )

    def test_broken_plan_parcelle_or_troncon_is_blocking(self):
        source = source_fixture("ArbreVegetation", physical_document(geometry="POINT (1 1)"))
        source["ParcelleVegetation"][0]["planId"] = UUID(int=999).hex
        with self.assertRaisesRegex(VegetationMigrationError, "plan absent"):
            prepare(source)

        source = source_fixture("ArbreVegetation", physical_document(geometry="POINT (1 1)"))
        source["ParcelleVegetation"][0]["linearId"] = UUID(int=999).hex
        with self.assertRaisesRegex(VegetationMigrationError, "tronçon absent"):
            prepare(source)

        source = source_fixture("ArbreVegetation", physical_document(geometry="POINT (1 1)"))
        source["ArbreVegetation"][0]["parcelleId"] = UUID(int=999).hex
        with self.assertRaisesRegex(VegetationMigrationError, "parcelle absente"):
            prepare(source)

    def test_valid_false_and_comments_are_preserved(self):
        prepared = prepare(
            source_fixture(
                "ArbreVegetation",
                physical_document(
                    geometry="POINT (1 1)",
                    valid=False,
                    commentaire="Cerisier — texte brut",
                ),
            )
        )
        self.assertFalse(prepared.vegetation[0].valid)
        self.assertEqual(prepared.vegetation[0].commentaire, "Cerisier — texte brut")

    def test_explicit_override_is_isolated_and_not_name_based(self):
        synthetic_id = UUID(int=103).hex
        document = physical_document(
            _id=synthetic_id,
            designation="Nom quelconque",
            geometry="POLYGON ((0 0, 0 0, 0 0, 0 0))",
            explicitGeometry="POLYGON ((20 20, 30 20, 30 30, 20 30, 20 20))",
        )
        other = prepare(
            source_fixture("PeuplementVegetation", document),
            database="copie_externe",
        )
        self.assertEqual(other.vegetation[0].geometry_method, MANUAL_REVIEW)

        overridden = prepare(
            source_fixture("PeuplementVegetation", document),
            database="synthetic_source",
            overrides=SourceMigrationOverrides(
                vegetation_geometry_source_by_id={
                    synthetic_id: "explicitGeometry"
                }
            ),
        )
        self.assertEqual(
            overridden.vegetation[0].geometry_method,
            RECONSTRUCT_FROM_EXPLICIT_GEOMETRY,
        )

    def test_invalid_polygon_parser_detects_self_intersection(self):
        geometry = inspect_wkt("POLYGON ((0 0, 10 10, 0 10, 10 0, 0 0))")
        self.assertIsNotNone(geometry)
        self.assertFalse(geometry.valid)
        self.assertIn(geometry.reason, {"aire nulle", "auto-intersection"})


if __name__ == "__main__":
    unittest.main()
