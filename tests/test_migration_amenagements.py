import unittest
from uuid import UUID

from digues_app.migration.amenagements import (
    TARGET_REFERENCES,
    AmenagementsMigrationError,
    attach_associated_ouvrages,
    prepare_amenagements_migration,
)
from digues_app.migration.ouvrages import prepare_ouvrages_migration
from digues_app.migration.source_overrides import SourceMigrationOverrides


AMENAGEMENT_ID = "00000000-0000-0000-0000-000000000010"
TRONCON_ID = UUID("00000000-0000-0000-0000-000000000020")
ASSOCIATED_ID = "00000000-0000-0000-0000-000000000030"
POLYGON = "POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))"


def amenagement_document(**updates):
    document = {
        "_id": AMENAGEMENT_ID,
        "designation": "Nom libre sans portée de mapping",
        "date_debut": "2026-08-30",
        "geometry": POLYGON,
        "valid": True,
    }
    document.update(updates)
    return document


def source_fixture(*amenagements, **extra):
    source = {
        "AmenagementHydraulique": list(amenagements),
        "OuvrageAssocieAmenagementHydraulique": [],
        "CheminAccesDependance": [],
        "PrestationAmenagementHydraulique": [],
        "TraitAmenagementHydraulique": [],
        "DesordreDependance": [],
    }
    source.update(extra)
    return source


class AmenagementsMigrationTest(unittest.TestCase):
    def test_target_reference_contains_zec_and_ind(self):
        self.assertEqual(
            [(row.id, row.code, row.abrege, row.libelle) for row in TARGET_REFERENCES],
            [
                ("ZEC", "zec", "ZEC", "Zone d'expansion des crues"),
                ("IND", "indefini", "IND", "Indéfini"),
            ],
        )

    def test_known_source_type_uses_explicit_mapping(self):
        source = source_fixture(
            amenagement_document(typeId="RefTypeAmenagementHydraulique:42")
        )
        prepared = prepare_amenagements_migration(
            source,
            troncon_ids=set(),
            source_database="autre_base",
            source_type_mapping={"RefTypeAmenagementHydraulique:42": "ZEC"},
        )
        self.assertEqual(prepared.amenagements[0].type_id, "ZEC")
        self.assertEqual(prepared.warnings, ())

    def test_missing_source_type_is_preserved_as_ind_with_warning(self):
        prepared = prepare_amenagements_migration(
            source_fixture(amenagement_document()),
            troncon_ids=set(),
            source_database="autre_base",
        )
        self.assertEqual(prepared.amenagements[0].type_id, "IND")
        self.assertTrue(any("type source absent" in warning for warning in prepared.warnings))

    def test_unknown_source_type_is_preserved_as_ind_with_warning(self):
        source = source_fixture(
            amenagement_document(typeId="RefTypeAmenagementHydraulique:404")
        )
        prepared = prepare_amenagements_migration(
            source, troncon_ids=set(), source_database="autre_base"
        )
        self.assertEqual(prepared.amenagements[0].type_id, "IND")
        self.assertTrue(any("type source inconnu" in warning for warning in prepared.warnings))

    def test_only_explicit_troncon_ids_create_links(self):
        explicit = prepare_amenagements_migration(
            source_fixture(amenagement_document(tronconIds=[TRONCON_ID.hex])),
            troncon_ids={TRONCON_ID},
            source_database="autre_base",
        )
        self.assertEqual(len(explicit.links), 1)
        self.assertEqual(explicit.links[0].troncon_id, TRONCON_ID)

        spatial_only = prepare_amenagements_migration(
            source_fixture(amenagement_document()),
            troncon_ids={TRONCON_ID},
            source_database="autre_base",
        )
        self.assertEqual(spatial_only.links, ())

    def test_non_polygon_geometry_is_blocking(self):
        source = source_fixture(
            amenagement_document(geometry="LINESTRING (0 0, 10 10)")
        )
        with self.assertRaisesRegex(AmenagementsMigrationError, "POLYGON"):
            prepare_amenagements_migration(
                source, troncon_ids=set(), source_database="autre_base"
            )

    def test_unconfigured_uuid_and_name_have_no_effect(self):
        current_id = UUID(int=101).hex
        source = source_fixture(
            amenagement_document(_id=current_id, designation="Fixture synthétique")
        )
        prepared = prepare_amenagements_migration(
            source, troncon_ids=set(), source_database="copie_externe"
        )
        self.assertEqual(prepared.amenagements[0].type_id, "IND")
        self.assertTrue(any("type source absent" in warning for warning in prepared.warnings))

    def test_explicit_override_is_applied_by_identifier(self):
        current_id = UUID(int=102).hex
        source = source_fixture(amenagement_document(_id=current_id))
        prepared = prepare_amenagements_migration(
            source,
            troncon_ids=set(),
            source_database="synthetic_source",
            overrides=SourceMigrationOverrides(
                amenagement_type_by_id={current_id: "ZEC"}
            ),
        )
        self.assertEqual(prepared.amenagements[0].type_id, "ZEC")
        self.assertTrue(any("override spécifique" in warning for warning in prepared.warnings))

    def test_associated_ouvrage_uses_explicit_parent_and_dvs_type(self):
        associated = {
            "_id": ASSOCIATED_ID,
            "amenagementHydrauliqueId": AMENAGEMENT_ID,
            "typeId": "RefOuvrageAssocieAH:3",
            "geometry": "LINESTRING (1 1, 2 2)",
            "date_debut": "2026-08-30",
            "valid": True,
        }
        source = source_fixture(
            amenagement_document(),
            OuvrageAssocieAmenagementHydraulique=[associated],
        )
        prepared = prepare_amenagements_migration(
            source, troncon_ids=set(), source_database="autre_base"
        )
        self.assertEqual(len(prepared.associated_ouvrages), 1)
        row = prepared.associated_ouvrages[0]
        self.assertEqual(row.type_id, "DVS")
        self.assertEqual(row.amenagement_hydraulique_id, UUID(AMENAGEMENT_ID))

        ouvrage_source = {
            "OuvrageAssocieAmenagementHydraulique": [associated],
            "CheminAccesDependance": [],
        }
        ouvrages = prepare_ouvrages_migration(
            ouvrage_source, troncon_ids=set(), strict_counts=False
        )
        combined = attach_associated_ouvrages(ouvrages, prepared)
        self.assertEqual(len(combined.rows["ouvrages_hydrauliques"]), 1)
        self.assertEqual(
            combined.deferred_counts["OuvrageAssocieAmenagementHydraulique"], 0
        )

    def test_broken_associated_parent_is_blocking(self):
        associated = {
            "_id": ASSOCIATED_ID,
            "amenagementHydrauliqueId": UUID(int=999).hex,
            "typeId": "RefOuvrageAssocieAH:3",
            "geometry": "LINESTRING (1 1, 2 2)",
            "valid": True,
        }
        source = source_fixture(
            amenagement_document(),
            OuvrageAssocieAmenagementHydraulique=[associated],
        )
        with self.assertRaisesRegex(AmenagementsMigrationError, "parent absent"):
            prepare_amenagements_migration(
                source, troncon_ids=set(), source_database="autre_base"
            )

    def test_unknown_associated_type_is_not_lost(self):
        associated = {
            "_id": ASSOCIATED_ID,
            "amenagementHydrauliqueId": AMENAGEMENT_ID,
            "typeId": "RefOuvrageAssocieAH:404",
            "geometry": None,
            "valid": True,
        }
        prepared = prepare_amenagements_migration(
            source_fixture(
                amenagement_document(),
                OuvrageAssocieAmenagementHydraulique=[associated],
            ),
            troncon_ids=set(),
            source_database="autre_base",
        )
        self.assertEqual(prepared.associated_ouvrages[0].type_id, "IND")
        self.assertTrue(any("ouvrage type_id=IND" in warning for warning in prepared.warnings))

    def test_only_prestations_remain_deferred_from_amenagements(self):
        source = source_fixture(
            amenagement_document(),
            CheminAccesDependance=[{"_id": UUID(int=index).hex} for index in range(1, 9)],
            PrestationAmenagementHydraulique=[{"_id": UUID(int=50).hex}],
        )
        prepared = prepare_amenagements_migration(
            source, troncon_ids=set(), source_database="autre_base"
        )
        self.assertEqual(prepared.deferred_chemins, 0)
        self.assertEqual(prepared.deferred_prestations, 1)
        self.assertEqual(len(prepared.amenagements), 1)

    def test_contradictory_source_type_fields_are_blocking(self):
        source = source_fixture(
            amenagement_document(
                typeId="RefTypeAmenagementHydraulique:1",
                typeAmenagementHydrauliqueId="RefTypeAmenagementHydraulique:2",
            )
        )
        with self.assertRaisesRegex(AmenagementsMigrationError, "contradictoires"):
            prepare_amenagements_migration(
                source, troncon_ids=set(), source_database="autre_base"
            )


if __name__ == "__main__":
    unittest.main()
