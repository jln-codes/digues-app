import re
import unittest

from digues_app.target.database import PostgreSQLConfig, initialize_schema
from digues_app.target.desordre_reperage import FUNCTION_DEFINITIONS
from digues_app.target.schema import (
    CONSTRAINT_DEFINITIONS,
    EXPECTED_TABLES,
    INDEX_DEFINITIONS,
    SCHEMA_DDL,
    TABLE_DEFINITIONS,
    render_schema_ddl,
)


def normalized(statement):
    return " ".join(statement.split()).lower()


class FakeSchemaCursor:
    def __init__(self):
        self.executed = []
        self.query = ""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        self.query = str(query)
        self.executed.append((str(query), params))

    def fetchone(self):
        return ("3.4.2", "1.3")

    def fetchall(self):
        if "FROM pg_extension" in self.query:
            return [
                ("postgis", "3.4.2", "extensions"),
                ("pgcrypto", "1.3", "extensions"),
            ]
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
                "systemes_reperage",
                "bornes_reperage",
                "link_troncons_bornes",
                "link_systemes_reperage_bornes",
                "ref_categories_desordre",
                "ref_types_desordre",
                "ref_urgences",
                "ref_types_ouvrage_hydraulique",
                "ref_types_equipement_mesure",
                "ref_types_cheminement",
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
                "cheminements",
                "link_cheminements_troncons",
                "link_cheminements_desordres",
                "mobilier",
                "reseaux_techniques",
                "observations",
                "photos",
                "territoires_administratifs",
                "desordre_localisations_reperage",
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
            "systemes_reperage",
            "bornes_reperage",
            "link_systemes_reperage_bornes",
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
            "cheminements",
            "link_cheminements_troncons",
            "link_cheminements_desordres",
            "mobilier",
            "reseaux_techniques",
            "desordre_localisations_reperage",
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
            "cheminements",
            "link_cheminements_troncons",
            "link_cheminements_desordres",
            "mobilier",
            "reseaux_techniques",
            "desordre_localisations_reperage",
        ):
            with self.subTest(table=table):
                self.assertIn(
                    "id uuid primary key default gen_random_uuid()",
                    normalized(TABLE_DEFINITIONS[table]),
                )

    def test_foreign_key_columns_are_uuid(self):
        expected_uuid_columns = {
            "digues": ("systeme_endiguement_id",),
            "troncons": ("digue_id", "systeme_reperage_defaut_id"),
            "systemes_reperage": ("troncon_id",),
            "link_troncons_bornes": ("troncon_id", "borne_id"),
            "link_systemes_reperage_bornes": (
                "systeme_reperage_id",
                "borne_id",
            ),
            "link_desordres_troncons": ("desordre_id", "troncon_id"),
            "desordre_localisations_reperage": (
                "desordre_id",
                "troncon_id",
                "systeme_reperage_id",
                "borne_debut_id",
                "borne_fin_id",
            ),
            "observations": (
                "desordre_id",
                "troncon_id",
                "ouvrage_hydraulique_id",
                "equipement_mesure_id",
                "cheminement_id",
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
            "link_cheminements_troncons": ("cheminement_id", "troncon_id"),
            "link_cheminements_desordres": ("cheminement_id", "desordre_id"),
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
            "ref_types_cheminement",
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
        self.assertIn(
            "type_cheminement_id text not null",
            normalized(TABLE_DEFINITIONS["cheminements"]),
        )
        for table in (
            "ref_types_ouvrage_hydraulique",
            "ref_types_equipement_mesure",
            "ref_types_cheminement",
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
            "systemes_reperage": (
                "foreign key (troncon_id) references public.troncons (id)"
            ),
            "link_troncons_bornes": (
                "foreign key (troncon_id) references public.troncons (id)",
                "foreign key (borne_id) references public.bornes_reperage (id)",
            ),
            "link_systemes_reperage_bornes": (
                "foreign key (systeme_reperage_id) references public.systemes_reperage (id)",
                "foreign key (borne_id) references public.bornes_reperage (id)",
            ),
            "link_desordres_troncons": (
                "foreign key (desordre_id) references public.desordres (id)",
                "foreign key (troncon_id) references public.troncons (id)",
            ),
            "desordre_localisations_reperage": (
                "foreign key (desordre_id) references public.desordres (id)",
                "foreign key (desordre_id, troncon_id) references public.link_desordres_troncons (desordre_id, troncon_id)",
                "foreign key (systeme_reperage_id, troncon_id) references public.systemes_reperage (id, troncon_id)",
                "foreign key (systeme_reperage_id, borne_debut_id) references public.link_systemes_reperage_bornes (systeme_reperage_id, borne_id)",
                "foreign key (systeme_reperage_id, borne_fin_id) references public.link_systemes_reperage_bornes (systeme_reperage_id, borne_id)",
            ),
            "observations": (
                "foreign key (desordre_id) references public.desordres (id)",
                "foreign key (troncon_id) references public.troncons (id)",
                "foreign key (ouvrage_hydraulique_id) references public.ouvrages_hydrauliques (id)",
                "foreign key (equipement_mesure_id) references public.equipements_mesure (id)",
                "foreign key (cheminement_id) references public.cheminements (id)",
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
            "cheminements": (
                "foreign key (type_cheminement_id) references public.ref_types_cheminement (id)",
            ),
            "link_cheminements_troncons": (
                "foreign key (cheminement_id) references public.cheminements (id)",
                "foreign key (troncon_id) references public.troncons (id)",
            ),
            "link_cheminements_desordres": (
                "foreign key (cheminement_id) references public.cheminements (id)",
                "foreign key (desordre_id) references public.desordres (id)",
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
            "cheminements": "cheminements_type_fk",
            "link_cheminements_troncons": (
                "link_cheminements_troncons_cheminements_fk",
                "link_cheminements_troncons_troncons_fk",
                "link_cheminements_troncons_unique",
            ),
            "link_cheminements_desordres": (
                "link_cheminements_desordres_cheminements_fk",
                "link_cheminements_desordres_desordres_fk",
                "link_cheminements_desordres_unique",
            ),
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
        cheminement_troncon_link = normalized(
            TABLE_DEFINITIONS["link_cheminements_troncons"]
        )
        self.assertIn(
            "constraint link_cheminements_troncons_unique "
            "unique (cheminement_id, troncon_id)",
            cheminement_troncon_link,
        )
        cheminement_desordre_link = normalized(
            TABLE_DEFINITIONS["link_cheminements_desordres"]
        )
        self.assertIn(
            "constraint link_cheminements_desordres_unique "
            "unique (cheminement_id, desordre_id)",
            cheminement_desordre_link,
        )

    def test_reperage_core_has_explicit_keys_cycle_fk_and_indexes(self):
        troncons = normalized(TABLE_DEFINITIONS["troncons"])
        systemes = normalized(TABLE_DEFINITIONS["systemes_reperage"])
        bornes = normalized(TABLE_DEFINITIONS["bornes_reperage"])
        troncons_bornes = normalized(TABLE_DEFINITIONS["link_troncons_bornes"])
        systemes_bornes = normalized(
            TABLE_DEFINITIONS["link_systemes_reperage_bornes"]
        )
        self.assertIn("systeme_reperage_defaut_id uuid null", troncons)
        self.assertIn("troncon_id uuid not null", systemes)
        self.assertNotIn("geometry", systemes)
        self.assertIn("geometry geometry(point, 3950) null", bornes)
        self.assertNotIn("valeur_pr", bornes)
        self.assertIn("primary key (troncon_id, borne_id)", troncons_bornes)
        self.assertIn("valeur_pr numeric not null", systemes_bornes)
        self.assertIn("id uuid primary key", systemes_bornes)
        self.assertNotIn("default gen_random_uuid()", systemes_bornes)
        cycle_fk = normalized(
            CONSTRAINT_DEFINITIONS["troncons_systeme_reperage_defaut_fk"]
        )
        self.assertIn("alter table public.troncons", cycle_fk)
        self.assertIn(
            "foreign key (systeme_reperage_defaut_id) references public.systemes_reperage (id)",
            cycle_fk,
        )
        self.assertEqual(
            set(INDEX_DEFINITIONS),
            {
                "systemes_reperage_troncon_idx",
                "troncons_systeme_reperage_defaut_idx",
                "link_troncons_bornes_borne_idx",
                "link_systemes_reperage_bornes_borne_idx",
                "desordre_localisations_reperage_desordre_idx",
                "desordre_localisations_reperage_troncon_idx",
                "desordre_localisations_reperage_systeme_idx",
            },
        )

    def test_desordre_reperage_prototype_is_qgis_editable_and_constrained(self):
        statement = normalized(
            TABLE_DEFINITIONS["desordre_localisations_reperage"]
        )
        self.assertIn("distance_debut_m double precision not null", statement)
        self.assertIn("position_debut_relative text not null", statement)
        self.assertIn("offset_debut_m double precision generated always as", statement)
        self.assertIn("position_debut_relative in (", statement)
        self.assertIn("unique (desordre_id)", statement)
        for migration_field in (
            "pr_debut_source", "pr_fin_source", "position_debut_source",
            "position_fin_source", "mode_saisie_source", "politique_autorite",
            "qualite", "source_document_id", "trace_source",
            "diagnostic_conversion",
        ):
            self.assertNotIn(migration_field, statement)
        self.assertNotIn("on delete cascade", statement)
        ddl = normalized(" ".join(SCHEMA_DDL))
        self.assertIn(
            "create or replace view public.view_desordre_localisations_reperage",
            ddl,
        )
        self.assertIn("create or replace function public.synchroniser_desordre_reperage", ddl)
        self.assertIn("st_linesubstring", normalized(
            FUNCTION_DEFINITIONS["appliquer_desordre_reperage"]
        ))
        self.assertIn("create or replace view public.view_desordres_points_saisie", ddl)

    def test_point_edit_trigger_arbitrates_all_coordinate_families(self):
        statement = normalized(FUNCTION_DEFINITIONS["editer_desordre_point"])
        self.assertIn("v_geometry_modifiee", statement)
        self.assertIn("v_xy_modifie", statement)
        self.assertIn("v_lonlat_modifie", statement)
        self.assertIn("v_nombre_familles > 1", statement)
        self.assertIn("v_nombre_familles = 0", statement)
        self.assertIn("x et y sont obligatoires ensemble", statement)
        self.assertIn("longitude et latitude sont obligatoires ensemble", statement)
        self.assertIn("st_point(new.coord_x_3950, new.coord_y_3950)", statement)
        self.assertIn("st_point(new.longitude_4326, new.latitude_4326)", statement)
        self.assertIn("st_transform(", statement)

    def test_source_only_order_and_vegetation_type_are_not_operational_columns(self):
        system_bornes = normalized(
            TABLE_DEFINITIONS["link_systemes_reperage_bornes"]
        )
        vegetation = normalized(TABLE_DEFINITIONS["vegetation"])
        self.assertNotIn("ordre_source", system_bornes)
        self.assertNotIn("type_source_code", vegetation)

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
            "cheminements",
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
        self.assertNotIn("troncon_id", normalized(TABLE_DEFINITIONS["cheminements"]))

    def test_territoire_administratif_is_a_singleton_polygon_configuration(self):
        territory = normalized(TABLE_DEFINITIONS["territoires_administratifs"])
        self.assertIn("id integer primary key default 1", territory)
        self.assertIn("check (id = 1)", territory)
        self.assertIn("libelle text not null", territory)
        self.assertIn("geometry geometry(polygon, 3950) not null", territory)
        self.assertIn(
            "constraint territoires_administratifs_geometry_check",
            territory,
        )
        self.assertIn("geometrytype(geometry) = 'polygon'", territory)
        self.assertIn("st_isvalid(geometry)", territory)
        self.assertIn("not st_isempty(geometry)", territory)
        self.assertNotIn("valid boolean", territory)
        self.assertNotIn("date_debut", territory)
        self.assertNotIn("date_fin", territory)
        self.assertNotIn("source_filename", territory)

    def test_old_franchissement_target_vocabulary_is_absent(self):
        self.assertNotIn("ouvrages_franchissement", TABLE_DEFINITIONS)
        self.assertNotIn("ref_types_ouvrage_franchissement", TABLE_DEFINITIONS)
        ddl = normalized(" ".join(SCHEMA_DDL))
        self.assertNotIn("ouvrage_franchissement_id", ddl)
        self.assertIn("cheminement_id uuid null", normalized(TABLE_DEFINITIONS["observations"]))

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
        self.assertEqual(status.postgis_schema, "extensions")
        executed_ddl = [query for query, _params in connection.cursor_instance.executed]
        for statement in render_schema_ddl("extensions"):
            self.assertIn(statement, executed_ddl)

    def test_schema_ddl_renders_postgis_search_path_from_extension_schema(self):
        default_ddl = normalized(" ".join(SCHEMA_DDL))
        supabase_like_ddl = normalized(" ".join(render_schema_ddl("extensions")))

        self.assertIn("set search_path = pg_catalog, public", default_ddl)
        self.assertNotIn("__sirs_postgis_search_path_suffix__", default_ddl)
        self.assertIn(
            'set search_path = pg_catalog, public, "extensions"',
            supabase_like_ddl,
        )
        self.assertNotIn("__sirs_postgis_search_path_suffix__", supabase_like_ddl)


if __name__ == "__main__":
    unittest.main()
