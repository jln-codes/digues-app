"""Fonctions PostgreSQL/PostGIS déterministes du moteur de repérage linéaire.

Les fonctions fondamentales reçoivent toujours un tronçon et un système
explicites. Elles ne lisent jamais ``troncons.systeme_reperage_defaut_id``.
L'abscisse utilisée en interne est la distance métrique depuis le début
géométrique du LineString, et non un PR ou une distance hydraulique.
"""


NUMERIC_EPSILON_METERS = 1e-8

# Contrat TEXT volontairement évolutif : aucune migration d'ENUM n'est requise
# pour préciser ultérieurement les diagnostics du moteur.
STATUS_CONTRACT = {
    "OK": "La sortie géométrique ou métier demandée est calculée.",
    "REFERENCE_ABSENTE": "Une entrée obligatoire ou une référence est absente.",
    "CONFLIT_SYSTEME": "Le système ou la borne ne correspond pas aux références demandées.",
    "HORS_DOMAINE": "La valeur sort du tronçon ou de l'étendue du système, sans clamp.",
    "SYSTEME_INCOMPLET": "Le système ne définit pas assez de références pour cette sortie.",
    "AMBIGU": "Plusieurs solutions existent ou la relation PR-abscisse n'est pas univoque.",
    "GEOMETRIE_INVALIDE": "Une géométrie obligatoire est absente, mal typée ou dans un autre SRID.",
}


FUNCTION_DEFINITIONS = {
    "_reperage_pr_depuis_abscisse": f"""
        CREATE OR REPLACE FUNCTION public._reperage_pr_depuis_abscisse(
            p_troncon_id UUID,
            p_systeme_reperage_id UUID,
            p_abscisse_m DOUBLE PRECISION
        )
        RETURNS TABLE (
            statut TEXT,
            pr NUMERIC,
            details JSONB
        )
        LANGUAGE plpgsql
        STABLE
        PARALLEL SAFE
        SET search_path = pg_catalog, public
        AS $function$
        DECLARE
            v_troncon_geometry geometry;
            v_systeme_troncon_id UUID;
            v_longueur_m DOUBLE PRECISION;
            v_nombre_bornes INTEGER;
            v_nombre_geometries_invalides INTEGER;
            v_nombre_references_invalides INTEGER;
            v_abscisse_min DOUBLE PRECISION;
            v_abscisse_max DOUBLE PRECISION;
            v_abscisse_0 DOUBLE PRECISION;
            v_abscisse_1 DOUBLE PRECISION;
            v_pr_0 NUMERIC;
            v_pr_1 NUMERIC;
            v_pr_exact NUMERIC;
            v_doublon_abscisse BOOLEAN;
            v_epsilon CONSTANT DOUBLE PRECISION := {NUMERIC_EPSILON_METERS};
        BEGIN
            statut := NULL;
            pr := NULL;
            details := '{{}}'::jsonb;

            IF p_troncon_id IS NULL OR p_systeme_reperage_id IS NULL
               OR p_abscisse_m IS NULL
               OR p_abscisse_m::text IN ('NaN', 'Infinity', '-Infinity') THEN
                statut := 'REFERENCE_ABSENTE';
                details := jsonb_build_object(
                    'message', 'Tronçon, système et abscisse sont obligatoires.'
                );
                RETURN NEXT;
                RETURN;
            END IF;

            SELECT t.geometry
            INTO v_troncon_geometry
            FROM public.troncons AS t
            WHERE t.id = p_troncon_id;
            IF NOT FOUND THEN
                statut := 'REFERENCE_ABSENTE';
                details := jsonb_build_object('reference', 'troncon');
                RETURN NEXT;
                RETURN;
            END IF;

            SELECT sr.troncon_id
            INTO v_systeme_troncon_id
            FROM public.systemes_reperage AS sr
            WHERE sr.id = p_systeme_reperage_id;
            IF NOT FOUND THEN
                statut := 'REFERENCE_ABSENTE';
                details := jsonb_build_object('reference', 'systeme_reperage');
                RETURN NEXT;
                RETURN;
            END IF;
            IF v_systeme_troncon_id <> p_troncon_id THEN
                statut := 'CONFLIT_SYSTEME';
                details := jsonb_build_object(
                    'troncon_systeme', v_systeme_troncon_id
                );
                RETURN NEXT;
                RETURN;
            END IF;

            IF v_troncon_geometry IS NULL
               OR ST_IsEmpty(v_troncon_geometry)
               OR GeometryType(v_troncon_geometry) <> 'LINESTRING'
               OR ST_SRID(v_troncon_geometry) <> 3950
               OR NOT ST_IsValid(v_troncon_geometry)
               OR ST_Length(v_troncon_geometry) <= 0 THEN
                statut := 'GEOMETRIE_INVALIDE';
                details := jsonb_build_object('reference', 'troncon');
                RETURN NEXT;
                RETURN;
            END IF;
            v_longueur_m := ST_Length(v_troncon_geometry);

            SELECT
                COUNT(*)::integer,
                COUNT(*) FILTER (
                    WHERE b.geometry IS NULL
                       OR ST_IsEmpty(b.geometry)
                       OR GeometryType(b.geometry) <> 'POINT'
                       OR ST_SRID(b.geometry) <> 3950
                       OR NOT ST_IsValid(b.geometry)
                )::integer,
                COUNT(*) FILTER (
                    WHERE NOT sr.valid OR NOT l.valid OR NOT b.valid
                )::integer
            INTO
                v_nombre_bornes,
                v_nombre_geometries_invalides,
                v_nombre_references_invalides
            FROM public.systemes_reperage AS sr
            JOIN public.link_systemes_reperage_bornes AS l
              ON l.systeme_reperage_id = sr.id
            JOIN public.bornes_reperage AS b ON b.id = l.borne_id
            WHERE sr.id = p_systeme_reperage_id;

            details := jsonb_build_object(
                'nombre_bornes', v_nombre_bornes,
                'references_valid_false', v_nombre_references_invalides,
                'epsilon_numerique_m', v_epsilon
            );
            IF v_nombre_bornes = 0 THEN
                statut := 'SYSTEME_INCOMPLET';
                RETURN NEXT;
                RETURN;
            END IF;
            IF v_nombre_geometries_invalides > 0 THEN
                statut := 'GEOMETRIE_INVALIDE';
                details := details || jsonb_build_object(
                    'geometries_bornes_invalides', v_nombre_geometries_invalides
                );
                RETURN NEXT;
                RETURN;
            END IF;

            WITH references_projetees AS (
                SELECT
                    l.id,
                    l.valeur_pr,
                    ST_LineLocatePoint(v_troncon_geometry, b.geometry)
                        * v_longueur_m AS abscisse_m
                FROM public.link_systemes_reperage_bornes AS l
                JOIN public.bornes_reperage AS b ON b.id = l.borne_id
                WHERE l.systeme_reperage_id = p_systeme_reperage_id
            )
            SELECT EXISTS (
                SELECT 1
                FROM references_projetees AS a
                JOIN references_projetees AS b ON a.id < b.id
                WHERE abs(a.abscisse_m - b.abscisse_m) <= v_epsilon
            )
            INTO v_doublon_abscisse;
            IF v_doublon_abscisse THEN
                statut := 'AMBIGU';
                details := details || jsonb_build_object(
                    'cause', 'ABSCISSES_BORNES_DUPLIQUEES'
                );
                RETURN NEXT;
                RETURN;
            END IF;

            WITH references_projetees AS (
                SELECT
                    l.valeur_pr,
                    ST_LineLocatePoint(v_troncon_geometry, b.geometry)
                        * v_longueur_m AS abscisse_m
                FROM public.link_systemes_reperage_bornes AS l
                JOIN public.bornes_reperage AS b ON b.id = l.borne_id
                WHERE l.systeme_reperage_id = p_systeme_reperage_id
            )
            SELECT min(r.abscisse_m), max(r.abscisse_m)
            INTO v_abscisse_min, v_abscisse_max
            FROM references_projetees AS r;

            IF v_nombre_bornes = 1 THEN
                IF abs(p_abscisse_m - v_abscisse_min) <= v_epsilon THEN
                    SELECT l.valeur_pr
                    INTO pr
                    FROM public.link_systemes_reperage_bornes AS l
                    WHERE l.systeme_reperage_id = p_systeme_reperage_id;
                    statut := 'OK';
                ELSE
                    statut := 'SYSTEME_INCOMPLET';
                    details := details || jsonb_build_object(
                        'cause', 'ECHELLE_PR_A_UNE_BORNE'
                    );
                END IF;
                RETURN NEXT;
                RETURN;
            END IF;

            IF p_abscisse_m < v_abscisse_min OR p_abscisse_m > v_abscisse_max THEN
                statut := 'HORS_DOMAINE';
                details := details || jsonb_build_object(
                    'abscisse_min_m', v_abscisse_min,
                    'abscisse_max_m', v_abscisse_max
                );
                RETURN NEXT;
                RETURN;
            END IF;

            WITH references_projetees AS (
                SELECT
                    l.valeur_pr,
                    ST_LineLocatePoint(v_troncon_geometry, b.geometry)
                        * v_longueur_m AS abscisse_m
                FROM public.link_systemes_reperage_bornes AS l
                JOIN public.bornes_reperage AS b ON b.id = l.borne_id
                WHERE l.systeme_reperage_id = p_systeme_reperage_id
            )
            SELECT r.valeur_pr
            INTO v_pr_exact
            FROM references_projetees AS r
            WHERE abs(r.abscisse_m - p_abscisse_m) <= v_epsilon;
            IF FOUND THEN
                statut := 'OK';
                pr := v_pr_exact;
                RETURN NEXT;
                RETURN;
            END IF;

            WITH references_projetees AS (
                SELECT
                    l.valeur_pr,
                    ST_LineLocatePoint(v_troncon_geometry, b.geometry)
                        * v_longueur_m AS abscisse_m
                FROM public.link_systemes_reperage_bornes AS l
                JOIN public.bornes_reperage AS b ON b.id = l.borne_id
                WHERE l.systeme_reperage_id = p_systeme_reperage_id
            ), intervalles AS (
                SELECT
                    r.abscisse_m AS abscisse_0,
                    lead(r.abscisse_m) OVER (ORDER BY r.abscisse_m) AS abscisse_1,
                    r.valeur_pr AS pr_0,
                    lead(r.valeur_pr) OVER (ORDER BY r.abscisse_m) AS pr_1
                FROM references_projetees AS r
            )
            SELECT i.abscisse_0, i.abscisse_1, i.pr_0, i.pr_1
            INTO v_abscisse_0, v_abscisse_1, v_pr_0, v_pr_1
            FROM intervalles AS i
            WHERE p_abscisse_m > i.abscisse_0
              AND p_abscisse_m < i.abscisse_1;

            IF NOT FOUND THEN
                statut := 'SYSTEME_INCOMPLET';
                details := details || jsonb_build_object(
                    'cause', 'INTERVALLE_SPATIAL_INTROUVABLE'
                );
                RETURN NEXT;
                RETURN;
            END IF;

            pr := v_pr_0
                + ((p_abscisse_m - v_abscisse_0)
                    / (v_abscisse_1 - v_abscisse_0))::numeric
                  * (v_pr_1 - v_pr_0);
            statut := 'OK';
            RETURN NEXT;
        END
        $function$
    """,
    "xy_vers_reperage": f"""
        CREATE OR REPLACE FUNCTION public.xy_vers_reperage(
            p_troncon_id UUID,
            p_systeme_reperage_id UUID,
            p_point_xy geometry
        )
        RETURNS TABLE (
            statut TEXT,
            statut_pr TEXT,
            troncon_id UUID,
            systeme_reperage_id UUID,
            point_source geometry(Point, 3950),
            point_projete geometry(Point, 3950),
            distance_axe_m DOUBLE PRECISION,
            abscisse_m DOUBLE PRECISION,
            borne_id UUID,
            abscisse_borne_m DOUBLE PRECISION,
            offset_borne_m DOUBLE PRECISION,
            distance_borne_m DOUBLE PRECISION,
            position_relative TEXT,
            pr NUMERIC,
            details JSONB
        )
        LANGUAGE plpgsql
        STABLE
        PARALLEL SAFE
        SET search_path = pg_catalog, public
        AS $function$
        DECLARE
            v_troncon_geometry geometry;
            v_systeme_troncon_id UUID;
            v_longueur_m DOUBLE PRECISION;
            v_fraction DOUBLE PRECISION;
            v_nombre_bornes INTEGER;
            v_nombre_geometries_invalides INTEGER;
            v_nombre_ex_aequo INTEGER;
            v_ecart_min DOUBLE PRECISION;
            v_systeme_valid BOOLEAN;
            v_borne_valid BOOLEAN;
            v_lien_valid BOOLEAN;
            v_pr_details JSONB;
            v_epsilon CONSTANT DOUBLE PRECISION := {NUMERIC_EPSILON_METERS};
        BEGIN
            troncon_id := p_troncon_id;
            systeme_reperage_id := p_systeme_reperage_id;
            statut_pr := NULL;
            details := jsonb_build_object('epsilon_numerique_m', v_epsilon);

            IF p_troncon_id IS NULL OR p_systeme_reperage_id IS NULL THEN
                statut := 'REFERENCE_ABSENTE';
                details := details || jsonb_build_object(
                    'message', 'Tronçon et système sont obligatoires.'
                );
                RETURN NEXT;
                RETURN;
            END IF;

            SELECT t.geometry
            INTO v_troncon_geometry
            FROM public.troncons AS t
            WHERE t.id = p_troncon_id;
            IF NOT FOUND THEN
                statut := 'REFERENCE_ABSENTE';
                details := details || jsonb_build_object('reference', 'troncon');
                RETURN NEXT;
                RETURN;
            END IF;

            SELECT sr.troncon_id, sr.valid
            INTO v_systeme_troncon_id, v_systeme_valid
            FROM public.systemes_reperage AS sr
            WHERE sr.id = p_systeme_reperage_id;
            IF NOT FOUND THEN
                statut := 'REFERENCE_ABSENTE';
                details := details || jsonb_build_object(
                    'reference', 'systeme_reperage'
                );
                RETURN NEXT;
                RETURN;
            END IF;
            IF v_systeme_troncon_id <> p_troncon_id THEN
                statut := 'CONFLIT_SYSTEME';
                details := details || jsonb_build_object(
                    'troncon_systeme', v_systeme_troncon_id
                );
                RETURN NEXT;
                RETURN;
            END IF;

            IF v_troncon_geometry IS NULL
               OR ST_IsEmpty(v_troncon_geometry)
               OR GeometryType(v_troncon_geometry) <> 'LINESTRING'
               OR ST_SRID(v_troncon_geometry) <> 3950
               OR NOT ST_IsValid(v_troncon_geometry)
               OR ST_Length(v_troncon_geometry) <= 0 THEN
                statut := 'GEOMETRIE_INVALIDE';
                details := details || jsonb_build_object('reference', 'troncon');
                RETURN NEXT;
                RETURN;
            END IF;
            IF p_point_xy IS NULL
               OR ST_IsEmpty(p_point_xy)
               OR GeometryType(p_point_xy) <> 'POINT'
               OR ST_NDims(p_point_xy) <> 2
               OR ST_SRID(p_point_xy) <> 3950
               OR NOT ST_IsValid(p_point_xy) THEN
                statut := 'GEOMETRIE_INVALIDE';
                details := details || jsonb_build_object(
                    'reference', 'point_xy',
                    'type_recu', CASE WHEN p_point_xy IS NULL THEN NULL
                        ELSE GeometryType(p_point_xy) END,
                    'srid_recu', CASE WHEN p_point_xy IS NULL THEN NULL
                        ELSE ST_SRID(p_point_xy) END
                );
                RETURN NEXT;
                RETURN;
            END IF;

            point_source := p_point_xy::geometry(Point, 3950);
            v_longueur_m := ST_Length(v_troncon_geometry);
            v_fraction := ST_LineLocatePoint(v_troncon_geometry, p_point_xy);
            abscisse_m := v_fraction * v_longueur_m;
            point_projete := ST_LineInterpolatePoint(
                v_troncon_geometry, v_fraction
            )::geometry(Point, 3950);
            distance_axe_m := ST_Distance(p_point_xy, point_projete);

            SELECT
                COUNT(*)::integer,
                COUNT(*) FILTER (
                    WHERE b.geometry IS NULL
                       OR ST_IsEmpty(b.geometry)
                       OR GeometryType(b.geometry) <> 'POINT'
                       OR ST_SRID(b.geometry) <> 3950
                       OR NOT ST_IsValid(b.geometry)
                )::integer
            INTO v_nombre_bornes, v_nombre_geometries_invalides
            FROM public.link_systemes_reperage_bornes AS l
            JOIN public.bornes_reperage AS b ON b.id = l.borne_id
            WHERE l.systeme_reperage_id = p_systeme_reperage_id;

            details := details || jsonb_build_object(
                'nombre_bornes', v_nombre_bornes,
                'systeme_valid', v_systeme_valid
            );
            IF v_nombre_bornes = 0 THEN
                statut := 'SYSTEME_INCOMPLET';
                statut_pr := 'SYSTEME_INCOMPLET';
                RETURN NEXT;
                RETURN;
            END IF;
            IF v_nombre_geometries_invalides > 0 THEN
                statut := 'GEOMETRIE_INVALIDE';
                statut_pr := 'GEOMETRIE_INVALIDE';
                details := details || jsonb_build_object(
                    'geometries_bornes_invalides', v_nombre_geometries_invalides
                );
                RETURN NEXT;
                RETURN;
            END IF;

            WITH references_projetees AS (
                SELECT
                    l.borne_id,
                    l.valid AS lien_valid,
                    b.valid AS borne_valid,
                    ST_LineLocatePoint(v_troncon_geometry, b.geometry)
                        * v_longueur_m AS abscisse_borne,
                    abs(
                        abscisse_m
                        - ST_LineLocatePoint(v_troncon_geometry, b.geometry)
                          * v_longueur_m
                    ) AS ecart
                FROM public.link_systemes_reperage_bornes AS l
                JOIN public.bornes_reperage AS b ON b.id = l.borne_id
                WHERE l.systeme_reperage_id = p_systeme_reperage_id
            ), minimum AS (
                SELECT min(r.ecart) AS ecart FROM references_projetees AS r
            )
            SELECT m.ecart, COUNT(*)::integer
            INTO v_ecart_min, v_nombre_ex_aequo
            FROM references_projetees AS r
            CROSS JOIN minimum AS m
            WHERE abs(r.ecart - m.ecart) <= v_epsilon
            GROUP BY m.ecart;

            SELECT h.statut, h.pr, h.details
            INTO statut_pr, pr, v_pr_details
            FROM public._reperage_pr_depuis_abscisse(
                p_troncon_id, p_systeme_reperage_id, abscisse_m
            ) AS h;
            details := details || jsonb_build_object('pr', v_pr_details);

            IF v_nombre_ex_aequo > 1 THEN
                statut := 'AMBIGU';
                details := details || jsonb_build_object(
                    'cause', 'BORNES_EQUIDISTANTES',
                    'nombre_ex_aequo', v_nombre_ex_aequo,
                    'ecart_min_m', v_ecart_min
                );
                RETURN NEXT;
                RETURN;
            END IF;

            WITH references_projetees AS (
                SELECT
                    l.borne_id,
                    l.valid AS lien_valid,
                    b.valid AS borne_valid,
                    ST_LineLocatePoint(v_troncon_geometry, b.geometry)
                        * v_longueur_m AS abscisse_borne,
                    abs(
                        abscisse_m
                        - ST_LineLocatePoint(v_troncon_geometry, b.geometry)
                          * v_longueur_m
                    ) AS ecart
                FROM public.link_systemes_reperage_bornes AS l
                JOIN public.bornes_reperage AS b ON b.id = l.borne_id
                WHERE l.systeme_reperage_id = p_systeme_reperage_id
            )
            SELECT
                r.borne_id, r.abscisse_borne, r.borne_valid, r.lien_valid
            INTO borne_id, abscisse_borne_m, v_borne_valid, v_lien_valid
            FROM references_projetees AS r
            WHERE abs(r.ecart - v_ecart_min) <= v_epsilon;

            offset_borne_m := abscisse_m - abscisse_borne_m;
            distance_borne_m := abs(offset_borne_m);
            position_relative := CASE
                WHEN abs(offset_borne_m) <= v_epsilon THEN 'SUR_BORNE'
                WHEN offset_borne_m < 0 THEN 'AVANT_BORNE'
                ELSE 'APRES_BORNE'
            END;
            details := details || jsonb_build_object(
                'borne_valid', v_borne_valid,
                'lien_systeme_borne_valid', v_lien_valid
            );
            statut := 'OK';
            RETURN NEXT;
        END
        $function$
    """,
    "borne_offset_vers_xy": f"""
        CREATE OR REPLACE FUNCTION public.borne_offset_vers_xy(
            p_troncon_id UUID,
            p_systeme_reperage_id UUID,
            p_borne_id UUID,
            p_offset_m DOUBLE PRECISION
        )
        RETURNS TABLE (
            statut TEXT,
            statut_pr TEXT,
            troncon_id UUID,
            systeme_reperage_id UUID,
            borne_id UUID,
            point_xy geometry(Point, 3950),
            abscisse_m DOUBLE PRECISION,
            abscisse_borne_m DOUBLE PRECISION,
            offset_m DOUBLE PRECISION,
            distance_m DOUBLE PRECISION,
            position_relative TEXT,
            pr NUMERIC,
            details JSONB
        )
        LANGUAGE plpgsql
        STABLE
        PARALLEL SAFE
        SET search_path = pg_catalog, public
        AS $function$
        DECLARE
            v_troncon_geometry geometry;
            v_borne_geometry geometry;
            v_systeme_troncon_id UUID;
            v_longueur_m DOUBLE PRECISION;
            v_systeme_valid BOOLEAN;
            v_borne_valid BOOLEAN;
            v_lien_valid BOOLEAN;
            v_pr_details JSONB;
            v_epsilon CONSTANT DOUBLE PRECISION := {NUMERIC_EPSILON_METERS};
        BEGIN
            troncon_id := p_troncon_id;
            systeme_reperage_id := p_systeme_reperage_id;
            borne_id := p_borne_id;
            offset_m := p_offset_m;
            distance_m := abs(p_offset_m);
            position_relative := CASE
                WHEN p_offset_m IS NULL THEN NULL
                WHEN abs(p_offset_m) <= v_epsilon THEN 'SUR_BORNE'
                WHEN p_offset_m < 0 THEN 'AVANT_BORNE'
                ELSE 'APRES_BORNE'
            END;
            details := jsonb_build_object('epsilon_numerique_m', v_epsilon);

            IF p_troncon_id IS NULL OR p_systeme_reperage_id IS NULL
               OR p_borne_id IS NULL OR p_offset_m IS NULL
               OR p_offset_m::text IN ('NaN', 'Infinity', '-Infinity') THEN
                statut := 'REFERENCE_ABSENTE';
                details := details || jsonb_build_object(
                    'message', 'Tronçon, système, borne et offset sont obligatoires.'
                );
                RETURN NEXT;
                RETURN;
            END IF;

            SELECT t.geometry
            INTO v_troncon_geometry
            FROM public.troncons AS t
            WHERE t.id = p_troncon_id;
            IF NOT FOUND THEN
                statut := 'REFERENCE_ABSENTE';
                details := details || jsonb_build_object('reference', 'troncon');
                RETURN NEXT;
                RETURN;
            END IF;

            SELECT sr.troncon_id, sr.valid
            INTO v_systeme_troncon_id, v_systeme_valid
            FROM public.systemes_reperage AS sr
            WHERE sr.id = p_systeme_reperage_id;
            IF NOT FOUND THEN
                statut := 'REFERENCE_ABSENTE';
                details := details || jsonb_build_object(
                    'reference', 'systeme_reperage'
                );
                RETURN NEXT;
                RETURN;
            END IF;
            IF v_systeme_troncon_id <> p_troncon_id THEN
                statut := 'CONFLIT_SYSTEME';
                details := details || jsonb_build_object(
                    'troncon_systeme', v_systeme_troncon_id
                );
                RETURN NEXT;
                RETURN;
            END IF;

            SELECT b.geometry, b.valid
            INTO v_borne_geometry, v_borne_valid
            FROM public.bornes_reperage AS b
            WHERE b.id = p_borne_id;
            IF NOT FOUND THEN
                statut := 'REFERENCE_ABSENTE';
                details := details || jsonb_build_object('reference', 'borne');
                RETURN NEXT;
                RETURN;
            END IF;

            SELECT l.valid
            INTO v_lien_valid
            FROM public.link_systemes_reperage_bornes AS l
            WHERE l.systeme_reperage_id = p_systeme_reperage_id
              AND l.borne_id = p_borne_id;
            IF NOT FOUND THEN
                statut := 'CONFLIT_SYSTEME';
                details := details || jsonb_build_object(
                    'cause', 'BORNE_ABSENTE_DU_SYSTEME'
                );
                RETURN NEXT;
                RETURN;
            END IF;

            IF v_troncon_geometry IS NULL
               OR ST_IsEmpty(v_troncon_geometry)
               OR GeometryType(v_troncon_geometry) <> 'LINESTRING'
               OR ST_SRID(v_troncon_geometry) <> 3950
               OR NOT ST_IsValid(v_troncon_geometry)
               OR ST_Length(v_troncon_geometry) <= 0 THEN
                statut := 'GEOMETRIE_INVALIDE';
                details := details || jsonb_build_object('reference', 'troncon');
                RETURN NEXT;
                RETURN;
            END IF;
            IF v_borne_geometry IS NULL
               OR ST_IsEmpty(v_borne_geometry)
               OR GeometryType(v_borne_geometry) <> 'POINT'
               OR ST_SRID(v_borne_geometry) <> 3950
               OR NOT ST_IsValid(v_borne_geometry) THEN
                statut := 'GEOMETRIE_INVALIDE';
                details := details || jsonb_build_object('reference', 'borne');
                RETURN NEXT;
                RETURN;
            END IF;

            v_longueur_m := ST_Length(v_troncon_geometry);
            abscisse_borne_m := ST_LineLocatePoint(
                v_troncon_geometry, v_borne_geometry
            ) * v_longueur_m;
            abscisse_m := abscisse_borne_m + p_offset_m;
            details := details || jsonb_build_object(
                'longueur_troncon_m', v_longueur_m,
                'systeme_valid', v_systeme_valid,
                'borne_valid', v_borne_valid,
                'lien_systeme_borne_valid', v_lien_valid
            );

            IF abscisse_m < 0 OR abscisse_m > v_longueur_m THEN
                statut := 'HORS_DOMAINE';
                statut_pr := NULL;
                RETURN NEXT;
                RETURN;
            END IF;

            point_xy := ST_LineInterpolatePoint(
                v_troncon_geometry, abscisse_m / v_longueur_m
            )::geometry(Point, 3950);
            SELECT h.statut, h.pr, h.details
            INTO statut_pr, pr, v_pr_details
            FROM public._reperage_pr_depuis_abscisse(
                p_troncon_id, p_systeme_reperage_id, abscisse_m
            ) AS h;
            details := details || jsonb_build_object('pr', v_pr_details);
            statut := 'OK';
            RETURN NEXT;
        END
        $function$
    """,
    "pr_vers_xy": f"""
        CREATE OR REPLACE FUNCTION public.pr_vers_xy(
            p_troncon_id UUID,
            p_systeme_reperage_id UUID,
            p_pr NUMERIC
        )
        RETURNS TABLE (
            statut TEXT,
            troncon_id UUID,
            systeme_reperage_id UUID,
            pr_demande NUMERIC,
            point_xy geometry(Point, 3950),
            abscisse_m DOUBLE PRECISION,
            borne_0_id UUID,
            borne_1_id UUID,
            abscisse_0_m DOUBLE PRECISION,
            abscisse_1_m DOUBLE PRECISION,
            pr_0 NUMERIC,
            pr_1 NUMERIC,
            details JSONB
        )
        LANGUAGE plpgsql
        STABLE
        PARALLEL SAFE
        SET search_path = pg_catalog, public
        AS $function$
        DECLARE
            v_troncon_geometry geometry;
            v_systeme_troncon_id UUID;
            v_longueur_m DOUBLE PRECISION;
            v_nombre_bornes INTEGER;
            v_nombre_geometries_invalides INTEGER;
            v_nombre_references_invalides INTEGER;
            v_pr_min NUMERIC;
            v_pr_max NUMERIC;
            v_sens_min INTEGER;
            v_sens_max INTEGER;
            v_doublon_abscisse BOOLEAN;
            v_doublon_pr BOOLEAN;
            v_systeme_valid BOOLEAN;
            v_borne_exacte UUID;
            v_abscisse_exacte DOUBLE PRECISION;
            v_epsilon CONSTANT DOUBLE PRECISION := {NUMERIC_EPSILON_METERS};
        BEGIN
            troncon_id := p_troncon_id;
            systeme_reperage_id := p_systeme_reperage_id;
            pr_demande := p_pr;
            details := jsonb_build_object('epsilon_numerique_m', v_epsilon);

            IF p_troncon_id IS NULL OR p_systeme_reperage_id IS NULL
               OR p_pr IS NULL
               OR p_pr::text IN ('NaN', 'Infinity', '-Infinity') THEN
                statut := 'REFERENCE_ABSENTE';
                details := details || jsonb_build_object(
                    'message', 'Tronçon, système et PR sont obligatoires.'
                );
                RETURN NEXT;
                RETURN;
            END IF;

            SELECT t.geometry
            INTO v_troncon_geometry
            FROM public.troncons AS t
            WHERE t.id = p_troncon_id;
            IF NOT FOUND THEN
                statut := 'REFERENCE_ABSENTE';
                details := details || jsonb_build_object('reference', 'troncon');
                RETURN NEXT;
                RETURN;
            END IF;

            SELECT sr.troncon_id, sr.valid
            INTO v_systeme_troncon_id, v_systeme_valid
            FROM public.systemes_reperage AS sr
            WHERE sr.id = p_systeme_reperage_id;
            IF NOT FOUND THEN
                statut := 'REFERENCE_ABSENTE';
                details := details || jsonb_build_object(
                    'reference', 'systeme_reperage'
                );
                RETURN NEXT;
                RETURN;
            END IF;
            IF v_systeme_troncon_id <> p_troncon_id THEN
                statut := 'CONFLIT_SYSTEME';
                details := details || jsonb_build_object(
                    'troncon_systeme', v_systeme_troncon_id
                );
                RETURN NEXT;
                RETURN;
            END IF;

            IF v_troncon_geometry IS NULL
               OR ST_IsEmpty(v_troncon_geometry)
               OR GeometryType(v_troncon_geometry) <> 'LINESTRING'
               OR ST_SRID(v_troncon_geometry) <> 3950
               OR NOT ST_IsValid(v_troncon_geometry)
               OR ST_Length(v_troncon_geometry) <= 0 THEN
                statut := 'GEOMETRIE_INVALIDE';
                details := details || jsonb_build_object('reference', 'troncon');
                RETURN NEXT;
                RETURN;
            END IF;
            v_longueur_m := ST_Length(v_troncon_geometry);

            SELECT
                COUNT(*)::integer,
                COUNT(*) FILTER (
                    WHERE b.geometry IS NULL
                       OR ST_IsEmpty(b.geometry)
                       OR GeometryType(b.geometry) <> 'POINT'
                       OR ST_SRID(b.geometry) <> 3950
                       OR NOT ST_IsValid(b.geometry)
                )::integer,
                COUNT(*) FILTER (
                    WHERE NOT sr.valid OR NOT l.valid OR NOT b.valid
                )::integer
            INTO
                v_nombre_bornes,
                v_nombre_geometries_invalides,
                v_nombre_references_invalides
            FROM public.systemes_reperage AS sr
            JOIN public.link_systemes_reperage_bornes AS l
              ON l.systeme_reperage_id = sr.id
            JOIN public.bornes_reperage AS b ON b.id = l.borne_id
            WHERE sr.id = p_systeme_reperage_id;
            details := details || jsonb_build_object(
                'nombre_bornes', v_nombre_bornes,
                'systeme_valid', v_systeme_valid,
                'references_valid_false', v_nombre_references_invalides
            );

            IF v_nombre_bornes = 0 THEN
                statut := 'SYSTEME_INCOMPLET';
                RETURN NEXT;
                RETURN;
            END IF;
            IF v_nombre_geometries_invalides > 0 THEN
                statut := 'GEOMETRIE_INVALIDE';
                details := details || jsonb_build_object(
                    'geometries_bornes_invalides', v_nombre_geometries_invalides
                );
                RETURN NEXT;
                RETURN;
            END IF;

            WITH references_projetees AS (
                SELECT
                    l.id,
                    l.borne_id,
                    l.valeur_pr,
                    ST_LineLocatePoint(v_troncon_geometry, b.geometry)
                        * v_longueur_m AS abscisse_m
                FROM public.link_systemes_reperage_bornes AS l
                JOIN public.bornes_reperage AS b ON b.id = l.borne_id
                WHERE l.systeme_reperage_id = p_systeme_reperage_id
            )
            SELECT
                EXISTS (
                    SELECT 1
                    FROM references_projetees AS a
                    JOIN references_projetees AS b ON a.id < b.id
                    WHERE abs(a.abscisse_m - b.abscisse_m) <= v_epsilon
                ),
                EXISTS (
                    SELECT 1
                    FROM references_projetees AS r
                    GROUP BY r.valeur_pr
                    HAVING COUNT(*) > 1
                ),
                min(r.valeur_pr),
                max(r.valeur_pr)
            INTO v_doublon_abscisse, v_doublon_pr, v_pr_min, v_pr_max
            FROM references_projetees AS r;

            IF v_doublon_abscisse THEN
                statut := 'AMBIGU';
                details := details || jsonb_build_object(
                    'cause', 'ABSCISSES_BORNES_DUPLIQUEES'
                );
                RETURN NEXT;
                RETURN;
            END IF;
            IF v_doublon_pr THEN
                statut := 'AMBIGU';
                details := details || jsonb_build_object(
                    'cause', 'PR_DUPLIQUES'
                );
                RETURN NEXT;
                RETURN;
            END IF;

            IF v_nombre_bornes = 1 THEN
                SELECT l.borne_id,
                       ST_LineLocatePoint(v_troncon_geometry, b.geometry)
                           * v_longueur_m
                INTO v_borne_exacte, v_abscisse_exacte
                FROM public.link_systemes_reperage_bornes AS l
                JOIN public.bornes_reperage AS b ON b.id = l.borne_id
                WHERE l.systeme_reperage_id = p_systeme_reperage_id
                  AND l.valeur_pr = p_pr;
                IF FOUND THEN
                    borne_0_id := v_borne_exacte;
                    borne_1_id := v_borne_exacte;
                    abscisse_0_m := v_abscisse_exacte;
                    abscisse_1_m := v_abscisse_exacte;
                    pr_0 := p_pr;
                    pr_1 := p_pr;
                    abscisse_m := v_abscisse_exacte;
                    point_xy := ST_LineInterpolatePoint(
                        v_troncon_geometry, abscisse_m / v_longueur_m
                    )::geometry(Point, 3950);
                    statut := 'OK';
                ELSE
                    statut := 'SYSTEME_INCOMPLET';
                    details := details || jsonb_build_object(
                        'cause', 'ECHELLE_PR_A_UNE_BORNE'
                    );
                END IF;
                RETURN NEXT;
                RETURN;
            END IF;

            WITH references_projetees AS (
                SELECT
                    l.valeur_pr,
                    ST_LineLocatePoint(v_troncon_geometry, b.geometry)
                        * v_longueur_m AS abscisse_m
                FROM public.link_systemes_reperage_bornes AS l
                JOIN public.bornes_reperage AS b ON b.id = l.borne_id
                WHERE l.systeme_reperage_id = p_systeme_reperage_id
            ), variations AS (
                SELECT sign(
                    lead(r.valeur_pr) OVER (ORDER BY r.abscisse_m)
                    - r.valeur_pr
                )::integer AS sens
                FROM references_projetees AS r
            )
            SELECT min(v.sens), max(v.sens)
            INTO v_sens_min, v_sens_max
            FROM variations AS v
            WHERE v.sens IS NOT NULL;
            IF v_sens_min <> v_sens_max OR v_sens_min = 0 THEN
                statut := 'AMBIGU';
                details := details || jsonb_build_object(
                    'cause', 'RELATION_PR_NON_MONOTONE'
                );
                RETURN NEXT;
                RETURN;
            END IF;

            WITH references_projetees AS (
                SELECT
                    l.borne_id,
                    l.valeur_pr,
                    ST_LineLocatePoint(v_troncon_geometry, b.geometry)
                        * v_longueur_m AS abscisse_m
                FROM public.link_systemes_reperage_bornes AS l
                JOIN public.bornes_reperage AS b ON b.id = l.borne_id
                WHERE l.systeme_reperage_id = p_systeme_reperage_id
            )
            SELECT r.borne_id, r.abscisse_m
            INTO v_borne_exacte, v_abscisse_exacte
            FROM references_projetees AS r
            WHERE r.valeur_pr = p_pr;
            IF FOUND THEN
                borne_0_id := v_borne_exacte;
                borne_1_id := v_borne_exacte;
                abscisse_0_m := v_abscisse_exacte;
                abscisse_1_m := v_abscisse_exacte;
                pr_0 := p_pr;
                pr_1 := p_pr;
                abscisse_m := v_abscisse_exacte;
                point_xy := ST_LineInterpolatePoint(
                    v_troncon_geometry, abscisse_m / v_longueur_m
                )::geometry(Point, 3950);
                statut := 'OK';
                RETURN NEXT;
                RETURN;
            END IF;

            IF p_pr < v_pr_min OR p_pr > v_pr_max THEN
                statut := 'HORS_DOMAINE';
                details := details || jsonb_build_object(
                    'pr_min', v_pr_min,
                    'pr_max', v_pr_max
                );
                RETURN NEXT;
                RETURN;
            END IF;

            WITH references_projetees AS (
                SELECT
                    l.borne_id,
                    l.valeur_pr,
                    ST_LineLocatePoint(v_troncon_geometry, b.geometry)
                        * v_longueur_m AS abscisse_m
                FROM public.link_systemes_reperage_bornes AS l
                JOIN public.bornes_reperage AS b ON b.id = l.borne_id
                WHERE l.systeme_reperage_id = p_systeme_reperage_id
            ), intervalles AS (
                SELECT
                    r.borne_id AS borne_0,
                    lead(r.borne_id) OVER (ORDER BY r.abscisse_m) AS borne_1,
                    r.abscisse_m AS abscisse_0,
                    lead(r.abscisse_m) OVER (ORDER BY r.abscisse_m) AS abscisse_1,
                    r.valeur_pr AS valeur_pr_0,
                    lead(r.valeur_pr) OVER (ORDER BY r.abscisse_m) AS valeur_pr_1
                FROM references_projetees AS r
            )
            SELECT
                i.borne_0, i.borne_1,
                i.abscisse_0, i.abscisse_1,
                i.valeur_pr_0, i.valeur_pr_1
            INTO
                borne_0_id, borne_1_id,
                abscisse_0_m, abscisse_1_m,
                pr_0, pr_1
            FROM intervalles AS i
            WHERE p_pr > least(i.valeur_pr_0, i.valeur_pr_1)
              AND p_pr < greatest(i.valeur_pr_0, i.valeur_pr_1);
            IF NOT FOUND THEN
                statut := 'SYSTEME_INCOMPLET';
                details := details || jsonb_build_object(
                    'cause', 'INTERVALLE_PR_INTROUVABLE'
                );
                RETURN NEXT;
                RETURN;
            END IF;

            abscisse_m := abscisse_0_m
                + ((p_pr - pr_0) / (pr_1 - pr_0))::double precision
                  * (abscisse_1_m - abscisse_0_m);
            point_xy := ST_LineInterpolatePoint(
                v_troncon_geometry, abscisse_m / v_longueur_m
            )::geometry(Point, 3950);
            statut := 'OK';
            RETURN NEXT;
        END
        $function$
    """,
}


REPERAGE_FUNCTION_DDL = tuple(
    statement.strip() for statement in FUNCTION_DEFINITIONS.values()
)
