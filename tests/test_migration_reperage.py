import unittest
from decimal import Decimal
from uuid import UUID

from digues_app.migration.crs import CRSInfo
from digues_app.migration.reperage import (
    ReperageMigrationError,
    insert_prepared_reperage,
    prepare_reperage_migration,
)
from digues_app.migration.validation import INTEGRITY_CHECKS


TRONCON_ID = "00000000-0000-0000-0000-000000000001"
OTHER_TRONCON_ID = "00000000-0000-0000-0000-000000000002"
SYSTEME_ID = "10000000-0000-0000-0000-000000000001"
SECOND_SYSTEME_ID = "10000000-0000-0000-0000-000000000002"
BORNE_IDS = tuple(
    f"20000000-0000-0000-0000-00000000000{index}" for index in range(1, 4)
)
ASSOCIATION_IDS = tuple(
    f"30000000-0000-0000-0000-00000000000{index}" for index in range(1, 5)
)


def source_documents():
    bornes = [
        {
            "_id": borne_id,
            "libelle": f"B{index}",
            "commentaire": None,
            "geometry": f"POINT ({index}.5 {index + 1}.25)",
            "fictive": index == 3,
            "date_debut": "2020-01-02",
            "date_fin": None,
            "valid": index != 2,
        }
        for index, borne_id in enumerate(BORNE_IDS, start=1)
    ]
    associations = [
        {
            "id": ASSOCIATION_IDS[index],
            "borneId": borne_id,
            "valeurPR": value,
            "valid": index != 1,
        }
        for index, (borne_id, value) in enumerate(
            zip(BORNE_IDS, ("123.4500", -7.25, "9876543210.123456789"))
        )
    ]
    return {
        "TronconDigue": [
            {
                "_id": TRONCON_ID,
                "borneIds": list(BORNE_IDS),
                "systemeRepDefautId": SYSTEME_ID,
            }
        ],
        "SystemeReperage": [
            {
                "_id": SYSTEME_ID,
                "linearId": TRONCON_ID,
                "libelle": "Élémentaire",
                "commentaire": "source",
                "valid": False,
                "systemeReperageBornes": associations,
            },
            {
                "_id": SECOND_SYSTEME_ID,
                "linearId": TRONCON_ID,
                "libelle": "Secondaire",
                "valid": True,
                "systemeReperageBornes": [
                    {
                        "id": ASSOCIATION_IDS[3],
                        "borneId": BORNE_IDS[0],
                        "valeurPR": "42.000",
                        "valid": True,
                    }
                ],
            },
        ],
        "BorneDigue": bornes,
    }


class RecordingCursor:
    def __init__(self):
        self.batches = []

    def executemany(self, statement, rows):
        self.batches.append((" ".join(statement.split()), list(rows)))


class ReperageMigrationTest(unittest.TestCase):
    def test_positive_target_validation_covers_reperage_integrity(self):
        queries = " ".join(" ".join(query.split()) for query in INTEGRITY_CHECKS.values())
        for table in (
            "systemes_reperage",
            "bornes_reperage",
            "link_troncons_bornes",
            "link_systemes_reperage_bornes",
        ):
            self.assertIn(table, queries)
        self.assertIn("systeme_reperage_defaut_id", queries)
        self.assertIn("s.troncon_id <> t.id", queries)
        self.assertIn("ST_SRID(geometry) <> 3950", queries)
        self.assertNotIn("exactement deux", queries.lower())

    def test_preserves_historical_ids_pr_valid_and_explicit_relations(self):
        prepared = prepare_reperage_migration(
            source_documents(),
            troncon_ids={UUID(TRONCON_ID)},
        )
        self.assertEqual(prepared.expected_counts["systemes_reperage"], 2)
        self.assertEqual(prepared.expected_counts["bornes_reperage"], 3)
        self.assertEqual(prepared.expected_counts["link_troncons_bornes"], 3)
        self.assertEqual(
            prepared.expected_counts["link_systemes_reperage_bornes"], 4
        )
        self.assertEqual(prepared.default_system_count, 1)
        self.assertEqual(prepared.systemes[0].id, UUID(SYSTEME_ID))
        self.assertFalse(prepared.systemes[0].valid)
        self.assertFalse(prepared.bornes[1].valid)
        self.assertEqual(
            prepared.valeur_pr_by_id[UUID(ASSOCIATION_IDS[0])],
            Decimal("123.4500"),
        )
        self.assertEqual(
            prepared.valeur_pr_by_id[UUID(ASSOCIATION_IDS[2])],
            Decimal("9876543210.123456789"),
        )
        self.assertEqual(prepared.inconsistencies, ())

    def test_does_not_invent_troncon_borne_relation_from_system(self):
        documents = source_documents()
        documents["TronconDigue"][0]["borneIds"] = list(BORNE_IDS[:2])
        prepared = prepare_reperage_migration(
            documents,
            troncon_ids={UUID(TRONCON_ID)},
        )
        pairs = {(row.troncon_id, row.borne_id) for row in prepared.troncons_bornes}
        self.assertNotIn((UUID(TRONCON_ID), UUID(BORNE_IDS[2])), pairs)
        self.assertEqual(len(prepared.inconsistencies), 1)
        self.assertIn("sans correction", prepared.warnings[0])

    def test_rejects_missing_system_troncon_and_wrong_default_owner(self):
        documents = source_documents()
        documents["SystemeReperage"][0]["linearId"] = OTHER_TRONCON_ID
        with self.assertRaisesRegex(ReperageMigrationError, "tronçon absent"):
            prepare_reperage_migration(
                documents,
                troncon_ids={UUID(TRONCON_ID)},
            )

        documents = source_documents()
        documents["TronconDigue"].append(
            {"_id": OTHER_TRONCON_ID, "borneIds": []}
        )
        documents["SystemeReperage"][0]["linearId"] = OTHER_TRONCON_ID
        with self.assertRaisesRegex(ReperageMigrationError, "autre tronçon"):
            prepare_reperage_migration(
                documents,
                troncon_ids={UUID(TRONCON_ID), UUID(OTHER_TRONCON_ID)},
            )

    def test_rejects_missing_borne_without_spatial_fallback(self):
        documents = source_documents()
        documents["BorneDigue"].pop()
        with self.assertRaisesRegex(ReperageMigrationError, "borne absente"):
            prepare_reperage_migration(
                documents,
                troncon_ids={UUID(TRONCON_ID)},
            )

    def test_insert_uses_shared_crs_pipeline_and_updates_default_last(self):
        prepared = prepare_reperage_migration(
            source_documents(),
            troncon_ids={UUID(TRONCON_ID)},
        )
        cursor = RecordingCursor()
        insert_prepared_reperage(
            cursor,
            prepared,
            crs_info=CRSInfo(source_srid=2154),
        )
        statements = [statement for statement, _rows in cursor.batches]
        self.assertIn(
            "ST_Transform(ST_GeomFromText(%s, 2154), 3950)", statements[1]
        )
        self.assertIn("UPDATE public.troncons", statements[-1])
        self.assertEqual(
            cursor.batches[-1][1],
            [(UUID(SYSTEME_ID), UUID(TRONCON_ID))],
        )


if __name__ == "__main__":
    unittest.main()
