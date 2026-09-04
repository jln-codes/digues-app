"""Définition SQL du premier noyau métier PostgreSQL/PostGIS."""

from .reperage import REPERAGE_FUNCTION_DDL
from .desordre_reperage import (
    FUNCTION_DDL as DESORDRE_REPERAGE_FUNCTION_DDL,
    INDEX_DEFINITIONS as DESORDRE_REPERAGE_INDEX_DEFINITIONS,
    TABLE_DEFINITIONS as DESORDRE_REPERAGE_TABLE_DEFINITIONS,
    TRIGGER_DDL as DESORDRE_REPERAGE_TRIGGER_DDL,
    VIEW_TRIGGER_DDL as DESORDRE_REPERAGE_VIEW_TRIGGER_DDL,
    VIEW_DEFINITIONS,
)

POSTGIS_SEARCH_PATH_SUFFIX_PLACEHOLDER = "__SIRS_POSTGIS_SEARCH_PATH_SUFFIX__"


def quote_identifier(identifier: str) -> str:
    """Quote un identifiant PostgreSQL pour une clause search_path statique."""

    if not identifier or "\x00" in identifier:
        raise ValueError("Identifiant PostgreSQL invalide")
    return '"' + identifier.replace('"', '""') + '"'


def postgis_search_path_suffix(postgis_schema: str | None) -> str:
    if postgis_schema is None or postgis_schema in {"public", "pg_catalog"}:
        return ""
    return ", " + quote_identifier(postgis_schema)


def render_schema_ddl(postgis_schema: str | None = "public") -> tuple[str, ...]:
    suffix = postgis_search_path_suffix(postgis_schema)
    return tuple(
        statement.replace(POSTGIS_SEARCH_PATH_SUFFIX_PLACEHOLDER, suffix)
        for statement in SCHEMA_DDL_TEMPLATE
    )


TABLE_DEFINITIONS = {
    "systemes": """
        CREATE TABLE IF NOT EXISTS public.systemes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            libelle TEXT NOT NULL,
            valid BOOLEAN NOT NULL
        )
    """,
    "digues": """
        CREATE TABLE IF NOT EXISTS public.digues (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            systeme_endiguement_id UUID NULL,
            libelle TEXT NOT NULL,
            valid BOOLEAN NOT NULL,
            CONSTRAINT digues_systemes_fk
                FOREIGN KEY (systeme_endiguement_id)
                REFERENCES public.systemes (id)
        )
    """,
    "troncons": """
        CREATE TABLE IF NOT EXISTS public.troncons (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            digue_id UUID NOT NULL,
            systeme_reperage_defaut_id UUID NULL,
            libelle TEXT NOT NULL,
            geometry geometry(LineString, 3950),
            valid BOOLEAN NOT NULL,
            CONSTRAINT troncons_digues_fk
                FOREIGN KEY (digue_id)
                REFERENCES public.digues (id)
        )
    """,
    "systemes_reperage": """
        CREATE TABLE IF NOT EXISTS public.systemes_reperage (
            id UUID PRIMARY KEY,
            troncon_id UUID NOT NULL,
            libelle TEXT NULL,
            commentaire TEXT NULL,
            valid BOOLEAN NOT NULL,
            CONSTRAINT systemes_reperage_id_troncon_unique
                UNIQUE (id, troncon_id),
            CONSTRAINT systemes_reperage_troncons_fk
                FOREIGN KEY (troncon_id)
                REFERENCES public.troncons (id)
        )
    """,
    "bornes_reperage": """
        CREATE TABLE IF NOT EXISTS public.bornes_reperage (
            id UUID PRIMARY KEY,
            libelle TEXT NULL,
            commentaire TEXT NULL,
            geometry geometry(Point, 3950) NULL,
            fictive BOOLEAN NULL,
            date_debut DATE NULL,
            date_fin DATE NULL,
            valid BOOLEAN NOT NULL
        )
    """,
    "link_troncons_bornes": """
        CREATE TABLE IF NOT EXISTS public.link_troncons_bornes (
            troncon_id UUID NOT NULL,
            borne_id UUID NOT NULL,
            CONSTRAINT link_troncons_bornes_pk
                PRIMARY KEY (troncon_id, borne_id),
            CONSTRAINT link_troncons_bornes_troncons_fk
                FOREIGN KEY (troncon_id)
                REFERENCES public.troncons (id),
            CONSTRAINT link_troncons_bornes_bornes_fk
                FOREIGN KEY (borne_id)
                REFERENCES public.bornes_reperage (id)
        )
    """,
    "link_systemes_reperage_bornes": """
        CREATE TABLE IF NOT EXISTS public.link_systemes_reperage_bornes (
            id UUID PRIMARY KEY,
            systeme_reperage_id UUID NOT NULL,
            borne_id UUID NOT NULL,
            valeur_pr NUMERIC NOT NULL,
            valid BOOLEAN NOT NULL,
            CONSTRAINT link_systemes_reperage_bornes_systemes_fk
                FOREIGN KEY (systeme_reperage_id)
                REFERENCES public.systemes_reperage (id),
            CONSTRAINT link_systemes_reperage_bornes_bornes_fk
                FOREIGN KEY (borne_id)
                REFERENCES public.bornes_reperage (id),
            CONSTRAINT link_systemes_reperage_bornes_unique
                UNIQUE (systeme_reperage_id, borne_id)
        )
    """,
    "ref_categories_desordre": """
        CREATE TABLE IF NOT EXISTS public.ref_categories_desordre (
            id TEXT PRIMARY KEY,
            libelle TEXT NOT NULL,
            valid BOOLEAN NOT NULL
        )
    """,
    "ref_types_desordre": """
        CREATE TABLE IF NOT EXISTS public.ref_types_desordre (
            id TEXT PRIMARY KEY,
            categorie_id TEXT NOT NULL,
            libelle TEXT NOT NULL,
            valid BOOLEAN NOT NULL,
            CONSTRAINT ref_types_desordre_categorie_fk
                FOREIGN KEY (categorie_id)
                REFERENCES public.ref_categories_desordre (id)
        )
    """,
    "ref_urgences": """
        CREATE TABLE IF NOT EXISTS public.ref_urgences (
            id TEXT PRIMARY KEY,
            libelle TEXT NOT NULL,
            valid BOOLEAN NOT NULL
        )
    """,
    "ref_types_ouvrage_hydraulique": """
        CREATE TABLE IF NOT EXISTS public.ref_types_ouvrage_hydraulique (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            abrege TEXT NOT NULL UNIQUE,
            libelle TEXT NOT NULL,
            valid BOOLEAN NOT NULL
        )
    """,
    "ref_types_equipement_mesure": """
        CREATE TABLE IF NOT EXISTS public.ref_types_equipement_mesure (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            abrege TEXT NOT NULL UNIQUE,
            libelle TEXT NOT NULL,
            valid BOOLEAN NOT NULL
        )
    """,
    "ref_types_cheminement": """
        CREATE TABLE IF NOT EXISTS public.ref_types_cheminement (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            abrege TEXT NOT NULL UNIQUE,
            libelle TEXT NOT NULL,
            valid BOOLEAN NOT NULL
        )
    """,
    "ref_types_mobilier": """
        CREATE TABLE IF NOT EXISTS public.ref_types_mobilier (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            abrege TEXT NOT NULL UNIQUE,
            libelle TEXT NOT NULL,
            valid BOOLEAN NOT NULL
        )
    """,
    "ref_types_reseau_technique": """
        CREATE TABLE IF NOT EXISTS public.ref_types_reseau_technique (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            abrege TEXT NOT NULL UNIQUE,
            libelle TEXT NOT NULL,
            valid BOOLEAN NOT NULL
        )
    """,
    "ref_types_amenagement_hydraulique": """
        CREATE TABLE IF NOT EXISTS public.ref_types_amenagement_hydraulique (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            abrege TEXT NOT NULL UNIQUE,
            libelle TEXT NOT NULL,
            valid BOOLEAN NOT NULL
        )
    """,
    "ref_natures_vegetation": """
        CREATE TABLE IF NOT EXISTS public.ref_natures_vegetation (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            abrege TEXT NOT NULL UNIQUE,
            libelle TEXT NOT NULL,
            valid BOOLEAN NOT NULL
        )
    """,
    "ref_etats_sanitaires_vegetation": """
        CREATE TABLE IF NOT EXISTS public.ref_etats_sanitaires_vegetation (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            abrege TEXT NOT NULL UNIQUE,
            libelle TEXT NOT NULL,
            valid BOOLEAN NOT NULL
        )
    """,
    "ref_classes_hauteur_vegetation": """
        CREATE TABLE IF NOT EXISTS public.ref_classes_hauteur_vegetation (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            abrege TEXT NOT NULL UNIQUE,
            libelle TEXT NOT NULL,
            valid BOOLEAN NOT NULL
        )
    """,
    "ref_classes_diametre_vegetation": """
        CREATE TABLE IF NOT EXISTS public.ref_classes_diametre_vegetation (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            abrege TEXT NOT NULL UNIQUE,
            libelle TEXT NOT NULL,
            valid BOOLEAN NOT NULL
        )
    """,
    "desordres": """
        CREATE TABLE IF NOT EXISTS public.desordres (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            type_desordre_id TEXT NULL,
            designation TEXT NULL,
            commentaire TEXT NULL,
            date_debut DATE NULL,
            date_fin DATE NULL,
            geometry geometry(Geometry, 3950) NULL,
            valid BOOLEAN NOT NULL,
            CONSTRAINT desordres_type_desordre_fk
                FOREIGN KEY (type_desordre_id)
                REFERENCES public.ref_types_desordre (id),
            CONSTRAINT desordres_geometry_type_check
                CHECK (
                    geometry IS NULL
                    OR GeometryType(geometry) IN ('POINT', 'LINESTRING', 'POLYGON')
                )
        )
    """,
    "link_desordres_troncons": """
        CREATE TABLE IF NOT EXISTS public.link_desordres_troncons (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            desordre_id UUID NOT NULL,
            troncon_id UUID NOT NULL,
            CONSTRAINT link_desordres_troncons_desordres_fk
                FOREIGN KEY (desordre_id)
                REFERENCES public.desordres (id),
            CONSTRAINT link_desordres_troncons_troncons_fk
                FOREIGN KEY (troncon_id)
                REFERENCES public.troncons (id),
            CONSTRAINT link_desordres_troncons_unique
                UNIQUE (desordre_id, troncon_id)
        )
    """,
    "amenagements_hydrauliques": """
        CREATE TABLE IF NOT EXISTS public.amenagements_hydrauliques (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            type_id TEXT NULL,
            designation TEXT NULL,
            date_debut DATE NULL,
            geometry geometry(Polygon, 3950) NOT NULL,
            valid BOOLEAN NOT NULL,
            CONSTRAINT amenagements_hydrauliques_type_fk
                FOREIGN KEY (type_id)
                REFERENCES public.ref_types_amenagement_hydraulique (id)
        )
    """,
    "link_amenagements_troncons": """
        CREATE TABLE IF NOT EXISTS public.link_amenagements_troncons (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            amenagement_hydraulique_id UUID NOT NULL,
            troncon_id UUID NOT NULL,
            CONSTRAINT link_amenagements_troncons_amenagements_fk
                FOREIGN KEY (amenagement_hydraulique_id)
                REFERENCES public.amenagements_hydrauliques (id),
            CONSTRAINT link_amenagements_troncons_troncons_fk
                FOREIGN KEY (troncon_id)
                REFERENCES public.troncons (id),
            CONSTRAINT link_amenagements_troncons_unique
                UNIQUE (amenagement_hydraulique_id, troncon_id)
        )
    """,
    "plans_gestion_vegetation": """
        CREATE TABLE IF NOT EXISTS public.plans_gestion_vegetation (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            libelle TEXT NULL,
            annee_debut INTEGER NULL,
            annee_fin INTEGER NULL,
            valid BOOLEAN NOT NULL
        )
    """,
    "parcelles_gestion_vegetation": """
        CREATE TABLE IF NOT EXISTS public.parcelles_gestion_vegetation (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            plan_id UUID NULL,
            designation TEXT NULL,
            date_debut DATE NULL,
            geometry geometry(LineString, 3950) NOT NULL,
            valid BOOLEAN NOT NULL,
            CONSTRAINT parcelles_gestion_vegetation_plan_fk
                FOREIGN KEY (plan_id)
                REFERENCES public.plans_gestion_vegetation (id)
        )
    """,
    "link_parcelles_gestion_troncons": """
        CREATE TABLE IF NOT EXISTS public.link_parcelles_gestion_troncons (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            parcelle_gestion_id UUID NOT NULL,
            troncon_id UUID NOT NULL,
            CONSTRAINT link_parcelles_gestion_troncons_parcelles_fk
                FOREIGN KEY (parcelle_gestion_id)
                REFERENCES public.parcelles_gestion_vegetation (id),
            CONSTRAINT link_parcelles_gestion_troncons_troncons_fk
                FOREIGN KEY (troncon_id)
                REFERENCES public.troncons (id),
            CONSTRAINT link_parcelles_gestion_troncons_unique
                UNIQUE (parcelle_gestion_id, troncon_id)
        )
    """,
    "vegetation": """
        CREATE TABLE IF NOT EXISTS public.vegetation (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            nature_id TEXT NOT NULL,
            designation TEXT NULL,
            commentaire TEXT NULL,
            date_debut DATE NULL,
            etat_sanitaire_id TEXT NULL,
            classe_hauteur_id TEXT NULL,
            classe_diametre_id TEXT NULL,
            geometry geometry(Geometry, 3950) NULL,
            parcelle_gestion_id UUID NOT NULL,
            valid BOOLEAN NOT NULL,
            CONSTRAINT vegetation_nature_fk
                FOREIGN KEY (nature_id)
                REFERENCES public.ref_natures_vegetation (id),
            CONSTRAINT vegetation_etat_sanitaire_fk
                FOREIGN KEY (etat_sanitaire_id)
                REFERENCES public.ref_etats_sanitaires_vegetation (id),
            CONSTRAINT vegetation_classe_hauteur_fk
                FOREIGN KEY (classe_hauteur_id)
                REFERENCES public.ref_classes_hauteur_vegetation (id),
            CONSTRAINT vegetation_classe_diametre_fk
                FOREIGN KEY (classe_diametre_id)
                REFERENCES public.ref_classes_diametre_vegetation (id),
            CONSTRAINT vegetation_parcelle_gestion_fk
                FOREIGN KEY (parcelle_gestion_id)
                REFERENCES public.parcelles_gestion_vegetation (id),
            CONSTRAINT vegetation_geometry_type_check
                CHECK (
                    geometry IS NULL
                    OR GeometryType(geometry) IN ('POINT', 'LINESTRING', 'POLYGON')
                )
        )
    """,
    "ouvrages_hydrauliques": """
        CREATE TABLE IF NOT EXISTS public.ouvrages_hydrauliques (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            type_id TEXT NOT NULL,
            designation TEXT NULL,
            commentaire TEXT NULL,
            date_debut DATE NULL,
            geometry geometry(Geometry, 3950) NULL,
            troncon_id UUID NULL,
            amenagement_hydraulique_id UUID NULL,
            valid BOOLEAN NOT NULL,
            CONSTRAINT ouvrages_hydrauliques_type_fk
                FOREIGN KEY (type_id)
                REFERENCES public.ref_types_ouvrage_hydraulique (id),
            CONSTRAINT ouvrages_hydrauliques_troncons_fk
                FOREIGN KEY (troncon_id)
                REFERENCES public.troncons (id),
            CONSTRAINT ouvrages_hydrauliques_amenagements_fk
                FOREIGN KEY (amenagement_hydraulique_id)
                REFERENCES public.amenagements_hydrauliques (id)
        )
    """,
    "equipements_mesure": """
        CREATE TABLE IF NOT EXISTS public.equipements_mesure (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            type_id TEXT NOT NULL,
            designation TEXT NULL,
            commentaire TEXT NULL,
            date_debut DATE NULL,
            geometry geometry(Point, 3950) NULL,
            troncon_id UUID NULL,
            valid BOOLEAN NOT NULL,
            CONSTRAINT equipements_mesure_type_fk
                FOREIGN KEY (type_id)
                REFERENCES public.ref_types_equipement_mesure (id),
            CONSTRAINT equipements_mesure_troncons_fk
                FOREIGN KEY (troncon_id)
                REFERENCES public.troncons (id)
        )
    """,
    "cheminements": """
        CREATE TABLE IF NOT EXISTS public.cheminements (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            type_cheminement_id TEXT NOT NULL,
            designation TEXT NULL,
            libelle TEXT NULL,
            commentaire TEXT NULL,
            date_debut DATE NULL,
            date_fin DATE NULL,
            largeur DOUBLE PRECISION NULL,
            usage_source_id TEXT NULL,
            statut_source BOOLEAN NULL,
            materiau_source_id TEXT NULL,
            revetement_source_id TEXT NULL,
            position_source_id TEXT NULL,
            cote_source_id TEXT NULL,
            securite_source_id TEXT NULL,
            orientation_ouvrage_source_id TEXT NULL,
            position_haut_source_id TEXT NULL,
            position_bas_source_id TEXT NULL,
            revetement_haut_source_id TEXT NULL,
            revetement_bas_source_id TEXT NULL,
            dimension_horizontale DOUBLE PRECISION NULL,
            dimension_verticale DOUBLE PRECISION NULL,
            numero_secteur INTEGER NULL,
            geometry geometry(Geometry, 3950) NULL,
            valid BOOLEAN NOT NULL,
            CONSTRAINT cheminements_type_fk
                FOREIGN KEY (type_cheminement_id)
                REFERENCES public.ref_types_cheminement (id)
        )
    """,
    "link_cheminements_troncons": """
        CREATE TABLE IF NOT EXISTS public.link_cheminements_troncons (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            cheminement_id UUID NOT NULL,
            troncon_id UUID NOT NULL,
            CONSTRAINT link_cheminements_troncons_cheminements_fk
                FOREIGN KEY (cheminement_id)
                REFERENCES public.cheminements (id),
            CONSTRAINT link_cheminements_troncons_troncons_fk
                FOREIGN KEY (troncon_id)
                REFERENCES public.troncons (id),
            CONSTRAINT link_cheminements_troncons_unique
                UNIQUE (cheminement_id, troncon_id)
        )
    """,
    "link_cheminements_desordres": """
        CREATE TABLE IF NOT EXISTS public.link_cheminements_desordres (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            cheminement_id UUID NOT NULL,
            desordre_id UUID NOT NULL,
            CONSTRAINT link_cheminements_desordres_cheminements_fk
                FOREIGN KEY (cheminement_id)
                REFERENCES public.cheminements (id),
            CONSTRAINT link_cheminements_desordres_desordres_fk
                FOREIGN KEY (desordre_id)
                REFERENCES public.desordres (id),
            CONSTRAINT link_cheminements_desordres_unique
                UNIQUE (cheminement_id, desordre_id)
        )
    """,
    "mobilier": """
        CREATE TABLE IF NOT EXISTS public.mobilier (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            type_id TEXT NOT NULL,
            designation TEXT NULL,
            commentaire TEXT NULL,
            date_debut DATE NULL,
            geometry geometry(Point, 3950) NULL,
            troncon_id UUID NULL,
            valid BOOLEAN NOT NULL,
            CONSTRAINT mobilier_type_fk
                FOREIGN KEY (type_id)
                REFERENCES public.ref_types_mobilier (id),
            CONSTRAINT mobilier_troncons_fk
                FOREIGN KEY (troncon_id)
                REFERENCES public.troncons (id)
        )
    """,
    "reseaux_techniques": """
        CREATE TABLE IF NOT EXISTS public.reseaux_techniques (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            type_id TEXT NOT NULL,
            designation TEXT NULL,
            commentaire TEXT NULL,
            date_debut DATE NULL,
            geometry geometry(Geometry, 3950) NULL,
            troncon_id UUID NULL,
            valid BOOLEAN NOT NULL,
            CONSTRAINT reseaux_techniques_type_fk
                FOREIGN KEY (type_id)
                REFERENCES public.ref_types_reseau_technique (id),
            CONSTRAINT reseaux_techniques_troncons_fk
                FOREIGN KEY (troncon_id)
                REFERENCES public.troncons (id)
        )
    """,
    "observations": """
        CREATE TABLE IF NOT EXISTS public.observations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            desordre_id UUID NULL,
            troncon_id UUID NULL,
            ouvrage_hydraulique_id UUID NULL,
            equipement_mesure_id UUID NULL,
            cheminement_id UUID NULL,
            mobilier_id UUID NULL,
            reseau_technique_id UUID NULL,
            amenagement_hydraulique_id UUID NULL,
            vegetation_id UUID NULL,
            urgence_id TEXT NULL,
            designation TEXT NULL,
            date DATE NULL,
            evolution TEXT NULL,
            valid BOOLEAN NOT NULL,
            CONSTRAINT observations_desordres_fk
                FOREIGN KEY (desordre_id) REFERENCES public.desordres (id),
            CONSTRAINT observations_troncons_fk
                FOREIGN KEY (troncon_id) REFERENCES public.troncons (id),
            CONSTRAINT observations_ouvrages_hydrauliques_fk
                FOREIGN KEY (ouvrage_hydraulique_id)
                REFERENCES public.ouvrages_hydrauliques (id),
            CONSTRAINT observations_equipements_mesure_fk
                FOREIGN KEY (equipement_mesure_id)
                REFERENCES public.equipements_mesure (id),
            CONSTRAINT observations_cheminements_fk
                FOREIGN KEY (cheminement_id)
                REFERENCES public.cheminements (id),
            CONSTRAINT observations_mobilier_fk
                FOREIGN KEY (mobilier_id) REFERENCES public.mobilier (id),
            CONSTRAINT observations_reseaux_techniques_fk
                FOREIGN KEY (reseau_technique_id)
                REFERENCES public.reseaux_techniques (id),
            CONSTRAINT observations_amenagements_hydrauliques_fk
                FOREIGN KEY (amenagement_hydraulique_id)
                REFERENCES public.amenagements_hydrauliques (id),
            CONSTRAINT observations_vegetation_fk
                FOREIGN KEY (vegetation_id) REFERENCES public.vegetation (id),
            CONSTRAINT observations_urgence_fk
                FOREIGN KEY (urgence_id) REFERENCES public.ref_urgences (id),
            CONSTRAINT observations_exactly_one_parent_check
                CHECK (
                    num_nonnulls(
                        desordre_id, troncon_id, ouvrage_hydraulique_id,
                        equipement_mesure_id, cheminement_id,
                        mobilier_id, reseau_technique_id,
                        amenagement_hydraulique_id, vegetation_id
                    ) = 1
                ),
            CONSTRAINT observations_urgence_desordre_only_check
                CHECK (urgence_id IS NULL OR desordre_id IS NOT NULL)
        )
    """,
    "photos": """
        CREATE TABLE IF NOT EXISTS public.photos (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            observation_id UUID NOT NULL,
            chemin_source TEXT NOT NULL,
            date DATE NULL,
            designation TEXT NULL,
            valid BOOLEAN NOT NULL,
            CONSTRAINT photos_observations_fk
                FOREIGN KEY (observation_id)
                REFERENCES public.observations (id)
        )
    """,
    **DESORDRE_REPERAGE_TABLE_DEFINITIONS,
}

EXPECTED_TABLES = tuple(TABLE_DEFINITIONS)

# Le cycle troncons <-> systemes_reperage impose d'ajouter la FK du système par
# défaut après la création des deux tables. Le bloc reste idempotent afin que
# `init-schema` conserve son comportement actuel.
CONSTRAINT_DEFINITIONS = {
    "troncons_systeme_reperage_defaut_fk": """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'troncons_systeme_reperage_defaut_fk'
                  AND conrelid = 'public.troncons'::regclass
            ) THEN
                ALTER TABLE public.troncons
                    ADD CONSTRAINT troncons_systeme_reperage_defaut_fk
                    FOREIGN KEY (systeme_reperage_defaut_id)
                    REFERENCES public.systemes_reperage (id);
            END IF;
        END
        $$
    """,
}

INDEX_DEFINITIONS = {
    "systemes_reperage_troncon_idx": """
        CREATE INDEX IF NOT EXISTS systemes_reperage_troncon_idx
        ON public.systemes_reperage (troncon_id)
    """,
    "troncons_systeme_reperage_defaut_idx": """
        CREATE INDEX IF NOT EXISTS troncons_systeme_reperage_defaut_idx
        ON public.troncons (systeme_reperage_defaut_id)
    """,
    "link_troncons_bornes_borne_idx": """
        CREATE INDEX IF NOT EXISTS link_troncons_bornes_borne_idx
        ON public.link_troncons_bornes (borne_id)
    """,
    "link_systemes_reperage_bornes_borne_idx": """
        CREATE INDEX IF NOT EXISTS link_systemes_reperage_bornes_borne_idx
        ON public.link_systemes_reperage_bornes (borne_id)
    """,
    **DESORDRE_REPERAGE_INDEX_DEFINITIONS,
}

SCHEMA_DDL_TEMPLATE = tuple(
    statement.strip()
    for statement in (
        *TABLE_DEFINITIONS.values(),
        *CONSTRAINT_DEFINITIONS.values(),
        *INDEX_DEFINITIONS.values(),
        *REPERAGE_FUNCTION_DDL,
        *DESORDRE_REPERAGE_FUNCTION_DDL,
        *DESORDRE_REPERAGE_TRIGGER_DDL,
        *VIEW_DEFINITIONS.values(),
        *DESORDRE_REPERAGE_VIEW_TRIGGER_DDL,
    )
)

SCHEMA_DDL = render_schema_ddl("public")
