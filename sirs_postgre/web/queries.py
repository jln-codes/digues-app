"""Requêtes GeoJSON en lecture seule pour la carte expérimentale."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from .database import WebDatabaseError
from .models import (
    LineStringGeometryUpdate,
    PointDesordreUpdate,
    PointReperageUpdate,
)


TRONCONS_GEOJSON_SQL = """
    SELECT jsonb_build_object(
        'type', 'FeatureCollection',
        'features', coalesce(
            jsonb_agg(feature ORDER BY sort_label, sort_id),
            '[]'::jsonb
        )
    )
    FROM (
        SELECT
            coalesce(t.libelle, '') AS sort_label,
            t.id::text AS sort_id,
            jsonb_build_object(
                'type', 'Feature',
                'id', t.id,
                'geometry', ST_AsGeoJSON(
                    ST_Transform(t.geometry, 4326)
                )::jsonb,
                'properties', jsonb_build_object(
                    'id', t.id,
                    'libelle', t.libelle,
                    'digue_id', t.digue_id,
                    'digue_libelle', d.libelle,
                    'valid', t.valid
                )
            ) AS feature
        FROM public.troncons AS t
        LEFT JOIN public.digues AS d ON d.id = t.digue_id
        WHERE t.geometry IS NOT NULL
    ) AS features
"""


SYSTEMES_ENDIGUEMENT_SQL = """
    SELECT jsonb_build_object(
        'systemes', coalesce(
            jsonb_agg(systeme ORDER BY sort_label, sort_id),
            '[]'::jsonb
        )
    )
    FROM (
        SELECT
            coalesce(s.libelle, '') AS sort_label,
            s.id::text AS sort_id,
            jsonb_build_object(
                'id', s.id,
                'libelle', s.libelle,
                'valid', s.valid,
                'digues', coalesce((
                    SELECT jsonb_agg(
                        jsonb_build_object(
                            'id', d.id,
                            'systeme_endiguement_id', d.systeme_endiguement_id,
                            'libelle', d.libelle,
                            'valid', d.valid,
                            'troncons', coalesce((
                                SELECT jsonb_agg(
                                    jsonb_build_object(
                                        'id', t.id,
                                        'digue_id', t.digue_id,
                                        'systeme_reperage_defaut_id',
                                            t.systeme_reperage_defaut_id,
                                        'libelle', t.libelle,
                                        'valid', t.valid
                                    )
                                    ORDER BY t.libelle, t.id
                                )
                                FROM public.troncons AS t
                                WHERE t.digue_id = d.id
                            ), '[]'::jsonb)
                        )
                        ORDER BY d.libelle, d.id
                    )
                    FROM public.digues AS d
                    WHERE d.systeme_endiguement_id = s.id
                ), '[]'::jsonb)
            ) AS systeme
        FROM public.systemes AS s
    ) AS systemes
"""


DESORDRES_GEOJSON_SQL = """
    SELECT jsonb_build_object(
        'type', 'FeatureCollection',
        'features', coalesce(
            jsonb_agg(feature ORDER BY sort_label, sort_id),
            '[]'::jsonb
        )
    )
    FROM (
        SELECT
            coalesce(d.designation, '') AS sort_label,
            d.id::text AS sort_id,
            jsonb_build_object(
                'type', 'Feature',
                'id', d.id,
                'geometry', ST_AsGeoJSON(
                    ST_Transform(d.geometry, 4326)
                )::jsonb,
                'properties', jsonb_build_object(
                    'id', d.id,
                    'designation', d.designation,
                    'type_desordre_id', d.type_desordre_id,
                    'type_desordre_libelle', td.libelle,
                    'commentaire', d.commentaire,
                    'date_debut', d.date_debut,
                    'date_fin', d.date_fin,
                    'valid', d.valid,
                    'type_geometrie', GeometryType(d.geometry)
                )
            ) AS feature
        FROM public.desordres AS d
        LEFT JOIN public.ref_types_desordre AS td
            ON td.id = d.type_desordre_id
        WHERE d.geometry IS NOT NULL
          AND GeometryType(d.geometry) IN ('POINT', 'LINESTRING')
    ) AS features
"""


POINT_DESORDRE_SQL = """
    SELECT jsonb_build_object(
        'type', 'Feature',
        'id', p.id,
        'geometry', ST_AsGeoJSON(
            ST_Transform(p.geometry, 4326)
        )::jsonb,
        'properties', jsonb_build_object(
            'id', p.id,
            'designation', p.designation,
            'type_desordre_id', p.type_desordre_id,
            'type_desordre_libelle', td.libelle,
            'commentaire', p.commentaire,
            'coord_x_3950', p.coord_x_3950,
            'coord_y_3950', p.coord_y_3950,
            'longitude_4326', p.longitude_4326,
            'latitude_4326', p.latitude_4326,
            'reperage', jsonb_build_object(
                'nombre_troncons', liens.nombre_troncons,
                'disponible', liens.nombre_troncons = 1
                    AND sr.id IS NOT NULL,
                'motif_indisponibilite', CASE
                    WHEN liens.nombre_troncons = 0
                        THEN 'Aucun tronçon associé.'
                    WHEN liens.nombre_troncons > 1
                        THEN 'Plusieurs tronçons associés.'
                    WHEN sr.id IS NULL
                        THEN 'Aucun système de repérage disponible.'
                    ELSE NULL
                END,
                'troncon_id', t.id,
                'troncon_libelle', t.libelle,
                'systeme_reperage_id', sr.id,
                'systeme_reperage_libelle', sr.libelle,
                'borne_debut_id', localisation.borne_debut_id,
                'borne_debut_libelle', borne.libelle,
                'distance_debut_m', localisation.distance_debut_m,
                'position_debut_relative',
                    localisation.position_debut_relative,
                'pr_debut', localisation.pr_debut,
                'bornes', coalesce((
                    SELECT jsonb_agg(
                        jsonb_build_object(
                            'id', disponible.borne_id,
                            'libelle', disponible.libelle,
                            'libelle_affichage', disponible.libelle_affichage,
                            'role_spatial', disponible.role_spatial,
                            'valeur_pr', disponible.valeur_pr
                        )
                        ORDER BY disponible.valeur_pr, disponible.borne_id
                    )
                    FROM public.view_systemes_reperage_bornes AS disponible
                    WHERE disponible.systeme_reperage_id = sr.id
                      AND disponible.valid
                ), '[]'::jsonb)
            ),
            'valid', p.valid
        )
    )
    FROM public.view_desordres_points_saisie AS p
    LEFT JOIN public.ref_types_desordre AS td
        ON td.id = p.type_desordre_id
    LEFT JOIN LATERAL (
        SELECT count(*)::integer AS nombre_troncons,
            min(lien.troncon_id::text)::uuid AS troncon_id
        FROM public.link_desordres_troncons AS lien
        WHERE lien.desordre_id = p.id
    ) AS liens ON true
    LEFT JOIN public.troncons AS t
        ON t.id = liens.troncon_id AND liens.nombre_troncons = 1
    LEFT JOIN public.desordre_localisations_reperage AS localisation
        ON localisation.desordre_id = p.id
       AND localisation.troncon_id = t.id
    LEFT JOIN public.systemes_reperage AS sr
        ON sr.id = coalesce(
            localisation.systeme_reperage_id,
            t.systeme_reperage_defaut_id
        )
       AND sr.troncon_id = t.id
    LEFT JOIN public.bornes_reperage AS borne
        ON borne.id = localisation.borne_debut_id
    WHERE p.id = %s
"""


DESORDRE_GEOMETRY_TYPE_SQL = """
    SELECT GeometryType(d.geometry)
    FROM public.desordres AS d
    WHERE d.id = %s
"""


LINE_DESORDRE_SQL = """
    SELECT jsonb_build_object(
        'type', 'Feature',
        'id', d.id,
        'geometry', ST_AsGeoJSON(ST_Transform(d.geometry, 4326))::jsonb,
        'properties', jsonb_build_object(
            'id', d.id,
            'designation', d.designation,
            'type_desordre_id', d.type_desordre_id,
            'type_desordre_libelle', td.libelle,
            'commentaire', d.commentaire,
            'date_debut', d.date_debut,
            'date_fin', d.date_fin,
            'valid', d.valid,
            'type_geometrie', GeometryType(d.geometry),
            'nombre_sommets', ST_NPoints(d.geometry),
            'reperage', jsonb_build_object(
                'nombre_troncons', liens.nombre_troncons,
                'disponible', liens.nombre_troncons = 1
                    AND localisation.id IS NOT NULL,
                'troncon_id', localisation.troncon_id,
                'troncon_libelle', localisation.troncon_libelle,
                'systeme_reperage_id', localisation.systeme_reperage_id,
                'systeme_reperage_libelle',
                    localisation.systeme_reperage_libelle,
                'borne_debut_id', localisation.borne_debut_id,
                'borne_debut_libelle', localisation.borne_debut_libelle,
                'distance_debut_m', localisation.distance_debut_m,
                'position_debut_relative',
                    localisation.position_debut_relative,
                'pr_debut', localisation.pr_debut,
                'borne_fin_id', localisation.borne_fin_id,
                'borne_fin_libelle', localisation.borne_fin_libelle,
                'distance_fin_m', localisation.distance_fin_m,
                'position_fin_relative', localisation.position_fin_relative,
                'pr_fin', localisation.pr_fin
            )
        )
    )
    FROM public.desordres AS d
    LEFT JOIN public.ref_types_desordre AS td
        ON td.id = d.type_desordre_id
    LEFT JOIN LATERAL (
        SELECT count(*)::integer AS nombre_troncons
        FROM public.link_desordres_troncons AS lien
        WHERE lien.desordre_id = d.id
    ) AS liens ON true
    LEFT JOIN public.view_desordre_localisations_reperage AS localisation
        ON localisation.desordre_id = d.id
    WHERE d.id = %s
      AND GeometryType(d.geometry) = 'LINESTRING'
"""


DESORDRE_OBSERVATIONS_SQL = """
    SELECT jsonb_build_object(
        'desordre_id', d.id,
        'observations', coalesce((
            SELECT jsonb_agg(observation ORDER BY sort_date DESC NULLS LAST, sort_id)
            FROM (
                SELECT
                    o.date AS sort_date,
                    o.id::text AS sort_id,
                    jsonb_build_object(
                        'id', o.id,
                        'desordre_id', o.desordre_id,
                        'urgence_id', o.urgence_id,
                        'urgence_libelle', u.libelle,
                        'designation', o.designation,
                        'date', o.date,
                        'evolution', o.evolution,
                        'valid', o.valid,
                        'photo_count', (
                            SELECT count(*)
                            FROM public.photos AS p
                            WHERE p.observation_id = o.id
                        )
                    ) AS observation
                FROM public.observations AS o
                LEFT JOIN public.ref_urgences AS u ON u.id = o.urgence_id
                WHERE o.desordre_id = d.id
            ) AS ordered_observations
        ), '[]'::jsonb)
    )
    FROM public.desordres AS d
    WHERE d.id = %s
"""


OBSERVATION_DETAIL_SQL = """
    SELECT jsonb_build_object(
        'id', o.id,
        'desordre_id', o.desordre_id,
        'urgence_id', o.urgence_id,
        'urgence_libelle', u.libelle,
        'designation', o.designation,
        'date', o.date,
        'evolution', o.evolution,
        'valid', o.valid,
        'photos', coalesce((
            SELECT jsonb_agg(photo ORDER BY sort_date DESC NULLS LAST, sort_id)
            FROM (
                SELECT
                    p.date AS sort_date,
                    p.id::text AS sort_id,
                    jsonb_build_object(
                        'id', p.id,
                        'observation_id', p.observation_id,
                        'designation', p.designation,
                        'date', p.date,
                        'valid', p.valid,
                        'nom_fichier', reverse(split_part(
                            reverse(replace(p.chemin_source, E'\\\\', '/')),
                            '/', 1
                        )),
                        'content_available', false
                    ) AS photo
                FROM public.photos AS p
                WHERE p.observation_id = o.id
            ) AS ordered_photos
        ), '[]'::jsonb)
    )
    FROM public.observations AS o
    LEFT JOIN public.ref_urgences AS u ON u.id = o.urgence_id
    WHERE o.id = %s
      AND o.desordre_id IS NOT NULL
"""


POINT_UPDATE_COLUMNS = {
    "designation": "designation",
    "type_desordre_id": "type_desordre_id",
    "commentaire": "commentaire",
    "coord_x_3950": "coord_x_3950",
    "coord_y_3950": "coord_y_3950",
    "longitude_4326": "longitude_4326",
    "latitude_4326": "latitude_4326",
}


class PointDesordreNotFoundError(LookupError):
    """Le désordre demandé n'existe pas ou n'est pas ponctuel."""


class PointDesordreUpdateError(ValueError):
    """Le trigger PostgreSQL a refusé la modification ponctuelle."""


class ObservationNotFoundError(LookupError):
    """Le désordre ou l'observation demandé n'existe pas."""


class PointReperageUnavailableError(ValueError):
    """Le désordre Point ne possède pas un contexte de repérage éditable."""


class PointReperageUpdateError(ValueError):
    """Le trigger PostgreSQL a refusé la modification du repérage."""


class DesordreNotFoundError(LookupError):
    """Le désordre cartographique demandé n'existe pas."""


class LineDesordreNotFoundError(LookupError):
    """Le désordre demandé n'existe pas ou n'est pas linéaire."""


class LineDesordreUpdateError(ValueError):
    """PostgreSQL a refusé la géométrie linéaire proposée."""


def _feature_collection(connection: Any, query: str) -> dict[str, Any]:
    try:
        with connection.cursor() as cursor:
            cursor.execute(query)
            row = cursor.fetchone()
    except Exception as exc:
        raise WebDatabaseError("Lecture cartographique PostgreSQL impossible.") from exc

    result = row[0] if row else None
    if isinstance(result, str):
        result = json.loads(result)
    if not isinstance(result, dict) or result.get("type") != "FeatureCollection":
        raise WebDatabaseError("Réponse GeoJSON PostgreSQL invalide.")
    result.setdefault("features", [])
    return result


def fetch_troncons(connection: Any) -> dict[str, Any]:
    """Retourne les tronçons transformés en EPSG:4326 par PostGIS."""

    return _feature_collection(connection, TRONCONS_GEOJSON_SQL)


def fetch_systemes_endiguement(connection: Any) -> dict[str, Any]:
    """Retourne l'arbre système d'endiguement → digues → tronçons."""

    try:
        with connection.cursor() as cursor:
            cursor.execute(SYSTEMES_ENDIGUEMENT_SQL)
            row = cursor.fetchone()
    except Exception as exc:
        raise WebDatabaseError("Lecture du patrimoine PostgreSQL impossible.") from exc
    result = row[0] if row else None
    if isinstance(result, str):
        result = json.loads(result)
    if not isinstance(result, dict) or not isinstance(result.get("systemes"), list):
        raise WebDatabaseError("Réponse hiérarchique PostgreSQL invalide.")
    return result


def fetch_desordres(connection: Any) -> dict[str, Any]:
    """Retourne ensemble les désordres Point et LineString en EPSG:4326."""

    return _feature_collection(connection, DESORDRES_GEOJSON_SQL)


def fetch_point_desordre(connection: Any, desordre_id: UUID) -> dict[str, Any]:
    """Relit un Point et toutes ses coordonnées dérivées depuis PostgreSQL."""

    try:
        with connection.cursor() as cursor:
            cursor.execute(POINT_DESORDRE_SQL, (desordre_id,))
            row = cursor.fetchone()
    except Exception as exc:
        raise WebDatabaseError("Lecture du désordre Point impossible.") from exc
    if not row:
        raise PointDesordreNotFoundError("Désordre Point introuvable.")
    result = row[0]
    if isinstance(result, str):
        result = json.loads(result)
    if not isinstance(result, dict) or result.get("type") != "Feature":
        raise WebDatabaseError("Réponse GeoJSON PostgreSQL invalide.")
    return result


def fetch_line_desordre(connection: Any, desordre_id: UUID) -> dict[str, Any]:
    """Relit une LineString complète en EPSG:4326 depuis PostgreSQL."""

    try:
        with connection.cursor() as cursor:
            cursor.execute(LINE_DESORDRE_SQL, (desordre_id,))
            row = cursor.fetchone()
    except Exception as exc:
        raise WebDatabaseError("Lecture du désordre LineString impossible.") from exc
    if not row:
        raise LineDesordreNotFoundError("Désordre LineString introuvable.")
    result = row[0]
    if isinstance(result, str):
        result = json.loads(result)
    if not isinstance(result, dict) or result.get("type") != "Feature":
        raise WebDatabaseError("Réponse GeoJSON PostgreSQL invalide.")
    return result


def fetch_desordre(connection: Any, desordre_id: UUID) -> dict[str, Any]:
    """Distribue la lecture détaillée selon la géométrie réelle du désordre."""

    try:
        with connection.cursor() as cursor:
            cursor.execute(DESORDRE_GEOMETRY_TYPE_SQL, (desordre_id,))
            row = cursor.fetchone()
    except Exception as exc:
        raise WebDatabaseError("Lecture du type géométrique impossible.") from exc
    if not row:
        raise DesordreNotFoundError("Désordre introuvable.")
    if row[0] == "POINT":
        return fetch_point_desordre(connection, desordre_id)
    if row[0] == "LINESTRING":
        return fetch_line_desordre(connection, desordre_id)
    raise DesordreNotFoundError("Type de désordre non pris en charge.")


def _json_object(
    connection: Any,
    query: str,
    identifier: UUID,
    *,
    error_message: str,
    not_found_message: str,
) -> dict[str, Any]:
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, (identifier,))
            row = cursor.fetchone()
    except Exception as exc:
        raise WebDatabaseError(error_message) from exc
    if not row:
        raise ObservationNotFoundError(not_found_message)
    result = row[0]
    if isinstance(result, str):
        result = json.loads(result)
    if not isinstance(result, dict):
        raise WebDatabaseError("Réponse PostgreSQL invalide.")
    return result


def fetch_desordre_observations(
    connection: Any, desordre_id: UUID
) -> dict[str, Any]:
    """Retourne les observations directement rattachées à un désordre."""

    return _json_object(
        connection,
        DESORDRE_OBSERVATIONS_SQL,
        desordre_id,
        error_message="Lecture des observations du désordre impossible.",
        not_found_message="Désordre introuvable.",
    )


def fetch_observation(connection: Any, observation_id: UUID) -> dict[str, Any]:
    """Retourne une observation de désordre et ses photos enfants."""

    return _json_object(
        connection,
        OBSERVATION_DETAIL_SQL,
        observation_id,
        error_message="Lecture de l'observation impossible.",
        not_found_message="Observation de désordre introuvable.",
    )


def update_point_desordre(
    connection: Any,
    desordre_id: UUID,
    update: PointDesordreUpdate,
) -> dict[str, Any]:
    """Met à jour la vue ponctuelle puis relit l'état produit par les triggers."""

    values = update.model_dump(exclude_unset=True)
    assignments = [f"{POINT_UPDATE_COLUMNS[field]} = %s" for field in values]
    parameters = [values[field] for field in values]
    parameters.append(desordre_id)

    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE public.view_desordres_points_saisie SET "
                    + ", ".join(assignments)
                    + " WHERE id = %s RETURNING id",
                    parameters,
                )
                if cursor.fetchone() is None:
                    raise PointDesordreNotFoundError(
                        "Désordre Point introuvable."
                    )
            return fetch_point_desordre(connection, desordre_id)
    except PointDesordreNotFoundError:
        raise
    except WebDatabaseError:
        raise
    except Exception as exc:
        diagnostic = getattr(exc, "diag", None)
        message = getattr(diagnostic, "message_primary", None)
        raise PointDesordreUpdateError(
            str(message or "Mise à jour refusée par PostgreSQL.")
        ) from exc


def update_point_reperage(
    connection: Any,
    desordre_id: UUID,
    update: PointReperageUpdate,
) -> dict[str, Any]:
    """Écrit le bornage enfant, puis relit géométrie et valeurs dérivées."""

    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM public.desordres "
                    "WHERE id = %s AND GeometryType(geometry) = 'POINT' "
                    "FOR UPDATE",
                    (desordre_id,),
                )
                if cursor.fetchone() is None:
                    raise PointDesordreNotFoundError(
                        "Désordre Point introuvable."
                    )
                cursor.execute(
                    "SELECT count(*)::integer, "
                    "min(l.troncon_id::text)::uuid "
                    "FROM public.link_desordres_troncons AS l "
                    "WHERE l.desordre_id = %s",
                    (desordre_id,),
                )
                nombre_troncons, troncon_id = cursor.fetchone()
                if nombre_troncons != 1:
                    raise PointReperageUnavailableError(
                        "Le repérage exige exactement un tronçon associé "
                        "au désordre."
                    )
                cursor.execute(
                    "SELECT coalesce(l.systeme_reperage_id, "
                    "t.systeme_reperage_defaut_id) "
                    "FROM public.troncons AS t "
                    "LEFT JOIN public.desordre_localisations_reperage AS l "
                    "ON l.desordre_id = %s AND l.troncon_id = t.id "
                    "WHERE t.id = %s",
                    (desordre_id, troncon_id),
                )
                systeme_row = cursor.fetchone()
                systeme_id = systeme_row[0] if systeme_row else None
                if systeme_id is None:
                    raise PointReperageUnavailableError(
                        "Aucun système de repérage n'est disponible pour "
                        "le tronçon associé."
                    )
                cursor.execute(
                    "SELECT 1 "
                    "FROM public.link_systemes_reperage_bornes "
                    "WHERE systeme_reperage_id = %s AND borne_id = %s",
                    (systeme_id, update.borne_debut_id),
                )
                if cursor.fetchone() is None:
                    raise PointReperageUpdateError(
                        "La borne sélectionnée n'appartient pas au système "
                        "de repérage du tronçon associé."
                    )
                cursor.execute(
                    "UPDATE public.desordre_localisations_reperage SET "
                    "troncon_id = %s, systeme_reperage_id = %s, "
                    "borne_debut_id = %s, distance_debut_m = %s, "
                    "position_debut_relative = %s "
                    "WHERE desordre_id = %s RETURNING id",
                    (
                        troncon_id,
                        systeme_id,
                        update.borne_debut_id,
                        update.distance_debut_m,
                        update.position_debut_relative,
                        desordre_id,
                    ),
                )
                if cursor.fetchone() is None:
                    cursor.execute(
                        "INSERT INTO public.desordre_localisations_reperage ("
                        "desordre_id, troncon_id, systeme_reperage_id, "
                        "borne_debut_id, distance_debut_m, "
                        "position_debut_relative, valid) "
                        "VALUES (%s, %s, %s, %s, %s, %s, true) RETURNING id",
                        (
                            desordre_id,
                            troncon_id,
                            systeme_id,
                            update.borne_debut_id,
                            update.distance_debut_m,
                            update.position_debut_relative,
                        ),
                    )
                    cursor.fetchone()
            return fetch_point_desordre(connection, desordre_id)
    except (
        PointDesordreNotFoundError,
        PointReperageUnavailableError,
        PointReperageUpdateError,
        WebDatabaseError,
    ):
        raise
    except Exception as exc:
        diagnostic = getattr(exc, "diag", None)
        message = getattr(diagnostic, "message_primary", None)
        raise PointReperageUpdateError(
            str(message or "Repérage refusé par PostgreSQL.")
        ) from exc


def update_line_desordre_geometry(
    connection: Any,
    desordre_id: UUID,
    update: LineStringGeometryUpdate,
) -> dict[str, Any]:
    """Transforme le GeoJSON 4326 en 3950, écrit, puis relit la ligne."""

    geometry_json = json.dumps(update.geometry.model_dump(), allow_nan=False)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT ST_IsValid(candidate.geometry), "
                    "NOT ST_IsEmpty(candidate.geometry), "
                    "ST_NPoints(ST_RemoveRepeatedPoints(candidate.geometry)) >= 2 "
                    "FROM (SELECT ST_SetSRID("
                    "ST_GeomFromGeoJSON(%s), 4326) AS geometry) AS candidate",
                    (geometry_json,),
                )
                is_valid, is_not_empty, has_distinct_vertices = cursor.fetchone()
                if not is_valid or not is_not_empty or not has_distinct_vertices:
                    raise LineDesordreUpdateError(
                        "La géométrie LineString proposée est invalide."
                    )
                cursor.execute(
                    "UPDATE public.desordres SET geometry = ST_Transform("
                    "ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 3950) "
                    "WHERE id = %s AND GeometryType(geometry) = 'LINESTRING' "
                    "RETURNING id",
                    (geometry_json, desordre_id),
                )
                if cursor.fetchone() is None:
                    raise LineDesordreNotFoundError(
                        "Désordre LineString introuvable."
                    )
            return fetch_line_desordre(connection, desordre_id)
    except (
        LineDesordreNotFoundError,
        LineDesordreUpdateError,
        WebDatabaseError,
    ):
        raise
    except Exception as exc:
        diagnostic = getattr(exc, "diag", None)
        message = getattr(diagnostic, "message_primary", None)
        raise LineDesordreUpdateError(
            str(message or "Géométrie LineString refusée par PostgreSQL.")
        ) from exc
