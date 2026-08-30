import re
import unittest

from sirs_postgre.target.database import PostgreSQLConfig, initialize_schema
from sirs_postgre.target.schema import EXPECTED_TABLES, SCHEMA_DDL, TABLE_DEFINITIONS


def normalized(statement):
    return " ".join(statement.split()).lower()


class FakeSchemaCursor:
    def __init__(self):
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        self.executed.append((str(query), params))

    def fetchone(self):
        return ("3.4.2", "1.3")

    def fetchall(self):
        return [(table,) for table in EXPECTED_TABLES]


class FakeSchemaConnection:
    def __init__(self):
        self.cursor_instance = FakeSchemaCursor()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.cursor_instance


class TargetSchemaTest(unittest.TestCase):
    def test_defines_exactly_the_requested_tables(self):
        self.assertEqual(
            EXPECTED_TABLES,
            (
                "systemes",
                "digues",
                "troncons",
                "ref_categories_desordre",
                "ref_types_desordre",
                "ref_urgences",
                "ref_types_ouvrage_hydraulique",
                "ref_types_equipement_mesure",
                "ref_types_ouvrage_franchissement",
                "ref_types_mobilier",
                "ref_types_reseau_technique",
                "ref_types_amenagement_hydraulique",
                "ref_natures_vegetation",
                "ref_etats_sanitaires_vegetation",
                "ref_classes_hauteur_vegetation",
                "ref_classes_diametre_vegetation",
                "desordres",
                "link_desordres_troncons",
                "amenagements_hydrauliques",
                "link_amenagements_troncons",
                "plans_gestion_vegetation",
                "parcelles_gestion_vegetation",
                "link_parcelles_gestion_troncons",
                "vegetation",
                "ouvrages_hydrauliques",
                "equipements_mesure",
                "ouvrages_franchissement",
                "mobilier",
                "reseaux_techniques",
                "observations",
                "photos",
            ),
        )
        created = [
            match
            for statement in SCHEMA_DDL
            for match in re.findall(
                r"create table if not exists public\.([a-z_]+)",
                normalized(statement),
            )
        ]
        self.assertEqual(created, list(EXPECTED_TABLES))
        self.assertTrue(
            set(created).isdisjoint(
                {
                    "systeme_endiguement",
                    "digue",
                    "troncon",
                    "desordre",
                    "link_desordre_troncon",
                    "observation",
                    "photo",
                }
            )
        )

    def test_business_identifiers_are_uuid_without_serial_types(self):
        for table in (
            "systemes",
            "digues",
            "troncons",
            "desordres",
            "link_desordres_troncons",
            "observations",
            "photos",
            "amenagements_hydrauliques",
            "link_amenagements_troncons",
            "plans_gestion_vegetation",
            "parcelles_gestion_vegetation",
            "link_parcelles_gestion_troncons",
            "vegetation",
            "ouvrages_hydrauliques",
            "equipements_mesure",
            "ouvrages_franchissement",
            "mobilier",
            "reseaux_techniques",
        ):
            with self.subTest(table=table):
                self.assertIn("id uuid primary key", normalized(TABLE_DEFINITIONS[table]))
        ddl = normalized(" ".join(SCHEMA_DDL))
        self.assertNotIn("serial", ddl)

    def test_simple_uuid_primary_keys_default_to_generated_uuid(self):
        for table in (
            "systemes",
            "digues",
            "troncons",
            "desordres",
            "link_desordres_troncons",
            "observations",
            "photos",
            "amenagements_hydrauliques",
            "link_amenagements_troncons",
            "plans_gestion_vegetation",
            "parcelles_gestion_vegetation",
            "link_parcelles_gestion_troncons",
            "vegetation",
            "ouvrages_hydrauliques",
            "equipements_mesure",
            "ouvrages_franchissement",
            "mobilier",
            "reseaux_techniques",
        ):
            with self.subTest(table=table):
                self.assertIn(
                    "id uuid primary key default gen_random_uuid()",
                    normalized(TABLE_DEFINITIONS[table]),
                )

    def test_foreign_key_columns_are_uuid(self):
        expected_uuid_columns = {
            "digues": ("systeme_endiguement_id",),
            "troncons": ("digue_id",),
            "link_desordres_troncons": ("desordre_id", "troncon_id"),
            "observations": (
                "desordre_id",
                "troncon_id",
                "ouvrage_hydraulique_id",
                "equipement_mesure_id",
                "ouvrage_franchissement_id",
                "mobilier_id",
                "reseau_technique_id",
                "amenagement_hydraulique_id",
                "vegetation_id",
            ),
            "photos": ("observation_id",),
            "link_amenagements_troncons": (
                "amenagement_hydraulique_id",
                "troncon_id",
            ),
            "parcelles_gestion_vegetation": ("plan_id",),
            "link_parcelles_gestion_troncons": (
                "parcelle_gestion_id",
                "troncon_id",
            ),
            "vegetation": ("parcelle_gestion_id",),
            "ouvrages_hydrauliques": (
                "troncon_id",
                "amenagement_hydraulique_id",
            ),
            "equipements_mesure": ("troncon_id",),
            "ouvrages_franchissement": ("troncon_id",),
            "mobilier": ("troncon_id",),
            "reseaux_techniques": ("troncon_id",),
        }
        for table, columns in expected_uuid_columns.items():
            statement = normalized(TABLE_DEFINITIONS[table])
            for column in columns:
                with self.subTest(table=table, column=column):
                    self.assertIn(f"{column} uuid", statement)

    def test_reference_primary_and_foreign_keys_are_text(self):
        for table in (
            "ref_categories_desordre",
            "ref_types_desordre",
            "ref_urgences",
            "ref_types_ouvrage_hydraulique",
            "ref_types_equipement_mesure",
            "ref_types_ouvrage_franchissement",
            "ref_types_mobilier",
            "ref_types_reseau_technique",
            "ref_types_amenagement_hydraulique",
            "ref_natures_vegetation",
            "ref_etats_sanitaires_vegetation",
            "ref_classes_hauteur_vegetation",
            "ref_classes_diametre_vegetation",
        ):
            with self.subTest(table=table):
                self.assertIn("id text primary key", normalized(TABLE_DEFINITIONS[table]))
                self.assertNotIn("gen_random_uuid", normalized(TABLE_DEFINITIONS[table]))
        self.assertIn(
            "categorie_id text not null",
            normalized(TABLE_DEFINITIONS["ref_types_desordre"]),
        )
        self.assertIn(
            "type_desordre_id text null",
            normalized(TABLE_DEFINITIONS["desordres"]),
        )
        self.assertIn(
            "urgence_id text null",
            normalized(TABLE_DEFINITIONS["observations"]),
        )
        for table in (
            "ref_types_ouvrage_hydraulique",
            "ref_types_equipement_mesure",
            "ref_types_ouvrage_franchissement",
            "ref_types_mobilier",
            "ref_types_reseau_technique",
            "ref_types_amenagement_hydraulique",
            "ref_natures_vegetation",
            "ref_etats_sanitaires_vegetation",
            "ref_classes_hauteur_vegetation",
            "ref_classes_diametre_vegetation",
        ):
            statement = normalized(TABLE_DEFINITIONS[table])
            self.assertIn("code text not null unique", statement)
            self.assertIn("abrege text not null unique", statement)

    def test_foreign_keys_follow_the_requested_relationships(self):
        expected_references = {
            "ref_types_desordre": (
                "foreign key (categorie_id) "
                "references public.ref_categories_desordre (id)"
            ),
            "digues": (
                "foreign key (systeme_endiguement_id) "
                "references public.systemes (id)"
            ),
            "troncons": "foreign key (digue_id) references public.digues (id)",
            "link_desordres_troncons": (
                "foreign key (desordre_id) references public.desordres (id)",
                "foreign key (troncon_id) references public.troncons (id)",
            ),
            "observations": (
                "foreign key (desordre_id) references public.desordres (id)",
                "foreign key (troncon_id) references public.troncons (id)",
                "foreign key (ouvrage_hydraulique_id) references public.ouvrages_hydrauliques (id)",
                "foreign key (equipement_mesure_id) references public.equipements_mesure (id)",
                "foreign key (ouvrage_franchissement_id) references public.ouvrages_franchissement (id)",
                "foreign key (mobilier_id) references public.mobilier (id)",
                "foreign key (reseau_technique_id) references public.reseaux_techniques (id)",
                "foreign key (amenagement_hydraulique_id) references public.amenagements_hydrauliques (id)",
                "foreign key (vegetation_id) references public.vegetation (id)",
                "foreign key (urgence_id) references public.ref_urgences (id)",
            ),
            "desordres": (
                "foreign key (type_desordre_id) "
                "references public.ref_types_desordre (id)"
            ),
            "photos": (
                "foreign key (observation_id) references public.observations (id)"
            ),
            "ouvrages_hydrauliques": (
                "foreign key (type_id) references public.ref_types_ouvrage_hydraulique (id)",
                "foreign key (troncon_id) references public.troncons (id)",
                "foreign key (amenagement_hydraulique_id) references public.amenagements_hydrauliques (id)",
            ),
            "amenagements_hydrauliques": (
                "foreign key (type_id) references public.ref_types_amenagement_hydraulique (id)"
            ),
            "link_amenagements_troncons": (
                "foreign key (amenagement_hydraulique_id) references public.amenagements_hydrauliques (id)",
                "foreign key (troncon_id) references public.troncons (id)",
            ),
            "parcelles_gestion_vegetation": (
                "foreign key (plan_id) references public.plans_gestion_vegetation (id)"
            ),
            "link_parcelles_gestion_troncons": (
                "foreign key (parcelle_gestion_id) references public.parcelles_gestion_vegetation (id)",
                "foreign key (troncon_id) references public.troncons (id)",
            ),
            "vegetation": (
                "foreign key (nature_id) references public.ref_natures_vegetation (id)",
                "foreign key (etat_sanitaire_id) references public.ref_etats_sanitaires_vegetation (id)",
                "foreign key (classe_hauteur_id) references public.ref_classes_hauteur_vegetation (id)",
                "foreign key (classe_diametre_id) references public.ref_classes_diametre_vegetation (id)",
                "foreign key (parcelle_gestion_id) references public.parcelles_gestion_vegetation (id)",
            ),
            "equipements_mesure": (
                "foreign key (type_id) references public.ref_types_equipement_mesure (id)",
                "foreign key (troncon_id) references public.troncons (id)",
            ),
            "ouvrages_franchissement": (
                "foreign key (type_id) references public.ref_types_ouvrage_franchissement (id)",
                "foreign key (troncon_id) references public.troncons (id)",
            ),
            "mobilier": (
                "foreign key (type_id) references public.ref_types_mobilier (id)",
                "foreign key (troncon_id) references public.troncons (id)",
            ),
            "reseaux_techniques": (
                "foreign key (type_id) references public.ref_types_reseau_technique (id)",
                "foreign key (troncon_id) references public.troncons (id)",
            ),
        }
        for table, references in expected_references.items():
            if isinstance(references, str):
                references = (references,)
            statement = normalized(TABLE_DEFINITIONS[table])
            for reference in references:
                with self.subTest(table=table, reference=reference):
                    self.assertIn(reference, statement)

    def test_constraints_follow_plural_table_names(self):
        expected_constraints = {
            "ref_types_desordre": "ref_types_desordre_categorie_fk",
            "digues": "digues_systemes_fk",
            "troncons": "troncons_digues_fk",
            "link_desordres_troncons": (
                "link_desordres_troncons_desordres_fk",
                "link_desordres_troncons_troncons_fk",
                "link_desordres_troncons_unique",
            ),
            "desordres": "desordres_type_desordre_fk",
            "observations": (
                "observations_desordres_fk",
                "observations_urgence_fk",
                "observations_exactly_one_parent_check",
                "observations_urgence_desordre_only_check",
            ),
            "photos": "photos_observations_fk",
            "amenagements_hydrauliques": "amenagements_hydrauliques_type_fk",
            "link_amenagements_troncons": (
                "link_amenagements_troncons_amenagements_fk",
                "link_amenagements_troncons_troncons_fk",
                "link_amenagements_troncons_unique",
            ),
            "parcelles_gestion_vegetation": "parcelles_gestion_vegetation_plan_fk",
            "link_parcelles_gestion_troncons": (
                "link_parcelles_gestion_troncons_parcelles_fk",
                "link_parcelles_gestion_troncons_troncons_fk",
                "link_parcelles_gestion_troncons_unique",
            ),
            "vegetation": (
                "vegetation_nature_fk",
                "vegetation_etat_sanitaire_fk",
                "vegetation_classe_hauteur_fk",
                "vegetation_classe_diametre_fk",
                "vegetation_parcelle_gestion_fk",
                "vegetation_geometry_type_check",
            ),
            "ouvrages_hydrauliques": "ouvrages_hydrauliques_amenagements_fk",
        }
        for table, constraints in expected_constraints.items():
            if isinstance(constraints, str):
                constraints = (constraints,)
            statement = normalized(TABLE_DEFINITIONS[table])
            for constraint in constraints:
                with self.subTest(table=table, constraint=constraint):
                    self.assertIn(f"constraint {constraint}", statement)

    def test_link_table_has_generated_primary_key_and_unique_business_pair(self):
        statement = normalized(TABLE_DEFINITIONS["link_desordres_troncons"])
        self.assertIn(
            "id uuid primary key default gen_random_uuid()",
            statement,
        )
        self.assertIn(
            "constraint link_desordres_troncons_unique "
            "unique (desordre_id, troncon_id)",
            statement,
        )
        self.assertNotIn("primary key (desordre_id, troncon_id)", statement)
        amenagement_link = normalized(
            TABLE_DEFINITIONS["link_amenagements_troncons"]
        )
        self.assertIn(
            "constraint link_amenagements_troncons_unique "
            "unique (amenagement_hydraulique_id, troncon_id)",
            amenagement_link,
        )
        vegetation_link = normalized(
            TABLE_DEFINITIONS["link_parcelles_gestion_troncons"]
        )
        self.assertIn(
            "constraint link_parcelles_gestion_troncons_unique "
            "unique (parcelle_gestion_id, troncon_id)",
            vegetation_link,
        )
        self.assertNotIn("unique (parcelle_gestion_id)", vegetation_link)

    def test_geometries_keep_srid_and_desordre_is_generic(self):
        troncon = normalized(TABLE_DEFINITIONS["troncons"])
        desordre = normalized(TABLE_DEFINITIONS["desordres"])
        self.assertIn("geometry geometry(linestring, 3950)", troncon)
        self.assertIn("geometry geometry(geometry, 3950)", desordre)
        self.assertNotIn("geometry geometry(linestring, 3950)", desordre)
        self.assertIn(
            "geometrytype(geometry) in ('point', 'linestring', 'polygon')",
            desordre,
        )
        self.assertIn(
            "geometry geometry(point, 3950)",
            normalized(TABLE_DEFINITIONS["equipements_mesure"]),
        )
        self.assertIn(
            "geometry geometry(point, 3950)",
            normalized(TABLE_DEFINITIONS["mobilier"]),
        )
        for table in (
            "ouvrages_hydrauliques",
            "ouvrages_franchissement",
            "reseaux_techniques",
        ):
            self.assertIn(
                "geometry geometry(geometry, 3950)",
                normalized(TABLE_DEFINITIONS[table]),
            )
        amenagement = normalized(TABLE_DEFINITIONS["amenagements_hydrauliques"])
        self.assertIn("geometry geometry(polygon, 3950) not null", amenagement)
        self.assertNotIn("superficie", amenagement)
        self.assertNotIn("capacite_stockage", amenagement)
        self.assertNotIn("profondeur_moyenne", amenagement)
        parcelle = normalized(TABLE_DEFINITIONS["parcelles_gestion_vegetation"])
        vegetation = normalized(TABLE_DEFINITIONS["vegetation"])
        self.assertIn("geometry geometry(linestring, 3950) not null", parcelle)
        self.assertIn("geometry geometry(geometry, 3950) null", vegetation)
        self.assertIn("geometrytype(geometry) in ('point', 'linestring', 'polygon')", vegetation)
        self.assertNotIn("troncon_id", vegetation)

    def test_observation_designation_is_nullable_text(self):
        observation = normalized(TABLE_DEFINITIONS["observations"])
        self.assertIn("designation text null", observation)
        for excluded_field in (
            "observateurid",
            "suiteapporterid",
            "lastupdateauthor",
        ):
            self.assertNotIn(excluded_field, observation)

    def test_observation_requires_exactly_one_parent_and_photo_requires_observation(self):
        observation = normalized(TABLE_DEFINITIONS["observations"])
        self.assertIn("num_nonnulls(", observation)
        self.assertIn(") = 1", observation)
        self.assertIn("desordre_id uuid null", observation)
        self.assertIn("vegetation_id uuid null", observation)
        photo = normalized(TABLE_DEFINITIONS["photos"])
        self.assertIn("observation_id uuid not null", photo)
        self.assertIn(
            "foreign key (observation_id) references public.observations (id)",
            photo,
        )

    def test_desordres_does_not_store_category(self):
        desordres = normalized(TABLE_DEFINITIONS["desordres"])
        self.assertNotIn("categorie_desordre_id", desordres)

    def test_initialization_uses_one_non_autocommit_connection(self):
        connection = FakeSchemaConnection()
        calls = []

        def connector(**kwargs):
            calls.append(kwargs)
            return connection

        status = initialize_schema(PostgreSQLConfig(), connector=connector)
        self.assertIs(calls[0]["autocommit"], False)
        self.assertEqual(status.tables, EXPECTED_TABLES)
        self.assertEqual(status.pgcrypto_version, "1.3")
        executed_ddl = [query for query, _params in connection.cursor_instance.executed]
        for statement in SCHEMA_DDL:
            self.assertIn(statement, executed_ddl)


if __name__ == "__main__":
    unittest.main()
