import copy
import unittest

from sirs_postgre.migration.core import (
    CORE_SOURCE_CLASSES,
    INSERT_STATEMENTS,
    CoreMigrationError,
    TargetNotEmptyError,
    couchdb_id_to_uuid,
    desordre_geometry_from_positions,
    desordre_geometry_from_source,
    execute_core_migration,
    _insert_prepared_core,
    prepare_core_migration,
    validate_troncon_wkt,
)
from sirs_postgre.migration.crs import CRSInfo
from sirs_postgre.target.schema import EXPECTED_TABLES


IDS = {
    "systeme": "00000000000000000000000000000001",
    "digue": "00000000000000000000000000000002",
    "troncon": "00000000000000000000000000000003",
    "desordre": "00000000000000000000000000000004",
    "observation": "00000000000000000000000000000005",
    "photo_1": "00000000000000000000000000000006",
    "photo_2": "00000000000000000000000000000007",
    "direct_photo": "00000000000000000000000000000008",
}

REFERENCE_IDS = {
    "categorie": "RefCategorieDesordre:1",
    "categorie_2": "RefCategorieDesordre:2",
    "type": "RefTypeDesordre:1",
    "urgence": "RefUrgence:1",
}


def source_fixture():
    return {
        "RefCategorieDesordre": [
            {
                "_id": REFERENCE_IDS["categorie"],
                "libelle": "Érosion externe",
                "valid": False,
            },
            {
                "_id": REFERENCE_IDS["categorie_2"],
                "libelle": "Érosion interne",
                "valid": True,
            },
        ],
        "RefTypeDesordre": [
            {
                "_id": REFERENCE_IDS["type"],
                "categorieId": REFERENCE_IDS["categorie"],
                "libelle": "Érosion longitudinale",
                "valid": True,
            }
        ],
        "RefUrgence": [
            {
                "_id": REFERENCE_IDS["urgence"],
                "libelle": "Urgent",
                "valid": False,
            }
        ],
        "SystemeEndiguement": [
            {"_id": IDS["systeme"], "libelle": "Système test", "valid": True}
        ],
        "Digue": [
            {
                "_id": IDS["digue"],
                "systemeEndiguementId": IDS["systeme"],
                "libelle": "Digue test",
                "valid": True,
            }
        ],
        "TronconDigue": [
            {
                "_id": IDS["troncon"],
                "digueId": IDS["digue"],
                "libelle": "Tronçon test",
                "geometry": "LINESTRING (1 2, 3 4)",
                "valid": True,
                "photos": [
                    {
                        "id": IDS["direct_photo"],
                        "chemin": "troncon/directe.jpg",
                        "valid": True,
                    }
                ],
            }
        ],
        "Desordre": [
            {
                "_id": IDS["desordre"],
                "designation": "Désordre test",
                "commentaire": "Commentaire",
                "date_debut": "2026-01-02",
                "positionDebut": "POINT(10 20)",
                "positionFin": "POINT (10.0 20.0)",
                "geometry": "LINESTRING (99 99, 99 99)",
                "linearId": IDS["troncon"],
                "typeDesordreId": REFERENCE_IDS["type"],
                "categorieDesordreId": REFERENCE_IDS["categorie"],
                "valid": False,
                "observations": [
                    {
                        "id": IDS["observation"],
                        "designation": "Observation test",
                        "date": "2026-02-03",
                        "evolution": "Stable",
                        "urgenceId": REFERENCE_IDS["urgence"],
                        "valid": False,
                        "photos": [
                            {
                                "id": IDS["photo_1"],
                                "chemin": "commun/photo.jpg",
                                "date": "2026-02-03",
                                "designation": "Photo A",
                                "valid": False,
                            },
                            {
                                "id": IDS["photo_2"],
                                "chemin": "commun/photo.jpg",
                                "date": None,
                                "designation": "Photo B",
                                "valid": True,
                            },
                        ],
                    }
                ],
            }
        ],
    }


class FakeMigrationCursor:
    def __init__(self, counts, *, fail_on_insert=False):
        self.counts = iter(counts)
        self.fail_on_insert = fail_on_insert
        self.inserted_batches = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        pass

    def fetchone(self):
        return (next(self.counts),)

    def executemany(self, query, rows):
        if self.fail_on_insert:
            raise RuntimeError("échec synthétique")
        self.inserted_batches.append((query, rows))


class FakeMigrationConnection:
    def __init__(self, cursor):
        self.cursor_instance = cursor
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, _exc, _traceback):
        self.rolled_back = exc_type is not None
        return False

    def cursor(self):
        return self.cursor_instance


class CoreTransformationTest(unittest.TestCase):
    def test_multivertex_desordre_geometry_is_preserved_before_positions_fallback(self):
        source = "LINESTRING (0 0, 10 4, 20 -2, 30 8, 40 0)"
        wkt, kind, warning = desordre_geometry_from_source(
            source,
            "POINT (0 0)",
            "POINT (40 0)",
            desordre_id="multi-sommets",
        )
        self.assertEqual(wkt, source)
        self.assertEqual(kind, "linestring")
        self.assertIsNone(warning)
        self.assertEqual(wkt.count(",") + 1, 5)

    def test_urgency_uses_the_observed_couchdb_class(self):
        self.assertEqual(
            CORE_SOURCE_CLASSES["RefUrgence"],
            "fr.sirs.core.model.RefUrgence",
        )

    def test_link_insert_lets_postgresql_generate_technical_id(self):
        statement = " ".join(
            INSERT_STATEMENTS["link_desordres_troncons"].split()
        ).lower()
        self.assertIn(
            "insert into public.link_desordres_troncons "
            "(desordre_id, troncon_id)",
            statement,
        )
        self.assertNotIn("(id,", statement)

    def test_migration_insert_statements_explicitly_supply_source_ids(self):
        for table in (
            "ref_categories_desordre",
            "ref_types_desordre",
            "ref_urgences",
            "systemes",
            "digues",
            "troncons",
            "desordres",
            "observations",
            "photos",
        ):
            with self.subTest(table=table):
                columns = " ".join(INSERT_STATEMENTS[table].split()).lower()
                self.assertRegex(columns, rf"insert into public\.{table} \(id,")

    def test_couchdb_id_is_normalized_without_changing_bits(self):
        compact = couchdb_id_to_uuid("001771be560d42069f0e1b185830d2b7")
        canonical = couchdb_id_to_uuid("001771be-560d-4206-9f0e-1b185830d2b7")
        self.assertEqual(compact, canonical)
        self.assertEqual(compact.hex, "001771be560d42069f0e1b185830d2b7")

    def test_troncon_wkt_is_preserved(self):
        wkt = "LINESTRING (1.25 2.5, 3.75 4.0)"
        self.assertIs(validate_troncon_wkt(wkt), wkt)
        with self.assertRaises(CoreMigrationError):
            validate_troncon_wkt("POINT (1 2)")

    def test_equal_positions_create_a_point(self):
        wkt, kind, warning = desordre_geometry_from_positions(
            "POINT(10 20)", "POINT (10.0 20.00)", desordre_id="d1"
        )
        self.assertEqual(wkt, "POINT (10 20)")
        self.assertEqual(kind, "point")
        self.assertIsNone(warning)

    def test_different_positions_create_a_linestring(self):
        wkt, kind, warning = desordre_geometry_from_positions(
            "POINT (10 20)", "POINT (30 40)", desordre_id="d1"
        )
        self.assertEqual(wkt, "LINESTRING (10 20, 30 40)")
        self.assertEqual(kind, "linestring")
        self.assertIsNone(warning)

    def test_missing_positions_create_null_and_warning(self):
        wkt, kind, warning = desordre_geometry_from_positions(
            None, None, desordre_id="d1"
        )
        self.assertIsNone(wkt)
        self.assertEqual(kind, "null")
        self.assertIn("geometry cible NULL", warning)

    def test_valid_source_polygon_is_preserved_for_future_sirs_bases(self):
        polygon = "POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))"
        wkt, kind, warning = desordre_geometry_from_source(
            polygon,
            "POINT (1 1)",
            "POINT (2 2)",
            desordre_id="d1",
        )
        self.assertEqual(wkt, polygon)
        self.assertEqual(kind, "polygon")
        self.assertIsNone(warning)

    def test_invalid_source_polygon_is_not_silently_rebuilt(self):
        wkt, kind, warning = desordre_geometry_from_source(
            "POLYGON ((0 0, 1 0, 0 0, 0 0))",
            "POINT (1 1)",
            "POINT (2 2)",
            desordre_id="d1",
        )
        self.assertIsNone(wkt)
        self.assertEqual(kind, "null")
        self.assertIn("Polygon source invalide", warning)

    def test_flattens_observations_photos_and_links_preserving_invalid_rows(self):
        prepared = prepare_core_migration(source_fixture())
        self.assertEqual(
            prepared.categories_desordre[0].id, REFERENCE_IDS["categorie"]
        )
        self.assertIs(prepared.categories_desordre[0].valid, False)
        self.assertEqual(prepared.types_desordre[0].id, REFERENCE_IDS["type"])
        self.assertEqual(
            prepared.types_desordre[0].categorie_id,
            REFERENCE_IDS["categorie"],
        )
        self.assertEqual(prepared.urgences[0].id, REFERENCE_IDS["urgence"])
        self.assertIs(prepared.urgences[0].valid, False)
        self.assertEqual(
            prepared.desordres[0].type_desordre_id, REFERENCE_IDS["type"]
        )
        self.assertEqual(len(prepared.links), 1)
        self.assertEqual(prepared.links[0].desordre_id, prepared.desordres[0].id)
        self.assertEqual(prepared.links[0].troncon_id, prepared.troncons[0].id)
        self.assertEqual(len(prepared.observations), 2)
        source_observation = next(
            row for row in prepared.observations if not row.synthetic
        )
        self.assertEqual(source_observation.designation, "Observation test")
        self.assertEqual(
            source_observation.desordre_id, prepared.desordres[0].id
        )
        self.assertIs(source_observation.valid, False)
        self.assertEqual(
            source_observation.urgence_id, REFERENCE_IDS["urgence"]
        )
        self.assertEqual(len(prepared.photos), 3)
        self.assertTrue(all(
            photo.observation_id == source_observation.id
            for photo in prepared.photos
            if photo.id.hex != IDS["direct_photo"]
        ))
        self.assertEqual(sum(not photo.valid for photo in prepared.photos), 1)

    def test_missing_observation_designation_becomes_null(self):
        documents = copy.deepcopy(source_fixture())
        del documents["Desordre"][0]["observations"][0]["designation"]
        prepared = prepare_core_migration(documents)
        self.assertIsNone(prepared.observations[0].designation)

    def test_missing_observation_urgency_becomes_null(self):
        documents = copy.deepcopy(source_fixture())
        del documents["Desordre"][0]["observations"][0]["urgenceId"]
        prepared = prepare_core_migration(documents)
        self.assertIsNone(prepared.observations[0].urgence_id)

    def test_migrates_direct_troncon_photos_through_synthetic_observation(self):
        prepared = prepare_core_migration(source_fixture())
        migrated_ids = {photo.id.hex for photo in prepared.photos}
        self.assertIn(IDS["direct_photo"], migrated_ids)
        self.assertEqual(prepared.direct_troncon_photos, 1)
        self.assertEqual(prepared.synthetic_observations, 1)
        synthetic = next(row for row in prepared.observations if row.synthetic)
        self.assertEqual(synthetic.troncon_id, prepared.troncons[0].id)
        self.assertEqual(synthetic.parent_count, 1)
        self.assertIsNone(synthetic.date)
        self.assertTrue(any("date absente" in warning for warning in prepared.warnings))

    def test_does_not_deduplicate_photos_by_path(self):
        prepared = prepare_core_migration(source_fixture())
        source_photos = [
            photo
            for photo in prepared.photos
            if photo.id.hex in {IDS["photo_1"], IDS["photo_2"]}
        ]
        self.assertEqual(len(source_photos), 2)
        self.assertEqual(
            [photo.chemin_source for photo in source_photos],
            ["commun/photo.jpg", "commun/photo.jpg"],
        )

    def test_invalid_degenerate_source_geometry_uses_position_fallback(self):
        prepared = prepare_core_migration(source_fixture())
        self.assertEqual(prepared.desordres[0].geometry_wkt, "POINT (10 20)")
        self.assertNotEqual(
            prepared.desordres[0].geometry_wkt,
            source_fixture()["Desordre"][0]["geometry"],
        )

    def test_target_non_empty_is_refused_before_insert(self):
        prepared = prepare_core_migration(source_fixture())
        cursor = FakeMigrationCursor([1] + [0] * (len(EXPECTED_TABLES) - 1))
        connection = FakeMigrationConnection(cursor)

        with self.assertRaises(TargetNotEmptyError):
            execute_core_migration(
                prepared,
                connector=lambda **_kwargs: connection,
            )
        self.assertEqual(cursor.inserted_batches, [])
        self.assertIs(connection.rolled_back, True)

    def test_target_transaction_rolls_back_on_insert_error(self):
        prepared = prepare_core_migration(source_fixture())
        cursor = FakeMigrationCursor([0] * len(EXPECTED_TABLES), fail_on_insert=True)
        connection = FakeMigrationConnection(cursor)

        with self.assertRaisesRegex(CoreMigrationError, "annulée"):
            execute_core_migration(
                prepared,
                connector=lambda **_kwargs: connection,
            )
        self.assertIs(connection.rolled_back, True)

    def test_all_core_geometry_inserts_use_shared_reprojection_expression(self):
        prepared = prepare_core_migration(source_fixture())
        cursor = FakeMigrationCursor([])
        _insert_prepared_core(cursor, prepared, CRSInfo(source_srid=2154))
        geometry_queries = [
            " ".join(query.split())
            for query, _rows in cursor.inserted_batches
            if "public.troncons" in query or "public.desordres" in query
        ]
        self.assertEqual(len(geometry_queries), 2)
        self.assertTrue(
            all(
                "ST_Transform(ST_GeomFromText(%s, 2154), 3950)" in query
                for query in geometry_queries
            )
        )

    def test_invalid_reference_is_blocking(self):
        documents = copy.deepcopy(source_fixture())
        documents["Desordre"][0]["linearId"] = IDS["photo_2"]
        with self.assertRaisesRegex(CoreMigrationError, "tronçon absent"):
            prepare_core_migration(documents)

    def test_type_without_source_category_is_migrated_without_warning(self):
        documents = copy.deepcopy(source_fixture())
        del documents["Desordre"][0]["categorieDesordreId"]
        prepared = prepare_core_migration(documents)
        self.assertEqual(
            prepared.desordres[0].type_desordre_id, REFERENCE_IDS["type"]
        )
        self.assertFalse(any("categorieDesordreId" in w for w in prepared.warnings))

    def test_source_category_without_type_becomes_null_with_warning(self):
        documents = copy.deepcopy(source_fixture())
        del documents["Desordre"][0]["typeDesordreId"]
        prepared = prepare_core_migration(documents)
        self.assertIsNone(prepared.desordres[0].type_desordre_id)
        self.assertTrue(any("sans typeDesordreId" in w for w in prepared.warnings))

    def test_matching_source_type_and_category_do_not_warn(self):
        prepared = prepare_core_migration(source_fixture())
        self.assertFalse(any("incohérent" in w for w in prepared.warnings))

    def test_mismatching_source_type_and_category_warns_without_changing_type(self):
        documents = copy.deepcopy(source_fixture())
        documents["Desordre"][0]["categorieDesordreId"] = REFERENCE_IDS["categorie_2"]
        prepared = prepare_core_migration(documents)
        self.assertEqual(
            prepared.desordres[0].type_desordre_id, REFERENCE_IDS["type"]
        )
        self.assertTrue(any("incohérent" in w for w in prepared.warnings))

    def test_invalid_type_category_reference_is_blocking(self):
        documents = copy.deepcopy(source_fixture())
        documents["RefTypeDesordre"][0]["categorieId"] = "RefCategorieDesordre:404"
        with self.assertRaisesRegex(CoreMigrationError, "catégorie absente"):
            prepare_core_migration(documents)

    def test_invalid_desordre_type_reference_is_blocking(self):
        documents = copy.deepcopy(source_fixture())
        documents["Desordre"][0]["typeDesordreId"] = "RefTypeDesordre:404"
        with self.assertRaisesRegex(CoreMigrationError, "type absent"):
            prepare_core_migration(documents)

    def test_invalid_observation_urgency_reference_is_blocking(self):
        documents = copy.deepcopy(source_fixture())
        documents["Desordre"][0]["observations"][0]["urgenceId"] = "RefUrgence:404"
        with self.assertRaisesRegex(CoreMigrationError, "urgence absente"):
            prepare_core_migration(documents)


if __name__ == "__main__":
    unittest.main()
