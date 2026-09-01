"""Localisation opérationnelle des désordres par repérage linéaire.

Seuls les désordres Point/LineString liés à exactement un tronçon sont
repérables. La géométrie reste la représentation réelle ; les opérations SQL
garantissent l'atomicité des deux sens d'édition.
"""

TABLE_DEFINITIONS = {
    "desordre_localisations_reperage": """
        CREATE TABLE IF NOT EXISTS public.desordre_localisations_reperage (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            desordre_id UUID NOT NULL,
            troncon_id UUID NOT NULL,
            systeme_reperage_id UUID NOT NULL,
            borne_debut_id UUID NOT NULL,
            distance_debut_m DOUBLE PRECISION NOT NULL,
            position_debut_relative TEXT NOT NULL,
            offset_debut_m DOUBLE PRECISION GENERATED ALWAYS AS (
                CASE position_debut_relative
                    WHEN 'AVANT_BORNE' THEN -distance_debut_m
                    WHEN 'SUR_BORNE' THEN 0.0
                    WHEN 'APRES_BORNE' THEN distance_debut_m
                    ELSE NULL
                END
            ) STORED,
            pr_debut NUMERIC NULL,
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
            pr_fin NUMERIC NULL,
            valid BOOLEAN NOT NULL DEFAULT true,
            CONSTRAINT desordre_localisations_reperage_desordre_unique
                UNIQUE (desordre_id),
            CONSTRAINT desordre_localisations_reperage_desordres_fk
                FOREIGN KEY (desordre_id) REFERENCES public.desordres (id),
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
            CONSTRAINT desordre_localisations_reperage_distance_debut_check
                CHECK (distance_debut_m >= 0),
            CONSTRAINT desordre_localisations_reperage_distance_fin_check
                CHECK (distance_fin_m IS NULL OR distance_fin_m >= 0),
            CONSTRAINT desordre_localisations_reperage_position_debut_check
                CHECK (position_debut_relative IN (
                    'AVANT_BORNE', 'SUR_BORNE', 'APRES_BORNE'
                )),
            CONSTRAINT desordre_localisations_reperage_position_fin_check
                CHECK (position_fin_relative IS NULL OR
                    position_fin_relative IN (
                        'AVANT_BORNE', 'SUR_BORNE', 'APRES_BORNE'
                    )),
            CONSTRAINT desordre_localisations_reperage_fin_complete_check
                CHECK (
                    num_nonnulls(
                        borne_fin_id, distance_fin_m, position_fin_relative
                    ) IN (0, 3)
                    AND (position_fin_relative <> 'SUR_BORNE'
                         OR distance_fin_m = 0)
                ),
            CONSTRAINT desordre_localisations_reperage_debut_zero_check
                CHECK (position_debut_relative <> 'SUR_BORNE'
                       OR distance_debut_m = 0)
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

FUNCTION_DEFINITIONS = {
    "synchroniser_desordre_reperage": """
        CREATE OR REPLACE FUNCTION public.synchroniser_desordre_reperage(
            p_desordre_id UUID,
            p_systeme_reperage_id UUID DEFAULT NULL
        ) RETURNS TEXT
        LANGUAGE plpgsql VOLATILE SET search_path = pg_catalog, public
        AS $function$
        DECLARE
            v_nombre_troncons INTEGER;
            v_troncon_id UUID;
            v_systeme_id UUID;
            v_geometry geometry;
            v_type TEXT;
            v_debut RECORD;
            v_fin RECORD;
            v_fin_borne_id UUID;
            v_fin_distance_m DOUBLE PRECISION;
            v_fin_position_relative TEXT;
            v_fin_pr NUMERIC;
            v_guard TEXT;
        BEGIN
            SELECT count(*)::integer, min(l.troncon_id::text)::uuid
            INTO v_nombre_troncons, v_troncon_id
            FROM public.link_desordres_troncons AS l
            WHERE l.desordre_id = p_desordre_id;
            SELECT d.geometry, GeometryType(d.geometry)
            INTO v_geometry, v_type
            FROM public.desordres AS d WHERE d.id = p_desordre_id;
            IF NOT FOUND THEN RETURN 'REFERENCE_ABSENTE'; END IF;

            IF v_nombre_troncons <> 1 OR v_geometry IS NULL
               OR v_type NOT IN ('POINT', 'LINESTRING') THEN
                DELETE FROM public.desordre_localisations_reperage
                WHERE desordre_id = p_desordre_id;
                RETURN CASE
                    WHEN v_nombre_troncons = 0 THEN 'AUCUN_TRONCON'
                    WHEN v_nombre_troncons > 1 THEN 'PLUSIEURS_TRONCONS'
                    ELSE 'TYPE_NON_REPERABLE'
                END;
            END IF;

            SELECT sr.id INTO v_systeme_id
            FROM public.systemes_reperage AS sr
            WHERE sr.id = p_systeme_reperage_id
              AND sr.troncon_id = v_troncon_id;
            IF v_systeme_id IS NULL THEN
                SELECT l.systeme_reperage_id INTO v_systeme_id
                FROM public.desordre_localisations_reperage AS l
                JOIN public.systemes_reperage AS sr
                  ON sr.id = l.systeme_reperage_id
                 AND sr.troncon_id = v_troncon_id
                WHERE l.desordre_id = p_desordre_id;
            END IF;
            IF v_systeme_id IS NULL THEN
                SELECT t.systeme_reperage_defaut_id INTO v_systeme_id
                FROM public.troncons AS t WHERE t.id = v_troncon_id;
            END IF;
            IF v_systeme_id IS NULL THEN
                DELETE FROM public.desordre_localisations_reperage
                WHERE desordre_id = p_desordre_id;
                RETURN 'SYSTEME_ABSENT';
            END IF;

            SELECT conversion.* INTO v_debut
            FROM public.xy_vers_reperage(
                v_troncon_id, v_systeme_id,
                CASE v_type WHEN 'POINT' THEN v_geometry
                    ELSE ST_StartPoint(v_geometry) END
            ) AS conversion;
            IF v_debut.statut <> 'OK' OR v_debut.borne_id IS NULL THEN
                DELETE FROM public.desordre_localisations_reperage
                WHERE desordre_id = p_desordre_id;
                RETURN v_debut.statut;
            END IF;
            IF v_type = 'LINESTRING' THEN
                SELECT conversion.* INTO v_fin
                FROM public.xy_vers_reperage(
                    v_troncon_id, v_systeme_id, ST_EndPoint(v_geometry)
                ) AS conversion;
                IF v_fin.statut <> 'OK' OR v_fin.borne_id IS NULL THEN
                    DELETE FROM public.desordre_localisations_reperage
                    WHERE desordre_id = p_desordre_id;
                    RETURN v_fin.statut;
                END IF;
                v_fin_borne_id := v_fin.borne_id;
                v_fin_distance_m := v_fin.distance_borne_m;
                v_fin_position_relative := v_fin.position_relative;
                v_fin_pr := v_fin.pr;
            END IF;

            v_guard := current_setting('sirs.reperage_guard', true);
            PERFORM set_config('sirs.reperage_guard', 'GEOMETRIE', true);
            INSERT INTO public.desordre_localisations_reperage (
                desordre_id, troncon_id, systeme_reperage_id,
                borne_debut_id, distance_debut_m, position_debut_relative,
                pr_debut, borne_fin_id, distance_fin_m,
                position_fin_relative, pr_fin, valid
            ) VALUES (
                p_desordre_id, v_troncon_id, v_systeme_id,
                v_debut.borne_id, v_debut.distance_borne_m,
                v_debut.position_relative, v_debut.pr,
                v_fin_borne_id, v_fin_distance_m,
                v_fin_position_relative, v_fin_pr, true
            )
            ON CONFLICT (desordre_id) DO UPDATE SET
                troncon_id = EXCLUDED.troncon_id,
                systeme_reperage_id = EXCLUDED.systeme_reperage_id,
                borne_debut_id = EXCLUDED.borne_debut_id,
                distance_debut_m = EXCLUDED.distance_debut_m,
                position_debut_relative = EXCLUDED.position_debut_relative,
                pr_debut = EXCLUDED.pr_debut,
                borne_fin_id = EXCLUDED.borne_fin_id,
                distance_fin_m = EXCLUDED.distance_fin_m,
                position_fin_relative = EXCLUDED.position_fin_relative,
                pr_fin = EXCLUDED.pr_fin;
            PERFORM set_config('sirs.reperage_guard', coalesce(v_guard, ''), true);
            RETURN 'OK';
        END
        $function$
    """,
    "appliquer_desordre_reperage": """
        CREATE OR REPLACE FUNCTION public.appliquer_desordre_reperage()
        RETURNS trigger
        LANGUAGE plpgsql VOLATILE SET search_path = pg_catalog, public
        AS $function$
        DECLARE
            v_nombre_troncons INTEGER;
            v_troncon_id UUID;
            v_geometry geometry;
            v_type TEXT;
            v_troncon_geometry geometry;
            v_debut RECORD;
            v_fin RECORD;
            v_fraction_debut DOUBLE PRECISION;
            v_fraction_fin DOUBLE PRECISION;
            v_guard TEXT;
        BEGIN
            IF current_setting('sirs.reperage_guard', true) = 'GEOMETRIE' THEN
                RETURN NEW;
            END IF;
            SELECT count(*)::integer, min(l.troncon_id::text)::uuid
            INTO v_nombre_troncons, v_troncon_id
            FROM public.link_desordres_troncons AS l
            WHERE l.desordre_id = NEW.desordre_id;
            IF v_nombre_troncons <> 1 OR NEW.troncon_id <> v_troncon_id THEN
                RAISE EXCEPTION
                    'Le repérage exige exactement un tronçon associé au désordre.';
            END IF;
            SELECT d.geometry, GeometryType(d.geometry), t.geometry
            INTO v_geometry, v_type, v_troncon_geometry
            FROM public.desordres AS d
            JOIN public.troncons AS t ON t.id = v_troncon_id
            WHERE d.id = NEW.desordre_id;
            IF v_type NOT IN ('POINT', 'LINESTRING') THEN
                RAISE EXCEPTION
                    'Le repérage éditable est réservé aux Point et LineString.';
            END IF;

            SELECT conversion.* INTO v_debut
            FROM public.borne_offset_vers_xy(
                NEW.troncon_id, NEW.systeme_reperage_id,
                NEW.borne_debut_id,
                CASE NEW.position_debut_relative
                    WHEN 'AVANT_BORNE' THEN -NEW.distance_debut_m
                    WHEN 'SUR_BORNE' THEN 0.0
                    ELSE NEW.distance_debut_m END
            ) AS conversion;
            IF v_debut.statut <> 'OK' THEN
                RAISE EXCEPTION 'Repérage de début invalide : %', v_debut.statut;
            END IF;
            NEW.pr_debut := v_debut.pr;
            IF v_type = 'POINT' THEN
                NEW.borne_fin_id := NULL;
                NEW.distance_fin_m := NULL;
                NEW.position_fin_relative := NULL;
                NEW.pr_fin := NULL;
                v_geometry := v_debut.point_xy;
            ELSE
                IF NEW.borne_fin_id IS NULL OR NEW.distance_fin_m IS NULL
                   OR NEW.position_fin_relative IS NULL THEN
                    RAISE EXCEPTION
                        'Le recalage d''une ligne exige un repérage de fin complet.';
                END IF;
                SELECT conversion.* INTO v_fin
                FROM public.borne_offset_vers_xy(
                    NEW.troncon_id, NEW.systeme_reperage_id,
                    NEW.borne_fin_id,
                    CASE NEW.position_fin_relative
                        WHEN 'AVANT_BORNE' THEN -NEW.distance_fin_m
                        WHEN 'SUR_BORNE' THEN 0.0
                        ELSE NEW.distance_fin_m END
                ) AS conversion;
                IF v_fin.statut <> 'OK' THEN
                    RAISE EXCEPTION 'Repérage de fin invalide : %', v_fin.statut;
                END IF;
                IF abs(v_fin.abscisse_m - v_debut.abscisse_m) <= 1e-8 THEN
                    RAISE EXCEPTION
                        'Le début et la fin ne peuvent pas définir une ligne nulle.';
                END IF;
                NEW.pr_fin := v_fin.pr;
                v_fraction_debut := v_debut.abscisse_m
                    / ST_Length(v_troncon_geometry);
                v_fraction_fin := v_fin.abscisse_m
                    / ST_Length(v_troncon_geometry);
                v_geometry := ST_LineSubstring(
                    v_troncon_geometry,
                    least(v_fraction_debut, v_fraction_fin),
                    greatest(v_fraction_debut, v_fraction_fin)
                );
                IF v_fraction_debut > v_fraction_fin THEN
                    v_geometry := ST_Reverse(v_geometry);
                END IF;
            END IF;

            v_guard := current_setting('sirs.reperage_guard', true);
            PERFORM set_config('sirs.reperage_guard', 'REPERAGE', true);
            UPDATE public.desordres SET geometry = v_geometry
            WHERE id = NEW.desordre_id;
            PERFORM set_config('sirs.reperage_guard', coalesce(v_guard, ''), true);
            RETURN NEW;
        END
        $function$
    """,
    "recalculer_desordre_apres_geometrie": """
        CREATE OR REPLACE FUNCTION public.recalculer_desordre_apres_geometrie()
        RETURNS trigger
        LANGUAGE plpgsql VOLATILE SET search_path = pg_catalog, public
        AS $function$
        BEGIN
            IF current_setting('sirs.reperage_guard', true)
               IS DISTINCT FROM 'REPERAGE' THEN
                PERFORM public.synchroniser_desordre_reperage(NEW.id);
            END IF;
            RETURN NEW;
        END
        $function$
    """,
    "recalculer_desordre_apres_lien_troncon": """
        CREATE OR REPLACE FUNCTION public.recalculer_desordre_apres_lien_troncon()
        RETURNS trigger
        LANGUAGE plpgsql VOLATILE SET search_path = pg_catalog, public
        AS $function$
        BEGIN
            IF TG_OP IN ('DELETE', 'UPDATE') THEN
                PERFORM public.synchroniser_desordre_reperage(OLD.desordre_id);
            END IF;
            IF TG_OP IN ('INSERT', 'UPDATE') THEN
                IF TG_OP = 'INSERT' OR NEW.desordre_id <> OLD.desordre_id THEN
                    PERFORM public.synchroniser_desordre_reperage(NEW.desordre_id);
                END IF;
            END IF;
            RETURN coalesce(NEW, OLD);
        END
        $function$
    """,
    "inverser_troncon": """
        CREATE OR REPLACE FUNCTION public.inverser_troncon(p_troncon_id UUID)
        RETURNS INTEGER
        LANGUAGE plpgsql VOLATILE SET search_path = pg_catalog, public
        AS $function$
        DECLARE
            v_desordre_id UUID;
            v_nombre INTEGER := 0;
        BEGIN
            UPDATE public.troncons SET geometry = ST_Reverse(geometry)
            WHERE id = p_troncon_id AND geometry IS NOT NULL
              AND GeometryType(geometry) = 'LINESTRING';
            IF NOT FOUND THEN
                RAISE EXCEPTION 'Tronçon absent ou géométrie non inversible.';
            END IF;
            FOR v_desordre_id IN
                SELECT l.desordre_id
                FROM public.link_desordres_troncons AS l
                WHERE l.troncon_id = p_troncon_id
                  AND 1 = (SELECT count(*)
                           FROM public.link_desordres_troncons AS tous
                           WHERE tous.desordre_id = l.desordre_id)
            LOOP
                PERFORM public.synchroniser_desordre_reperage(v_desordre_id);
                v_nombre := v_nombre + 1;
            END LOOP;
            RETURN v_nombre;
        END
        $function$
    """,
    "editer_desordre_point": """
        CREATE OR REPLACE FUNCTION public.editer_desordre_point()
        RETURNS trigger
        LANGUAGE plpgsql VOLATILE SET search_path = pg_catalog, public
        AS $function$
        DECLARE
            v_geometry geometry(Point, 3950);
            v_xy_modifie BOOLEAN;
            v_lonlat_modifie BOOLEAN;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                DELETE FROM public.desordres WHERE id = OLD.id;
                RETURN OLD;
            END IF;
            IF TG_OP = 'INSERT' THEN
                v_geometry := coalesce(
                    NEW.geometry,
                    ST_SetSRID(ST_Point(NEW.coord_x_3950, NEW.coord_y_3950), 3950)
                );
                INSERT INTO public.desordres (
                    id, type_desordre_id, designation, commentaire,
                    date_debut, date_fin, geometry, valid
                ) VALUES (
                    coalesce(NEW.id, gen_random_uuid()), NEW.type_desordre_id,
                    NEW.designation, NEW.commentaire, NEW.date_debut,
                    NEW.date_fin, v_geometry, NEW.valid
                ) RETURNING id INTO NEW.id;
            ELSE
                v_xy_modifie := NEW.coord_x_3950 IS DISTINCT FROM OLD.coord_x_3950
                    OR NEW.coord_y_3950 IS DISTINCT FROM OLD.coord_y_3950;
                v_lonlat_modifie := NEW.longitude_4326
                        IS DISTINCT FROM OLD.longitude_4326
                    OR NEW.latitude_4326 IS DISTINCT FROM OLD.latitude_4326;
                IF v_xy_modifie AND v_lonlat_modifie THEN
                    RAISE EXCEPTION
                        'Modifier soit X/Y, soit longitude/latitude, pas les deux.';
                ELSIF v_xy_modifie THEN
                    IF NEW.coord_x_3950 IS NULL OR NEW.coord_y_3950 IS NULL THEN
                        RAISE EXCEPTION 'X et Y sont obligatoires ensemble.';
                    END IF;
                    v_geometry := ST_SetSRID(
                        ST_Point(NEW.coord_x_3950, NEW.coord_y_3950), 3950
                    );
                ELSIF v_lonlat_modifie THEN
                    IF NEW.longitude_4326 IS NULL OR NEW.latitude_4326 IS NULL THEN
                        RAISE EXCEPTION
                            'Longitude et latitude sont obligatoires ensemble.';
                    END IF;
                    v_geometry := ST_Transform(
                        ST_SetSRID(
                            ST_Point(NEW.longitude_4326, NEW.latitude_4326), 4326
                        ), 3950
                    );
                ELSE
                    v_geometry := NEW.geometry;
                END IF;
                UPDATE public.desordres SET
                    type_desordre_id = NEW.type_desordre_id,
                    designation = NEW.designation,
                    commentaire = NEW.commentaire,
                    date_debut = NEW.date_debut,
                    date_fin = NEW.date_fin,
                    geometry = v_geometry,
                    valid = NEW.valid
                WHERE id = OLD.id;
            END IF;
            NEW.geometry := v_geometry;
            NEW.coord_x_3950 := ST_X(v_geometry);
            NEW.coord_y_3950 := ST_Y(v_geometry);
            NEW.longitude_4326 := ST_X(ST_Transform(v_geometry, 4326));
            NEW.latitude_4326 := ST_Y(ST_Transform(v_geometry, 4326));
            RETURN NEW;
        END
        $function$
    """,
}

TRIGGER_DEFINITIONS = {
    "desordres_recalcul_reperage_trigger": """
        CREATE OR REPLACE TRIGGER desordres_recalcul_reperage_trigger
        AFTER INSERT OR UPDATE OF geometry ON public.desordres
        FOR EACH ROW EXECUTE FUNCTION public.recalculer_desordre_apres_geometrie()
    """,
    "liens_desordres_recalcul_reperage_trigger": """
        CREATE OR REPLACE TRIGGER liens_desordres_recalcul_reperage_trigger
        AFTER INSERT OR DELETE OR UPDATE OF desordre_id, troncon_id
        ON public.link_desordres_troncons
        FOR EACH ROW
        EXECUTE FUNCTION public.recalculer_desordre_apres_lien_troncon()
    """,
    "desordre_reperage_appliquer_trigger": """
        CREATE OR REPLACE TRIGGER desordre_reperage_appliquer_trigger
        BEFORE INSERT OR UPDATE OF
            troncon_id, systeme_reperage_id,
            borne_debut_id, distance_debut_m, position_debut_relative,
            borne_fin_id, distance_fin_m, position_fin_relative
        ON public.desordre_localisations_reperage
        FOR EACH ROW EXECUTE FUNCTION public.appliquer_desordre_reperage()
    """,
}

VIEW_DEFINITIONS = {
    "view_desordres_points_saisie": """
        CREATE OR REPLACE VIEW public.view_desordres_points_saisie AS
        SELECT d.id, d.type_desordre_id, d.designation, d.commentaire,
            d.date_debut, d.date_fin, d.geometry, d.valid,
            ST_X(d.geometry)::double precision AS coord_x_3950,
            ST_Y(d.geometry)::double precision AS coord_y_3950,
            ST_X(ST_Transform(d.geometry, 4326))::double precision
                AS longitude_4326,
            ST_Y(ST_Transform(d.geometry, 4326))::double precision
                AS latitude_4326
        FROM public.desordres AS d
        WHERE GeometryType(d.geometry) = 'POINT'
    """,
    "view_systemes_reperage_bornes": """
        CREATE OR REPLACE VIEW public.view_systemes_reperage_bornes AS
        SELECT l.id, l.systeme_reperage_id, l.borne_id, b.libelle,
            CASE
                WHEN abs(ST_LineLocatePoint(t.geometry, b.geometry)) <= 1e-8
                    THEN 'DEBUT_TRONCON'
                WHEN abs(1 - ST_LineLocatePoint(t.geometry, b.geometry)) <= 1e-8
                    THEN 'FIN_TRONCON'
                ELSE 'BORNE_INTERMEDIAIRE'
            END AS role_spatial,
            CASE
                WHEN abs(ST_LineLocatePoint(t.geometry, b.geometry)) <= 1e-8
                    THEN 'Début du tronçon'
                WHEN abs(1 - ST_LineLocatePoint(t.geometry, b.geometry)) <= 1e-8
                    THEN 'Fin du tronçon'
                ELSE coalesce(b.libelle, b.id::text)
            END AS libelle_affichage,
            l.valeur_pr, l.valid AND b.valid AND sr.valid AS valid
        FROM public.link_systemes_reperage_bornes AS l
        JOIN public.systemes_reperage AS sr ON sr.id = l.systeme_reperage_id
        JOIN public.troncons AS t ON t.id = sr.troncon_id
        JOIN public.bornes_reperage AS b ON b.id = l.borne_id
    """,
    "view_desordre_localisations_reperage": """
        CREATE OR REPLACE VIEW public.view_desordre_localisations_reperage AS
        SELECT l.id, l.desordre_id,
            d.designation AS desordre_designation,
            GeometryType(d.geometry) AS type_geometrie_desordre,
            1::integer AS nombre_troncons, true AS reperage_disponible,
            l.troncon_id, t.libelle AS troncon_libelle,
            l.systeme_reperage_id,
            sr.libelle AS systeme_reperage_libelle,
            l.borne_debut_id, bd.libelle AS borne_debut_libelle,
            l.distance_debut_m, l.position_debut_relative, l.pr_debut,
            l.borne_fin_id, bf.libelle AS borne_fin_libelle,
            l.distance_fin_m, l.position_fin_relative, l.pr_fin,
            concat_ws(' — ', t.libelle,
                concat_ws(' ', bd.libelle,
                    round(l.distance_debut_m::numeric, 2) || ' m',
                    CASE WHEN l.offset_debut_m < 0 THEN 'amont'
                         WHEN l.offset_debut_m > 0 THEN 'aval'
                         ELSE 'sur borne' END)) AS resume_localisation,
            l.valid
        FROM public.desordre_localisations_reperage AS l
        JOIN public.desordres AS d ON d.id = l.desordre_id
        JOIN public.troncons AS t ON t.id = l.troncon_id
        JOIN public.systemes_reperage AS sr ON sr.id = l.systeme_reperage_id
        JOIN public.bornes_reperage AS bd ON bd.id = l.borne_debut_id
        LEFT JOIN public.bornes_reperage AS bf ON bf.id = l.borne_fin_id
    """,
}

VIEW_TRIGGER_DEFINITIONS = {
    "view_desordres_points_saisie_trigger": """
        CREATE OR REPLACE TRIGGER view_desordres_points_saisie_trigger
        INSTEAD OF INSERT OR UPDATE OR DELETE
        ON public.view_desordres_points_saisie
        FOR EACH ROW EXECUTE FUNCTION public.editer_desordre_point()
    """,
}

FUNCTION_DDL = tuple(statement.strip() for statement in FUNCTION_DEFINITIONS.values())
TRIGGER_DDL = tuple(statement.strip() for statement in TRIGGER_DEFINITIONS.values())
VIEW_TRIGGER_DDL = tuple(
    statement.strip() for statement in VIEW_TRIGGER_DEFINITIONS.values()
)
