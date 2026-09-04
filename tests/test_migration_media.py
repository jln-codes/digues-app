import unittest
from uuid import UUID

from digues_app.migration.media import (
    OWNER_FIELDS,
    ObservationRow,
    OwnerBinding,
    prepare_media_migration,
)


class MediaMigrationTest(unittest.TestCase):
    def test_every_supported_parent_can_own_an_observation(self):
        for index, owner_field in enumerate(OWNER_FIELDS, start=1):
            owner_id = UUID(int=index)
            source_class = f"Source{index}"
            observation_id = UUID(int=100 + index)
            prepared = prepare_media_migration(
                {
                    source_class: [
                        {
                            "_id": owner_id.hex,
                            "observations": [
                                {
                                    "id": observation_id.hex,
                                    "date": "2026-08-30",
                                    "valid": True,
                                    "photos": [],
                                }
                            ],
                        }
                    ]
                },
                owner_bindings={
                    (source_class, owner_id): OwnerBinding(owner_field, owner_id)
                },
                urgence_ids=set(),
            )
            row = prepared.observations[0]
            self.assertEqual(row.parent_count, 1)
            self.assertEqual(getattr(row, owner_field), owner_id)

    def test_direct_photos_same_owner_and_date_share_one_synthetic_observation(self):
        owner_id = UUID(int=1)
        prepared = prepare_media_migration(
            {
                "TronconDigue": [
                    {
                        "_id": owner_id.hex,
                        "photos": [
                            {
                                "id": UUID(int=2).hex,
                                "chemin": "a.jpg",
                                "date": "2026-08-30",
                                "valid": True,
                            },
                            {
                                "id": UUID(int=3).hex,
                                "chemin": "a.jpg",
                                "date": "2026-08-30",
                                "valid": False,
                            },
                        ],
                    }
                ]
            },
            owner_bindings={
                ("TronconDigue", owner_id): OwnerBinding("troncon_id", owner_id)
            },
            urgence_ids=set(),
        )
        self.assertEqual(len(prepared.observations), 1)
        self.assertEqual(len(prepared.photos), 2)
        self.assertEqual({photo.observation_id for photo in prepared.photos}, {prepared.observations[0].id})
        self.assertEqual(len({photo.id for photo in prepared.photos}), 2)
        self.assertEqual(prepared.direct_troncon_photos, 2)

    def test_missing_direct_photo_date_stays_null_and_warns_once(self):
        owner_id = UUID(int=1)
        prepared = prepare_media_migration(
            {
                "ArbreVegetation": [
                    {
                        "_id": owner_id.hex,
                        "photos": [
                            {
                                "id": UUID(int=2).hex,
                                "chemin": "sans-date.jpg",
                                "valid": True,
                            }
                        ],
                    }
                ]
            },
            owner_bindings={
                ("ArbreVegetation", owner_id): OwnerBinding("vegetation_id", owner_id)
            },
            urgence_ids=set(),
        )
        self.assertIsNone(prepared.observations[0].date)
        self.assertIsNone(prepared.photos[0].date)
        self.assertEqual(len(prepared.warnings), 1)
        self.assertIn("date absente", prepared.warnings[0])

    def test_direct_technical_access_photo_becomes_cheminement_media(self):
        cheminement_id = UUID(int=20)
        photo_id = UUID(int=21)
        prepared = prepare_media_migration(
            {
                "CheminAccesDependance": [
                    {
                        "_id": cheminement_id.hex,
                        "photos": [
                            {
                                "id": photo_id.hex,
                                "chemin": "chemin-technique.jpg",
                                "date": "2026-08-30",
                                "valid": True,
                            }
                        ],
                    }
                ]
            },
            owner_bindings={
                ("CheminAccesDependance", cheminement_id): OwnerBinding(
                    "cheminement_id", cheminement_id
                )
            },
            urgence_ids=set(),
        )
        self.assertEqual(len(prepared.observations), 1)
        self.assertTrue(prepared.observations[0].synthetic)
        self.assertEqual(prepared.observations[0].cheminement_id, cheminement_id)
        self.assertEqual(prepared.photos[0].id, photo_id)
        self.assertEqual(prepared.photos[0].observation_id, prepared.observations[0].id)
        self.assertEqual(prepared.direct_other_photos, 1)

    def test_duplicate_photo_uuid_is_refused(self):
        owner_id = UUID(int=1)
        photo = {
            "id": UUID(int=2).hex,
            "chemin": "photo.jpg",
            "date": "2026-08-30",
            "valid": True,
        }
        with self.assertRaisesRegex(RuntimeError, "photo dupliqués"):
            prepare_media_migration(
                {"TronconDigue": [{"_id": owner_id.hex, "photos": [photo, photo]}]},
                owner_bindings={
                    ("TronconDigue", owner_id): OwnerBinding("troncon_id", owner_id)
                },
                urgence_ids=set(),
            )

    def test_row_with_zero_or_two_parents_is_detectable(self):
        self.assertEqual(ObservationRow(id=UUID(int=1)).parent_count, 0)
        self.assertEqual(
            ObservationRow(
                id=UUID(int=1),
                desordre_id=UUID(int=2),
                vegetation_id=UUID(int=3),
            ).parent_count,
            2,
        )


if __name__ == "__main__":
    unittest.main()
