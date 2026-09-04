import copy
import unittest
from uuid import UUID

from digues_app.migration.ouvrages import (
    DEFERRED_SOURCE_COUNTS,
    EXPECTED_BUSINESS_COUNTS,
    OUVRAGE_SOURCE_CLASSES,
    TARGET_REFERENCES,
    OuvragesMigrationError,
    prepare_ouvrages_migration,
    transform_ouvrage_geometry,
)


TRONCON_ID = UUID("00000000-0000-0000-0000-000000000001")


def full_source_fixture():
    counter = 100
    invalid_left = 14

    def document(*, source_type=None, type_field=None, geometry="LINESTRING (1 2, 1 2)"):
        nonlocal counter, invalid_left
        identifier = UUID(int=counter).hex
        counter += 1
        valid = invalid_left <= 0
        invalid_left -= 1
        result = {
            "_id": identifier,
            "designation": f"Objet {counter}",
            "commentaire": "Test",
            "date_debut": "2026-08-30",
            "geometry": geometry,
            "linearId": TRONCON_ID.hex,
            "valid": valid,
        }
        if type_field and source_type is not None:
            result[type_field] = source_type
        return result

    source = {name: [] for name in OUVRAGE_SOURCE_CLASSES}
    op_types = (
        [("RefOuvrageParticulier:9", 30), ("RefOuvrageParticulier:5", 9),
         ("RefOuvrageParticulier:3", 2), ("RefOuvrageParticulier:20", 1),
         ("RefOuvrageParticulier:10", 1), (None, 2)]
    )
    for source_type, count in op_types:
        for _ in range(count):
            source["OuvrageParticulier"].append(
                document(
                    source_type=source_type,
                    type_field="typeOuvrageParticulierId",
                    geometry=(
                        "LINESTRING (1 2, 3 4)"
                        if source_type == "RefOuvrageParticulier:3"
                        else "LINESTRING (1 2, 1 2)"
                    ),
                )
            )

    oha_types = (
        [("RefOuvrageHydrauliqueAssocie:1", 5),
         ("RefOuvrageHydrauliqueAssocie:5", 7),
         ("RefOuvrageHydrauliqueAssocie:6", 2),
         ("RefOuvrageHydrauliqueAssocie:10", 2),
         ("RefOuvrageHydrauliqueAssocie:11", 6),
         ("RefOuvrageHydrauliqueAssocie:3", 3),
         ("RefOuvrageHydrauliqueAssocie:99", 1)]
    )
    for source_type, count in oha_types:
        for index in range(count):
            source["OuvrageHydrauliqueAssocie"].append(
                document(
                    source_type=source_type,
                    type_field="typeOuvrageHydroAssocieId",
                    geometry=(
                        "LINESTRING (1 2, 3 4)"
                        if source_type != "RefOuvrageHydrauliqueAssocie:3" and index == 0
                        else "LINESTRING (1 2, 1.0 2.00)"
                    ),
                )
            )

    for _ in range(6):
        source["OuvrageFranchissement"].append(
            document(
                source_type="RefOuvrageFranchissement:4",
                type_field="typeOuvrageFranchissementId",
                geometry="LINESTRING (1 2, 3 4)",
            )
        )
    for _ in range(6):
        source["EchelleLimnimetrique"].append(document())
    source["StationPompage"].append(document(geometry=None))
    for _ in range(9):
        source["Deversoir"].append(document(geometry="LINESTRING (1 2, 3 4)"))
    source["OuvertureBatardable"].append(document(geometry="LINESTRING (1 2, 3 4)"))
    for index in range(10):
        source["VoieAcces"].append(
            document(geometry=None if index == 0 else "LINESTRING (1 2, 3 4)")
        )
    for _ in range(2):
        source["VoieDigue"].append(
            document(
                source_type="RefVoieDigue:2",
                type_field="typeVoieDigueId",
                geometry="LINESTRING (1 2, 3 4)",
            )
        )
    for _ in range(3):
        source["ReseauTelecomEnergie"].append(
            document(
                source_type="RefReseauTelecomEnergie:1",
                type_field="typeReseauTelecomEnergieId",
            )
            )
    for index in range(8):
        chemin = document(
            geometry=(
                "POLYGON ((0 0, 2 0, 2 2, 0 2, 0 0))"
                if index == 0
                else "LINESTRING (1 2, 3 4)"
            )
        )
        chemin.pop("linearId")
        chemin.update(
            libelle=f"Accès technique {index}",
            largeur=0.0,
            statut=False,
            revetementId="RefRevetement:5" if index == 0 else None,
        )
        source["CheminAccesDependance"].append(chemin)
    for source_class, count in DEFERRED_SOURCE_COUNTS.items():
        for _ in range(count):
            source[source_class].append({"_id": UUID(int=counter).hex, "valid": True})
            counter += 1
    return source


class OuvragesMigrationTest(unittest.TestCase):
    def test_reference_catalogs_use_exact_stable_abbreviations(self):
        self.assertEqual(
            {table: len(rows) for table, rows in TARGET_REFERENCES.items()},
            {
                "ref_types_ouvrage_hydraulique": 17,
                "ref_types_equipement_mesure": 6,
                "ref_types_cheminement": 11,
                "ref_types_mobilier": 8,
                "ref_types_reseau_technique": 9,
            },
        )
        all_ids = {row.id for rows in TARGET_REFERENCES.values() for row in rows}
        self.assertIn("PIE", all_ids)
        self.assertIn("ECH", all_ids)
        self.assertIn("VAN", all_ids)
        self.assertFalse(any(":" in row.id for rows in TARGET_REFERENCES.values() for row in rows))
        for rows in TARGET_REFERENCES.values():
            self.assertTrue(all(row.id == row.abrege for row in rows))
            self.assertEqual(len(rows), len({row.id for row in rows}))
            self.assertEqual(len(rows), len({row.code for row in rows}))

    def test_strict_matrix_explains_all_118_objects(self):
        source = full_source_fixture()
        prepared = prepare_ouvrages_migration(source, troncon_ids={TRONCON_ID})
        self.assertEqual(prepared.migrated_count, 117)
        self.assertEqual(prepared.deferred_count, 1)
        self.assertEqual(prepared.explained_count, 118)
        self.assertEqual(
            {table: len(rows) for table, rows in prepared.rows.items()},
            EXPECTED_BUSINESS_COUNTS,
        )
        self.assertEqual(sum(prepared.invalid_counts.values()), 14)
        self.assertEqual(len(prepared.cheminement_troncon_links), 20)
        self.assertTrue(
            all(
                row.troncon_id == TRONCON_ID
                for table, rows in prepared.rows.items()
                if table != "cheminements"
                for row in rows
            )
        )
        self.assertEqual(
            sum(row.type_cheminement_id == "CAC" for row in prepared.rows["cheminements"]),
            8,
        )

    def test_conservative_type_mapping_is_not_inferred_further(self):
        prepared = prepare_ouvrages_migration(
            full_source_fixture(), troncon_ids={TRONCON_ID}
        )
        em_ind = [row for row in prepared.rows["equipements_mesure"] if row.type_id == "IND"]
        rt_ind = [row for row in prepared.rows["reseaux_techniques"] if row.type_id == "IND"]
        oh_ind = [row for row in prepared.rows["ouvrages_hydrauliques"] if row.type_id == "IND"]
        self.assertEqual(len(em_ind), 2)
        self.assertEqual(len(rt_ind), 1)
        self.assertEqual(len(oh_ind), 1)

    def test_point_conversion_uses_first_real_vertex(self):
        wkt, kind = transform_ouvrage_geometry(
            "LINESTRING (1662769.225 9249907.653, 1662769.226 9249907.654)",
            mode="point",
            context="échelle",
        )
        self.assertEqual(wkt, "POINT (1662769.225 9249907.653)")
        self.assertEqual(kind, "point")

    def test_only_degenerate_generic_lines_become_points(self):
        converted, kind = transform_ouvrage_geometry(
            "LINESTRING (1 2, 1.0 2.00)", mode="degenerate", context="vanne"
        )
        self.assertEqual(converted, "POINT (1 2)")
        self.assertEqual(kind, "point")
        preserved, kind = transform_ouvrage_geometry(
            "LINESTRING (1 2, 3 4)", mode="degenerate", context="vanne"
        )
        self.assertEqual(preserved, "LINESTRING (1 2, 3 4)")
        self.assertEqual(kind, "linestring")

    def test_missing_geometry_stays_null(self):
        self.assertEqual(
            transform_ouvrage_geometry(None, mode="point", context="Pz"),
            (None, "null"),
        )

    def test_unmapped_historical_type_is_blocking(self):
        source = full_source_fixture()
        source["OuvrageParticulier"][0]["typeOuvrageParticulierId"] = "RefOuvrageParticulier:404"
        with self.assertRaisesRegex(OuvragesMigrationError, "Distribution des types"):
            prepare_ouvrages_migration(source, troncon_ids={TRONCON_ID})

    def test_cheminements_preserve_specialized_fields_and_geometry(self):
        source = full_source_fixture()
        prepared = prepare_ouvrages_migration(source, troncon_ids={TRONCON_ID})
        chemins = [
            row
            for row in prepared.rows["cheminements"]
            if row.type_cheminement_id == "CAC"
        ]
        self.assertEqual(len(chemins), 8)
        polygon = next(row for row in chemins if row.geometry_kind == "polygon")
        self.assertEqual(polygon.libelle, "Accès technique 0")
        self.assertEqual(polygon.largeur, 0.0)
        self.assertFalse(polygon.statut_source)
        self.assertEqual(polygon.revetement_source_id, "RefRevetement:5")
        self.assertFalse(
            any(
                link.cheminement_id in {row.id for row in chemins}
                for link in prepared.cheminement_troncon_links
            )
        )
        expected_ids = {
            UUID(str(document["_id"]))
            for source_class in (
                "OuvrageFranchissement",
                "OuvrageParticulier",
                "VoieDigue",
                "VoieAcces",
                "CheminAccesDependance",
            )
            for document in source[source_class]
            if (
                source_class != "OuvrageParticulier"
                or document.get("typeOuvrageParticulierId")
                == "RefOuvrageParticulier:3"
            )
        }
        self.assertEqual({row.id for row in prepared.rows["cheminements"]}, expected_ids)

    def test_explicit_desordre_link_is_preserved_without_inference(self):
        source = full_source_fixture()
        desordre_id = UUID(int=999)
        source["OuvrageFranchissement"][0]["desordreIds"] = [desordre_id.hex]
        prepared = prepare_ouvrages_migration(
            source,
            troncon_ids={TRONCON_ID},
            desordre_ids={desordre_id},
        )
        self.assertEqual(len(prepared.cheminement_desordre_links), 1)
        self.assertEqual(
            prepared.cheminement_desordre_links[0].desordre_id,
            desordre_id,
        )

    def test_broken_explicit_desordre_link_is_blocking(self):
        source = full_source_fixture()
        source["OuvrageFranchissement"][0]["desordreIds"] = [UUID(int=999).hex]
        with self.assertRaisesRegex(OuvragesMigrationError, "désordre absent"):
            prepare_ouvrages_migration(
                source,
                troncon_ids={TRONCON_ID},
                desordre_ids=set(),
            )

    def test_broken_troncon_is_blocking(self):
        source = copy.deepcopy(full_source_fixture())
        source["Deversoir"][0]["linearId"] = UUID(int=999).hex
        with self.assertRaisesRegex(OuvragesMigrationError, "tronçon absent"):
            prepare_ouvrages_migration(source, troncon_ids={TRONCON_ID})

    def test_borne_digue_is_outside_source_scope(self):
        self.assertNotIn("BorneDigue", OUVRAGE_SOURCE_CLASSES)


if __name__ == "__main__":
    unittest.main()
