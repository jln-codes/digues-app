"""Schéma pilote de localisation de repérage réservé aux désordres.

La table enfant directe rend le 1:N utilisable par le widget de relation natif
de QGIS/QField. Elle ne préjuge pas du futur modèle transversal des autres
familles métier.
"""


TABLE_DEFINITIONS = {
    "desordre_localisations_reperage": """
        CREATE TABLE IF NOT EXISTS public.desordre_localisations_reperage (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            desordre_id UUID NOT NULL,
            troncon_id UUID NULL,
            systeme_reperage_id UUID NULL,
            borne_debut_id UUID NULL,
            distance_debut_m DOUBLE PRECISION NULL,
            position_debut_relative TEXT NULL,
            offset_debut_m DOUBLE PRECISION GENERATED ALWAYS AS (
                CASE position_debut_relative
                    WHEN 'AVANT_BORNE' THEN -distance_debut_m
                    WHEN 'SUR_BORNE' THEN 0.0
                    WHEN 'APRES_BORNE' THEN distance_debut_m
                    ELSE NULL
                END
            ) STORED,
            borne_fin_id UUID NULL,
            distance_fin_m DOUBLE PRECISION NULL,
            position_fin_relative TEXT NULL,
            offset_fin_m DOUBLE PRECISION GENERATED ALWAYS AS (
                CASE position_fin_relative
                    WHEN 'AVANT_BORNE' THEN -distance_fin_m
                    WHEN 'SUR_BORNE' THEN 0.0
                    WHEN 'APRES_BORNE' THEN distance_fin_m
                    ELSE NULL
                END
            ) STORED,
            pr_debut_source NUMERIC NULL,
            pr_fin_source NUMERIC NULL,
            position_debut_source geometry(Point, 3950) NULL,
            position_fin_source geometry(Point, 3950) NULL,
            mode_saisie_source TEXT NOT NULL DEFAULT 'INCONNU',
            politique_autorite TEXT NOT NULL DEFAULT 'MANUELLE',
            qualite TEXT NOT NULL DEFAULT 'INCOMPLETE',
            valid BOOLEAN NOT NULL DEFAULT true,
            source_document_id TEXT NULL,
            trace_source JSONB NOT NULL DEFAULT '{}'::jsonb,
            diagnostic_conversion JSONB NOT NULL DEFAULT '{}'::jsonb,
            CONSTRAINT desordre_localisations_reperage_desordres_fk
                FOREIGN KEY (desordre_id)
                REFERENCES public.desordres (id),
            CONSTRAINT desordre_localisations_reperage_lien_troncon_fk
                FOREIGN KEY (desordre_id, troncon_id)
                REFERENCES public.link_desordres_troncons
                    (desordre_id, troncon_id),
            CONSTRAINT desordre_localisations_reperage_systeme_troncon_fk
                FOREIGN KEY (systeme_reperage_id, troncon_id)
                REFERENCES public.systemes_reperage (id, troncon_id),
            CONSTRAINT desordre_localisations_reperage_borne_debut_fk
                FOREIGN KEY (systeme_reperage_id, borne_debut_id)
                REFERENCES public.link_systemes_reperage_bornes
                    (systeme_reperage_id, borne_id),
            CONSTRAINT desordre_localisations_reperage_borne_fin_fk
                FOREIGN KEY (systeme_reperage_id, borne_fin_id)
                REFERENCES public.link_systemes_reperage_bornes
                    (systeme_reperage_id, borne_id),
            CONSTRAINT desordre_localisations_reperage_mode_check
                CHECK (mode_saisie_source IN (
                    'GPS', 'CARTE', 'BORNE_DISTANCE', 'IMPORT', 'INCONNU'
                )),
            CONSTRAINT desordre_localisations_reperage_politique_check
                CHECK (politique_autorite IN (
                    'GEOMETRIE_FIXE', 'REPERAGE_FIXE', 'MANUELLE'
                )),
            CONSTRAINT desordre_localisations_reperage_qualite_check
                CHECK (qualite IN (
                    'OK', 'INCOMPLETE', 'REFERENCE_ABSENTE',
                    'CONFLIT_SYSTEME', 'AMBIGU', 'INCOHERENT'
                )),
            CONSTRAINT desordre_localisations_reperage_systeme_requires_troncon
                CHECK (systeme_reperage_id IS NULL OR troncon_id IS NOT NULL),
            CONSTRAINT desordre_localisations_reperage_borne_debut_requires_systeme
                CHECK (borne_debut_id IS NULL OR systeme_reperage_id IS NOT NULL),
            CONSTRAINT desordre_localisations_reperage_borne_fin_requires_systeme
                CHECK (borne_fin_id IS NULL OR systeme_reperage_id IS NOT NULL),
            CONSTRAINT desordre_localisations_reperage_distance_debut_check
                CHECK (distance_debut_m IS NULL OR distance_debut_m >= 0),
            CONSTRAINT desordre_localisations_reperage_distance_fin_check
                CHECK (distance_fin_m IS NULL OR distance_fin_m >= 0),
            CONSTRAINT desordre_localisations_reperage_position_debut_check
                CHECK (position_debut_relative IS NULL OR
                    position_debut_relative IN (
                        'AVANT_BORNE', 'SUR_BORNE', 'APRES_BORNE'
                    )),
            CONSTRAINT desordre_localisations_reperage_position_fin_check
                CHECK (position_fin_relative IS NULL OR
                    position_fin_relative IN (
                        'AVANT_BORNE', 'SUR_BORNE', 'APRES_BORNE'
                    )),
            CONSTRAINT desordre_localisations_reperage_debut_complete_check
                CHECK (
                    (distance_debut_m IS NULL) =
                    (position_debut_relative IS NULL)
                    AND (distance_debut_m IS NULL OR borne_debut_id IS NOT NULL)
                    AND (position_debut_relative <> 'SUR_BORNE'
                         OR distance_debut_m = 0)
                ),
            CONSTRAINT desordre_localisations_reperage_fin_complete_check
                CHECK (
                    (distance_fin_m IS NULL) =
                    (position_fin_relative IS NULL)
                    AND (distance_fin_m IS NULL OR borne_fin_id IS NOT NULL)
                    AND (position_fin_relative <> 'SUR_BORNE'
                         OR distance_fin_m = 0)
                )
        )
    """,
}


INDEX_DEFINITIONS = {
    "desordre_localisations_reperage_desordre_idx": """
        CREATE INDEX IF NOT EXISTS desordre_localisations_reperage_desordre_idx
        ON public.desordre_localisations_reperage (desordre_id)
    """,
    "desordre_localisations_reperage_troncon_idx": """
        CREATE INDEX IF NOT EXISTS desordre_localisations_reperage_troncon_idx
        ON public.desordre_localisations_reperage (troncon_id)
    """,
    "desordre_localisations_reperage_systeme_idx": """
        CREATE INDEX IF NOT EXISTS desordre_localisations_reperage_systeme_idx
        ON public.desordre_localisations_reperage (systeme_reperage_id)
    """,
}


VIEW_DEFINITIONS = {
    "view_desordre_localisations_reperage": """
        CREATE OR REPLACE VIEW public.view_desordre_localisations_reperage AS
        SELECT
            l.id,
            l.desordre_id,
            d.designation AS desordre_designation,
            GeometryType(d.geometry) AS type_geometrie_desordre,
            l.troncon_id,
            t.libelle AS troncon_libelle,
            l.systeme_reperage_id,
            sr.libelle AS systeme_reperage_libelle,
            l.borne_debut_id,
            bd.libelle AS borne_debut_libelle,
            l.distance_debut_m,
            l.position_debut_relative,
            l.borne_fin_id,
            bf.libelle AS borne_fin_libelle,
            l.distance_fin_m,
            l.position_fin_relative,
            l.pr_debut_source,
            l.pr_fin_source,
            calc_debut.pr AS pr_debut_courant,
            calc_fin.pr AS pr_fin_courant,
            l.mode_saisie_source,
            l.politique_autorite,
            l.qualite AS qualite_source,
            CASE
                WHEN l.qualite <> 'OK' THEN l.qualite
                WHEN calc_debut.statut <> 'OK' THEN calc_debut.statut
                WHEN calc_fin.statut <> 'OK' THEN calc_fin.statut
                WHEN calc_debut.statut_pr <> 'OK' THEN calc_debut.statut_pr
                WHEN calc_fin.statut_pr <> 'OK' THEN calc_fin.statut_pr
                ELSE 'OK'
            END AS statut_coherence,
            concat_ws(
                ' — ',
                t.libelle,
                concat_ws(
                    ' ',
                    bd.libelle,
                    CASE WHEN l.offset_debut_m IS NULL THEN NULL
                         ELSE round(abs(l.offset_debut_m)::numeric, 2) || ' m' END,
                    CASE WHEN l.offset_debut_m < 0 THEN 'avant'
                         WHEN l.offset_debut_m > 0 THEN 'après'
                         WHEN l.offset_debut_m = 0 THEN 'sur borne' END
                )
            ) AS resume_localisation,
            l.valid
        FROM public.desordre_localisations_reperage AS l
        JOIN public.desordres AS d ON d.id = l.desordre_id
        LEFT JOIN public.troncons AS t ON t.id = l.troncon_id
        LEFT JOIN public.systemes_reperage AS sr
          ON sr.id = l.systeme_reperage_id
        LEFT JOIN public.bornes_reperage AS bd ON bd.id = l.borne_debut_id
        LEFT JOIN public.bornes_reperage AS bf ON bf.id = l.borne_fin_id
        LEFT JOIN LATERAL (
            SELECT conversion.*
            FROM public.borne_offset_vers_xy(
                l.troncon_id,
                l.systeme_reperage_id,
                l.borne_debut_id,
                l.offset_debut_m
            ) AS conversion
            WHERE l.troncon_id IS NOT NULL
              AND l.systeme_reperage_id IS NOT NULL
              AND l.borne_debut_id IS NOT NULL
              AND l.offset_debut_m IS NOT NULL
        ) AS calc_debut ON true
        LEFT JOIN LATERAL (
            SELECT conversion.*
            FROM public.borne_offset_vers_xy(
                l.troncon_id,
                l.systeme_reperage_id,
                l.borne_fin_id,
                l.offset_fin_m
            ) AS conversion
            WHERE l.troncon_id IS NOT NULL
              AND l.systeme_reperage_id IS NOT NULL
              AND l.borne_fin_id IS NOT NULL
              AND l.offset_fin_m IS NOT NULL
        ) AS calc_fin ON true
    """,
}
