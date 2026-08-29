"""Définition SQL du premier noyau métier PostgreSQL/PostGIS."""

TABLE_DEFINITIONS = {
    "systeme_endiguement": """
        CREATE TABLE IF NOT EXISTS public.systeme_endiguement (
            id UUID PRIMARY KEY,
            libelle TEXT NOT NULL,
            valid BOOLEAN NOT NULL
        )
    """,
    "digue": """
        CREATE TABLE IF NOT EXISTS public.digue (
            id UUID PRIMARY KEY,
            systeme_endiguement_id UUID NULL,
            libelle TEXT NOT NULL,
            valid BOOLEAN NOT NULL,
            CONSTRAINT digue_systeme_endiguement_fk
                FOREIGN KEY (systeme_endiguement_id)
                REFERENCES public.systeme_endiguement (id)
        )
    """,
    "troncon": """
        CREATE TABLE IF NOT EXISTS public.troncon (
            id UUID PRIMARY KEY,
            digue_id UUID NOT NULL,
            libelle TEXT NOT NULL,
            geometry geometry(LineString, 3950),
            valid BOOLEAN NOT NULL,
            CONSTRAINT troncon_digue_fk
                FOREIGN KEY (digue_id)
                REFERENCES public.digue (id)
        )
    """,
    "desordre": """
        CREATE TABLE IF NOT EXISTS public.desordre (
            id UUID PRIMARY KEY,
            designation TEXT NULL,
            commentaire TEXT NULL,
            date_debut DATE NULL,
            date_fin DATE NULL,
            geometry geometry(Geometry, 3950) NULL,
            valid BOOLEAN NOT NULL
        )
    """,
    "link_desordre_troncon": """
        CREATE TABLE IF NOT EXISTS public.link_desordre_troncon (
            desordre_id UUID NOT NULL,
            troncon_id UUID NOT NULL,
            CONSTRAINT link_desordre_troncon_desordre_fk
                FOREIGN KEY (desordre_id)
                REFERENCES public.desordre (id),
            CONSTRAINT link_desordre_troncon_troncon_fk
                FOREIGN KEY (troncon_id)
                REFERENCES public.troncon (id),
            PRIMARY KEY (desordre_id, troncon_id)
        )
    """,
    "observation": """
        CREATE TABLE IF NOT EXISTS public.observation (
            id UUID PRIMARY KEY,
            desordre_id UUID NOT NULL,
            date DATE NULL,
            evolution TEXT NULL,
            valid BOOLEAN NOT NULL,
            CONSTRAINT observation_desordre_fk
                FOREIGN KEY (desordre_id)
                REFERENCES public.desordre (id)
        )
    """,
    "photo": """
        CREATE TABLE IF NOT EXISTS public.photo (
            id UUID PRIMARY KEY,
            observation_id UUID NOT NULL,
            chemin_source TEXT NOT NULL,
            date DATE NULL,
            designation TEXT NULL,
            valid BOOLEAN NOT NULL,
            CONSTRAINT photo_observation_fk
                FOREIGN KEY (observation_id)
                REFERENCES public.observation (id)
        )
    """,
}

EXPECTED_TABLES = tuple(TABLE_DEFINITIONS)
SCHEMA_DDL = tuple(statement.strip() for statement in TABLE_DEFINITIONS.values())
