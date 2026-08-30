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
    "ref_types_ouvrage_franchissement": """
        CREATE TABLE IF NOT EXISTS public.ref_types_ouvrage_franchissement (
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
    "ouvrages_franchissement": """
        CREATE TABLE IF NOT EXISTS public.ouvrages_franchissement (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            type_id TEXT NOT NULL,
            designation TEXT NULL,
            commentaire TEXT NULL,
            date_debut DATE NULL,
            geometry geometry(Geometry, 3950) NULL,
            troncon_id UUID NULL,
            valid BOOLEAN NOT NULL,
            CONSTRAINT ouvrages_franchissement_type_fk
                FOREIGN KEY (type_id)
                REFERENCES public.ref_types_ouvrage_franchissement (id),
            CONSTRAINT ouvrages_franchissement_troncons_fk
                FOREIGN KEY (troncon_id)
                REFERENCES public.troncons (id)
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
}

EXPECTED_TABLES = tuple(TABLE_DEFINITIONS)
SCHEMA_DDL = tuple(statement.strip() for statement in TABLE_DEFINITIONS.values())
