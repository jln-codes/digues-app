import copy
import unittest

from sirs_postgre.migration.core import (
    CoreMigrationError,
    TargetNotEmptyError,
    couchdb_id_to_uuid,
    desordre_geometry_from_positions,
    execute_core_migration,
    prepare_core_migration,
    validate_troncon_wkt,
)


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


def source_fixture():
    return {
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
                "valid": False,
                "observations": [
                    {
                        "id": IDS["observation"],
                        "date": "2026-02-03",
                        "evolution": "Stable",
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

    def test_flattens_observations_photos_and_links_preserving_invalid_rows(self):
        prepared = prepare_core_migration(source_fixture())
        self.assertEqual(len(prepared.links), 1)
        self.assertEqual(prepared.links[0].desordre_id, prepared.desordres[0].id)
        self.assertEqual(prepared.links[0].troncon_id, prepared.troncons[0].id)
        self.assertEqual(len(prepared.observations), 1)
        self.assertEqual(
            prepared.observations[0].desordre_id, prepared.desordres[0].id
        )
        self.assertIs(prepared.observations[0].valid, False)
        self.assertEqual(len(prepared.photos), 2)
        self.assertTrue(all(
            photo.observation_id == prepared.observations[0].id
            for photo in prepared.photos
        ))
        self.assertEqual(sum(not photo.valid for photo in prepared.photos), 1)

    def test_ignores_direct_troncon_photos(self):
        prepared = prepare_core_migration(source_fixture())
        migrated_ids = {photo.id.hex for photo in prepared.photos}
        self.assertNotIn(IDS["direct_photo"], migrated_ids)
        self.assertEqual(prepared.ignored_direct_troncon_photos, 1)

    def test_does_not_deduplicate_photos_by_path(self):
        prepared = prepare_core_migration(source_fixture())
        self.assertEqual(len(prepared.photos), 2)
        self.assertEqual(
            [photo.chemin_source for photo in prepared.photos],
            ["commun/photo.jpg", "commun/photo.jpg"],
        )

    def test_desordre_source_geometry_is_not_used(self):
        prepared = prepare_core_migration(source_fixture())
        self.assertEqual(prepared.desordres[0].geometry_wkt, "POINT (10 20)")
        self.assertNotEqual(
            prepared.desordres[0].geometry_wkt,
            source_fixture()["Desordre"][0]["geometry"],
        )

    def test_target_non_empty_is_refused_before_insert(self):
        prepared = prepare_core_migration(source_fixture())
        cursor = FakeMigrationCursor([1, 0, 0, 0, 0, 0, 0])
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
        cursor = FakeMigrationCursor([0] * 7, fail_on_insert=True)
        connection = FakeMigrationConnection(cursor)

        with self.assertRaisesRegex(CoreMigrationError, "annulée"):
            execute_core_migration(
                prepared,
                connector=lambda **_kwargs: connection,
            )
        self.assertIs(connection.rolled_back, True)

    def test_invalid_reference_is_blocking(self):
        documents = copy.deepcopy(source_fixture())
        documents["Desordre"][0]["linearId"] = IDS["photo_2"]
        with self.assertRaisesRegex(CoreMigrationError, "tronçon absent"):
            prepare_core_migration(documents)


if __name__ == "__main__":
    unittest.main()
