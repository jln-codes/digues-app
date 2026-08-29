"""Définition SQL du premier noyau métier PostgreSQL/PostGIS."""

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
            libelle TEXT NOT NULL,
            geometry geometry(LineString, 3950),
            valid BOOLEAN NOT NULL,
            CONSTRAINT troncons_digues_fk
                FOREIGN KEY (digue_id)
                REFERENCES public.digues (id)
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
                REFERENCES public.ref_types_desordre (id)
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
    "observations": """
        CREATE TABLE IF NOT EXISTS public.observations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            desordre_id UUID NOT NULL,
            urgence_id TEXT NULL,
            designation TEXT NULL,
            date DATE NULL,
            evolution TEXT NULL,
            valid BOOLEAN NOT NULL,
            CONSTRAINT observations_desordres_fk
                FOREIGN KEY (desordre_id)
                REFERENCES public.desordres (id),
            CONSTRAINT observations_urgence_fk
                FOREIGN KEY (urgence_id)
                REFERENCES public.ref_urgences (id)
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
}

EXPECTED_TABLES = tuple(TABLE_DEFINITIONS)
SCHEMA_DDL = tuple(statement.strip() for statement in TABLE_DEFINITIONS.values())
