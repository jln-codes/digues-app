"""Requêtes GeoJSON en lecture seule pour la carte expérimentale."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from .database import WebDatabaseError
from .models import (
    DesordreCreate,
    DigueCreate,
    LineEndpoints,
    LineStringGeometryUpdate,
    PointDesordreUpdate,
    PointReperageUpdate,
    SystemeEndiguementCreate,
    TronconCreate,
)


TYPES_DESORDRE_SQL = """
    SELECT jsonb_build_object(
        'types', coalesce(jsonb_agg(
            jsonb_build_object(
                'id', t.id,
                'libelle', t.libelle,
                'categorie_id', t.categorie_id,
                'valid', t.valid
            ) ORDER BY t.libelle, t.id
        ), '[]'::jsonb)
    )
    FROM public.ref_types_desordre AS t
"""


TRONCONS_OPTIONS_SQL = """
    SELECT jsonb_build_object(
        'troncons', coalesce(jsonb_agg(
            jsonb_build_object(
                'id', t.id,
                'libelle', t.libelle,
                'digue_id', t.digue_id,
                'digue_libelle', d.libelle,
                'valid', t.valid
            ) ORDER BY d.libelle, t.libelle, t.id
        ), '[]'::jsonb)
    )
    FROM public.troncons AS t
    LEFT JOIN public.digues AS d ON d.id = t.digue_id
"""


TRONCON_REPERAGE_OPTIONS_SQL = """
    SELECT jsonb_build_object(
        'troncon_id', t.id,
        'troncon_libelle', t.libelle,
        'systeme_reperage_id', sr.id,
        'systeme_reperage_libelle', sr.libelle,
        'bornes', coalesce((
            SELECT jsonb_agg(jsonb_build_object(
                'id', b.borne_id,
                'libelle', b.libelle,
                'libelle_affichage', b.libelle_affichage,
                'role_spatial', b.role_spatial,
                'valeur_pr', b.valeur_pr
            ) ORDER BY b.valeur_pr, b.borne_id)
            FROM public.view_systemes_reperage_bornes AS b
            WHERE b.systeme_reperage_id = sr.id AND b.valid
        ), '[]'::jsonb)
    )
    FROM public.troncons AS t
    LEFT JOIN public.systemes_reperage AS sr
      ON sr.id = t.systeme_reperage_defaut_id AND sr.valid
    WHERE t.id = %s AND t.valid
"""


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


SYSTEME_ENDIGUEMENT_DETAIL_SQL = """
    SELECT jsonb_build_object(
        'id', s.id,
        'libelle', s.libelle,
        'valid', s.valid,
        'digues', '[]'::jsonb
    )
    FROM public.systemes AS s
    WHERE s.id = %s
"""


DIGUE_DETAIL_SQL = """
    SELECT jsonb_build_object(
        'id', d.id,
        'systeme_endiguement_id', d.systeme_endiguement_id,
        'systeme_endiguement_libelle', s.libelle,
        'libelle', d.libelle,
        'valid', d.valid,
        'troncons', '[]'::jsonb
    )
    FROM public.digues AS d
    JOIN public.systemes AS s ON s.id = d.systeme_endiguement_id
    WHERE d.id = %s
"""


TRONCON_DETAIL_SQL = """
    SELECT jsonb_build_object(
        'type', 'Feature',
        'id', t.id,
        'geometry', ST_AsGeoJSON(ST_Transform(t.geometry, 4326))::jsonb,
        'properties', jsonb_build_object(
            'id', t.id,
            'digue_id', t.digue_id,
            'digue_libelle', d.libelle,
            'systeme_reperage_defaut_id', t.systeme_reperage_defaut_id,
            'libelle', t.libelle,
            'valid', t.valid,
            'nombre_sommets', ST_NPoints(t.geometry)
        )
    )
    FROM public.troncons AS t
    JOIN public.digues AS d ON d.id = t.digue_id
    WHERE t.id = %s
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
          AND GeometryType(d.geometry) IN ('POINT', 'LINESTRING', 'POLYGON')
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
            'troncon_ids', coalesce((
                SELECT jsonb_agg(lien.troncon_id ORDER BY lien.troncon_id)
                FROM public.link_desordres_troncons AS lien
                WHERE lien.desordre_id = p.id
            ), '[]'::jsonb),
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
            'debut_x_3950', ST_X(ST_StartPoint(d.geometry)),
            'debut_y_3950', ST_Y(ST_StartPoint(d.geometry)),
            'fin_x_3950', ST_X(ST_EndPoint(d.geometry)),
            'fin_y_3950', ST_Y(ST_EndPoint(d.geometry)),
            'debut_longitude_4326', ST_X(ST_Transform(
                ST_StartPoint(d.geometry), 4326
            )),
            'debut_latitude_4326', ST_Y(ST_Transform(
                ST_StartPoint(d.geometry), 4326
            )),
            'fin_longitude_4326', ST_X(ST_Transform(
                ST_EndPoint(d.geometry), 4326
            )),
            'fin_latitude_4326', ST_Y(ST_Transform(
                ST_EndPoint(d.geometry), 4326
            )),
            'troncon_ids', coalesce((
                SELECT jsonb_agg(lien.troncon_id ORDER BY lien.troncon_id)
                FROM public.link_desordres_troncons AS lien
                WHERE lien.desordre_id = d.id
            ), '[]'::jsonb),
            'reperage', jsonb_build_object(
                'nombre_troncons', liens.nombre_troncons,
                'disponible', liens.nombre_troncons = 1
                    AND localisation.id IS NOT NULL,
                'motif_indisponibilite', CASE
                    WHEN liens.nombre_troncons = 0 THEN 'Aucun tronçon associé.'
                    WHEN liens.nombre_troncons > 1
                        THEN 'Plusieurs tronçons associés.'
                    WHEN localisation.id IS NULL
                        THEN 'Aucun système de repérage disponible.'
                    ELSE NULL
                END,
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
                'pr_fin', localisation.pr_fin,
                'bornes', coalesce((
                    SELECT jsonb_agg(jsonb_build_object(
                        'id', disponible.borne_id,
                        'libelle', disponible.libelle,
                        'libelle_affichage', disponible.libelle_affichage,
                        'role_spatial', disponible.role_spatial,
                        'valeur_pr', disponible.valeur_pr
                    ) ORDER BY disponible.valeur_pr, disponible.borne_id)
                    FROM public.view_systemes_reperage_bornes AS disponible
                    WHERE disponible.systeme_reperage_id =
                        localisation.systeme_reperage_id
                      AND disponible.valid
                ), '[]'::jsonb)
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


POLYGON_DESORDRE_SQL = """
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
            'nombre_troncons', (
                SELECT count(*)::integer
                FROM public.link_desordres_troncons AS lien
                WHERE lien.desordre_id = d.id
            ),
            'troncon_ids', coalesce((
                SELECT jsonb_agg(lien.troncon_id ORDER BY lien.troncon_id)
                FROM public.link_desordres_troncons AS lien
                WHERE lien.desordre_id = d.id
            ), '[]'::jsonb),
            'coord_x_3950', ST_X(ST_PointOnSurface(d.geometry)),
            'coord_y_3950', ST_Y(ST_PointOnSurface(d.geometry)),
            'longitude_4326', ST_X(ST_Transform(
                ST_PointOnSurface(d.geometry), 4326
            )),
            'latitude_4326', ST_Y(ST_Transform(
                ST_PointOnSurface(d.geometry), 4326
            )),
            'reperage', jsonb_build_object(
                'disponible', false,
                'motif_indisponibilite',
                    'Le repérage polygonal est uniquement informatif.'
            )
        )
    )
    FROM public.desordres AS d
    LEFT JOIN public.ref_types_desordre AS td
        ON td.id = d.type_desordre_id
    WHERE d.id = %s AND GeometryType(d.geometry) = 'POLYGON'
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
    "date_debut": "date_debut",
    "date_fin": "date_fin",
    "valid": "valid",
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


class HeritageCreationError(ValueError):
    """La création patrimoniale a été refusée sans objet partiel."""


class DesordreCreationError(ValueError):
    """La création du désordre a été refusée sans objet partiel."""


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


def fetch_types_desordre(connection: Any) -> dict[str, Any]:
    """Retourne les types de désordre nécessaires au formulaire de création."""

    try:
        with connection.cursor() as cursor:
            cursor.execute(TYPES_DESORDRE_SQL)
            row = cursor.fetchone()
    except Exception as exc:
        raise WebDatabaseError("Lecture des types de désordre impossible.") from exc
    result = row[0] if row else None
    if isinstance(result, str):
        result = json.loads(result)
    if not isinstance(result, dict) or not isinstance(result.get("types"), list):
        raise WebDatabaseError("Réponse du référentiel des désordres invalide.")
    return result


def fetch_troncon_options(connection: Any) -> dict[str, Any]:
    """Retourne tous les tronçons, y compris ceux hors arbre des systèmes."""

    try:
        with connection.cursor() as cursor:
            cursor.execute(TRONCONS_OPTIONS_SQL)
            row = cursor.fetchone()
    except Exception as exc:
        raise WebDatabaseError("Lecture des tronçons disponibles impossible.") from exc
    result = row[0] if row else None
    if isinstance(result, str):
        result = json.loads(result)
    if not isinstance(result, dict) or not isinstance(result.get("troncons"), list):
        raise WebDatabaseError("Réponse des tronçons disponibles invalide.")
    return result


def fetch_troncon_reperage_options(
    connection: Any, troncon_id: UUID
) -> dict[str, Any]:
    """Retourne le système par défaut et ses bornes actives."""

    try:
        with connection.cursor() as cursor:
            cursor.execute(TRONCON_REPERAGE_OPTIONS_SQL, (troncon_id,))
            row = cursor.fetchone()
    except Exception as exc:
        raise WebDatabaseError("Lecture du repérage du tronçon impossible.") from exc
    if not row:
        raise DesordreCreationError("Tronçon absent ou invalide.")
    result = row[0]
    if not isinstance(result, dict):
        raise WebDatabaseError("Réponse de repérage du tronçon invalide.")
    return result


def _fetch_created_object(
    connection: Any,
    query: str,
    identifier: UUID,
    *,
    error_message: str,
) -> dict[str, Any]:
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, (identifier,))
            row = cursor.fetchone()
    except Exception as exc:
        raise WebDatabaseError(error_message) from exc
    if not row:
        raise WebDatabaseError("L'objet créé n'a pas pu être relu.")
    result = row[0]
    if isinstance(result, str):
        result = json.loads(result)
    if not isinstance(result, dict):
        raise WebDatabaseError("Réponse PostgreSQL invalide après création.")
    return result


def fetch_systeme_endiguement(
    connection: Any, systeme_id: UUID
) -> dict[str, Any]:
    return _fetch_created_object(
        connection,
        SYSTEME_ENDIGUEMENT_DETAIL_SQL,
        systeme_id,
        error_message="Relecture du système d'endiguement impossible.",
    )


def fetch_digue(connection: Any, digue_id: UUID) -> dict[str, Any]:
    return _fetch_created_object(
        connection,
        DIGUE_DETAIL_SQL,
        digue_id,
        error_message="Relecture de la digue impossible.",
    )


def fetch_troncon(connection: Any, troncon_id: UUID) -> dict[str, Any]:
    result = _fetch_created_object(
        connection,
        TRONCON_DETAIL_SQL,
        troncon_id,
        error_message="Relecture du tronçon impossible.",
    )
    if result.get("type") != "Feature" or (result.get("geometry") or {}).get(
        "type"
    ) != "LineString":
        raise WebDatabaseError("Réponse GeoJSON invalide après création du tronçon.")
    return result


def _creation_error(exc: Exception, fallback: str) -> HeritageCreationError:
    diagnostic = getattr(exc, "diag", None)
    message = getattr(diagnostic, "message_primary", None)
    return HeritageCreationError(str(message or fallback))


def create_systeme_endiguement(
    connection: Any, creation: SystemeEndiguementCreate
) -> dict[str, Any]:
    """Insère puis relit un système dans une transaction unique."""

    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO public.systemes (libelle, valid) "
                    "VALUES (%s, %s) RETURNING id",
                    (creation.libelle, creation.valid),
                )
                systeme_id = cursor.fetchone()[0]
            return fetch_systeme_endiguement(connection, systeme_id)
    except (WebDatabaseError, HeritageCreationError):
        raise
    except Exception as exc:
        raise _creation_error(
            exc, "Création du système d'endiguement refusée par PostgreSQL."
        ) from exc


def create_digue(connection: Any, creation: DigueCreate) -> dict[str, Any]:
    """Crée une digue seulement sous un système parent actif."""

    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM public.systemes WHERE id = %s AND valid",
                    (creation.systeme_endiguement_id,),
                )
                if cursor.fetchone() is None:
                    raise HeritageCreationError(
                        "Le système d'endiguement parent est absent ou invalide."
                    )
                cursor.execute(
                    "INSERT INTO public.digues "
                    "(systeme_endiguement_id, libelle, valid) "
                    "VALUES (%s, %s, %s) RETURNING id",
                    (
                        creation.systeme_endiguement_id,
                        creation.libelle,
                        creation.valid,
                    ),
                )
                digue_id = cursor.fetchone()[0]
            return fetch_digue(connection, digue_id)
    except (WebDatabaseError, HeritageCreationError):
        raise
    except Exception as exc:
        raise _creation_error(exc, "Création de la digue refusée par PostgreSQL.") from exc


def create_troncon(connection: Any, creation: TronconCreate) -> dict[str, Any]:
    """Valide en 4326, transforme en 3950, insère et relit la LineString."""

    geometry_json = json.dumps(creation.geometry.model_dump(), allow_nan=False)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM public.digues WHERE id = %s AND valid",
                    (creation.digue_id,),
                )
                if cursor.fetchone() is None:
                    raise HeritageCreationError(
                        "La digue parente est absente ou invalide."
                    )
                cursor.execute(
                    "SELECT ST_IsValid(candidate.geometry), "
                    "NOT ST_IsEmpty(candidate.geometry), "
                    "ST_NPoints(candidate.geometry) >= 2, "
                    "ST_Length(candidate.geometry) > 0 "
                    "FROM (SELECT ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326) "
                    "AS geometry) AS candidate",
                    (geometry_json,),
                )
                valid, not_empty, enough_vertices, non_degenerate = cursor.fetchone()
                if not all((valid, not_empty, enough_vertices, non_degenerate)):
                    raise HeritageCreationError(
                        "La LineString proposée est invalide ou dégénérée."
                    )
                cursor.execute(
                    "INSERT INTO public.troncons "
                    "(digue_id, libelle, geometry, valid) VALUES ("
                    "%s, %s, ST_Transform(ST_SetSRID("
                    "ST_GeomFromGeoJSON(%s), 4326), 3950), %s) RETURNING id",
                    (
                        creation.digue_id,
                        creation.libelle,
                        geometry_json,
                        creation.valid,
                    ),
                )
                troncon_id = cursor.fetchone()[0]
            return fetch_troncon(connection, troncon_id)
    except (WebDatabaseError, HeritageCreationError):
        raise
    except Exception as exc:
        raise _creation_error(
            exc, "Création du tronçon refusée par PostgreSQL."
        ) from exc


def _validate_desordre_references(cursor: Any, creation: DesordreCreate) -> None:
    if creation.type_desordre_id is not None:
        cursor.execute(
            "SELECT 1 FROM public.ref_types_desordre WHERE id = %s AND valid",
            (creation.type_desordre_id,),
        )
        if cursor.fetchone() is None:
            raise DesordreCreationError(
                "Le type de désordre est absent ou invalide."
            )
    if creation.troncon_ids:
        cursor.execute(
            "SELECT id FROM public.troncons "
            "WHERE id = ANY(%s::uuid[]) AND valid FOR SHARE",
            (creation.troncon_ids,),
        )
        existing = {row[0] for row in cursor.fetchall()}
        missing = set(creation.troncon_ids) - existing
        if missing:
            raise DesordreCreationError(
                "Au moins un tronçon associé est absent ou invalide."
            )


def _validate_desordre_geometry(cursor: Any, creation: DesordreCreate) -> str | None:
    if creation.geometry is None:
        return None
    geometry_json = json.dumps(creation.geometry.model_dump(), allow_nan=False)
    cursor.execute(
        "SELECT GeometryType(candidate.geometry), "
        "ST_IsValid(candidate.geometry), NOT ST_IsEmpty(candidate.geometry), "
        "CASE WHEN GeometryType(candidate.geometry) = 'LINESTRING' "
        "THEN ST_NPoints(ST_RemoveRepeatedPoints(candidate.geometry)) >= 2 "
        "ELSE true END, "
        "CASE WHEN GeometryType(candidate.geometry) = 'POLYGON' "
        "THEN ST_Area(ST_Transform(candidate.geometry, 3950)) > 0 "
        "ELSE true END "
        "FROM (SELECT ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326) "
        "AS geometry) AS candidate",
        (geometry_json,),
    )
    geometry_type, is_valid, not_empty, line_ok, polygon_ok = cursor.fetchone()
    expected = creation.geometry.type.upper()
    if geometry_type != expected or not all(
        (is_valid, not_empty, line_ok, polygon_ok)
    ):
        raise DesordreCreationError(
            f"La géométrie {creation.geometry.type} proposée est invalide."
        )
    return geometry_json


def _insert_desordre(cursor: Any, creation: DesordreCreate) -> UUID:
    common_columns = (
        "type_desordre_id, designation, commentaire, date_debut, date_fin, valid"
    )
    common_values = (
        creation.type_desordre_id,
        creation.designation,
        creation.commentaire,
        creation.date_debut,
        creation.date_fin,
        creation.valid,
    )
    geometry_json = _validate_desordre_geometry(cursor, creation)
    if geometry_json is not None:
        target = (
            "public.view_desordres_points_saisie"
            if creation.geometry.type == "Point"
            else "public.desordres"
        )
        cursor.execute(
            f"INSERT INTO {target} ({common_columns}, geometry) "
            "VALUES (%s, %s, %s, %s, %s, %s, "
            "ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 3950)) "
            "RETURNING id",
            (*common_values, geometry_json),
        )
    elif creation.line_endpoints is not None:
        debut_x, debut_y = creation.line_endpoints.debut
        fin_x, fin_y = creation.line_endpoints.fin
        point_sql = "ST_SetSRID(ST_Point(%s, %s), 3950)"
        if creation.line_endpoints.crs == "EPSG:4326":
            point_sql = f"ST_Transform(ST_SetSRID(ST_Point(%s, %s), 4326), 3950)"
        cursor.execute(
            "INSERT INTO public.desordres "
            f"({common_columns}, geometry) "
            "VALUES (%s, %s, %s, %s, %s, %s, "
            f"ST_MakeLine({point_sql}, {point_sql})) RETURNING id",
            (*common_values, debut_x, debut_y, fin_x, fin_y),
        )
    elif creation.reperage is not None:
        troncon_id = creation.troncon_ids[0]
        cursor.execute(
            "SELECT systeme_reperage_defaut_id FROM public.troncons "
            "WHERE id = %s",
            (troncon_id,),
        )
        systeme_id = cursor.fetchone()[0]
        if systeme_id is None:
            raise DesordreCreationError(
                "Le tronçon ne possède aucun système de repérage par défaut."
            )
        start_offset = (
            -creation.reperage.distance_debut_m
            if creation.reperage.position_debut_relative == "AVANT_BORNE"
            else 0.0 if creation.reperage.position_debut_relative == "SUR_BORNE"
            else creation.reperage.distance_debut_m
        )
        if creation.geometry_type == "Point":
            cursor.execute(
                "INSERT INTO public.desordres "
                f"({common_columns}, geometry) "
                "SELECT %s, %s, %s, %s, %s, %s, conversion.point_xy "
                "FROM public.borne_offset_vers_xy(%s, %s, %s, %s) "
                "AS conversion WHERE conversion.statut = 'OK' RETURNING id",
                (
                    *common_values, troncon_id, systeme_id,
                    creation.reperage.borne_debut_id, start_offset,
                ),
            )
        else:
            end_offset = (
                -creation.reperage.distance_fin_m
                if creation.reperage.position_fin_relative == "AVANT_BORNE"
                else 0.0 if creation.reperage.position_fin_relative == "SUR_BORNE"
                else creation.reperage.distance_fin_m
            )
            cursor.execute(
                "INSERT INTO public.desordres "
                f"({common_columns}, geometry) "
                "SELECT %s, %s, %s, %s, %s, %s, "
                "ST_MakeLine(debut.point_xy, fin.point_xy) "
                "FROM public.borne_offset_vers_xy(%s, %s, %s, %s) AS debut "
                "CROSS JOIN public.borne_offset_vers_xy(%s, %s, %s, %s) AS fin "
                "WHERE debut.statut = 'OK' AND fin.statut = 'OK' RETURNING id",
                (
                    *common_values,
                    troncon_id, systeme_id,
                    creation.reperage.borne_debut_id, start_offset,
                    troncon_id, systeme_id,
                    creation.reperage.borne_fin_id, end_offset,
                ),
            )
        row = cursor.fetchone()
        if row is None:
            raise DesordreCreationError("Le bornage proposé est invalide.")
        return row[0]
    elif creation.coord_x_3950 is not None:
        cursor.execute(
            "INSERT INTO public.view_desordres_points_saisie "
            f"({common_columns}, coord_x_3950, coord_y_3950) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (*common_values, creation.coord_x_3950, creation.coord_y_3950),
        )
    else:
        cursor.execute(
            "INSERT INTO public.view_desordres_points_saisie "
            f"({common_columns}, geometry) "
            "VALUES (%s, %s, %s, %s, %s, %s, "
            "ST_Transform(ST_SetSRID(ST_Point(%s, %s), 4326), 3950)) "
            "RETURNING id",
            (*common_values, creation.longitude_4326, creation.latitude_4326),
        )
    row = cursor.fetchone()
    if row is None:
        raise DesordreCreationError("La géométrie proposée est invalide.")
    return row[0]


def create_desordre(connection: Any, creation: DesordreCreate) -> dict[str, Any]:
    """Crée géométrie et liens, puis relit l'état produit par PostGIS."""

    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                _validate_desordre_references(cursor, creation)
                desordre_id = _insert_desordre(cursor, creation)
                if creation.troncon_ids:
                    cursor.execute(
                        "INSERT INTO public.link_desordres_troncons "
                        "(desordre_id, troncon_id) "
                        "SELECT %s, troncon_id FROM unnest(%s::uuid[]) "
                        "AS selected(troncon_id)",
                        (desordre_id, creation.troncon_ids),
                    )
                if creation.reperage is not None:
                    cursor.execute(
                        "SELECT systeme_reperage_defaut_id "
                        "FROM public.troncons WHERE id = %s",
                        (creation.troncon_ids[0],),
                    )
                    systeme_id = cursor.fetchone()[0]
                    cursor.execute(
                        "INSERT INTO public.desordre_localisations_reperage ("
                        "desordre_id, troncon_id, systeme_reperage_id, "
                        "borne_debut_id, distance_debut_m, "
                        "position_debut_relative, borne_fin_id, "
                        "distance_fin_m, position_fin_relative, valid) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, true) "
                        "ON CONFLICT (desordre_id) DO UPDATE SET "
                        "borne_debut_id = EXCLUDED.borne_debut_id, "
                        "distance_debut_m = EXCLUDED.distance_debut_m, "
                        "position_debut_relative = EXCLUDED.position_debut_relative, "
                        "borne_fin_id = EXCLUDED.borne_fin_id, "
                        "distance_fin_m = EXCLUDED.distance_fin_m, "
                        "position_fin_relative = EXCLUDED.position_fin_relative",
                        (
                            desordre_id, creation.troncon_ids[0], systeme_id,
                            creation.reperage.borne_debut_id,
                            creation.reperage.distance_debut_m,
                            creation.reperage.position_debut_relative,
                            creation.reperage.borne_fin_id,
                            creation.reperage.distance_fin_m,
                            creation.reperage.position_fin_relative,
                        ),
                    )
            return fetch_desordre(connection, desordre_id)
    except (DesordreCreationError, WebDatabaseError):
        raise
    except Exception as exc:
        diagnostic = getattr(exc, "diag", None)
        message = getattr(diagnostic, "message_primary", None)
        raise DesordreCreationError(
            str(message or "Création du désordre refusée par PostgreSQL.")
        ) from exc


def fetch_desordres(connection: Any) -> dict[str, Any]:
    """Retourne les désordres Point, LineString et Polygon en EPSG:4326."""

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


def fetch_polygon_desordre(connection: Any, desordre_id: UUID) -> dict[str, Any]:
    """Relit un Polygon et son point représentatif calculé par PostGIS."""

    try:
        with connection.cursor() as cursor:
            cursor.execute(POLYGON_DESORDRE_SQL, (desordre_id,))
            row = cursor.fetchone()
    except Exception as exc:
        raise WebDatabaseError("Lecture du désordre Polygon impossible.") from exc
    if not row:
        raise DesordreNotFoundError("Désordre Polygon introuvable.")
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
    if row[0] == "POLYGON":
        return fetch_polygon_desordre(connection, desordre_id)
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
    """Met à jour métadonnées/liens et, pour un Point, ses coordonnées."""

    values = update.model_dump(exclude_unset=True)
    troncon_ids = values.pop("troncon_ids", None)
    coordinate_fields = {
        "coord_x_3950", "coord_y_3950", "longitude_4326", "latitude_4326"
    }

    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT GeometryType(geometry) FROM public.desordres "
                    "WHERE id = %s FOR UPDATE",
                    (desordre_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise DesordreNotFoundError("Désordre introuvable.")
                geometry_type = row[0]
                if coordinate_fields & values.keys() and geometry_type != "POINT":
                    raise PointDesordreUpdateError(
                        "Les coordonnées numériques directes sont réservées au Point."
                    )
                if "type_desordre_id" in values and values["type_desordre_id"] is not None:
                    cursor.execute(
                        "SELECT 1 FROM public.ref_types_desordre "
                        "WHERE id = %s AND valid",
                        (values["type_desordre_id"],),
                    )
                    if cursor.fetchone() is None:
                        raise PointDesordreUpdateError(
                            "Le type de désordre est absent ou invalide."
                        )
                if values:
                    assignments = [
                        f"{POINT_UPDATE_COLUMNS[field]} = %s" for field in values
                    ]
                    parameters = [values[field] for field in values] + [desordre_id]
                    target = (
                        "public.view_desordres_points_saisie"
                        if geometry_type == "POINT"
                        else "public.desordres"
                    )
                    cursor.execute(
                        f"UPDATE {target} SET " + ", ".join(assignments)
                        + " WHERE id = %s RETURNING id",
                        parameters,
                    )
                    cursor.fetchone()
                if troncon_ids is not None:
                    if geometry_type == "POINT" and len(troncon_ids) > 1:
                        raise PointDesordreUpdateError(
                            "Un désordre Point accepte au plus un tronçon."
                        )
                    if troncon_ids:
                        cursor.execute(
                            "SELECT id FROM public.troncons "
                            "WHERE id = ANY(%s::uuid[]) AND valid FOR SHARE",
                            (troncon_ids,),
                        )
                        if {item[0] for item in cursor.fetchall()} != set(troncon_ids):
                            raise PointDesordreUpdateError(
                                "Au moins un tronçon est absent ou invalide."
                            )
                    cursor.execute(
                        "SELECT troncon_id FROM public.link_desordres_troncons "
                        "WHERE desordre_id = %s FOR UPDATE",
                        (desordre_id,),
                    )
                    current_troncon_ids = {item[0] for item in cursor.fetchall()}
                    requested_troncon_ids = set(troncon_ids)
                    if current_troncon_ids != requested_troncon_ids:
                        # La localisation porte une FK restrictive vers le lien :
                        # elle doit disparaître avant le lien qu'elle référence.
                        cursor.execute(
                            "DELETE FROM public.desordre_localisations_reperage "
                            "WHERE desordre_id = %s",
                            (desordre_id,),
                        )
                        cursor.execute(
                            "DELETE FROM public.link_desordres_troncons "
                            "WHERE desordre_id = %s",
                            (desordre_id,),
                        )
                        if troncon_ids:
                            cursor.execute(
                                "INSERT INTO public.link_desordres_troncons "
                                "(desordre_id, troncon_id) "
                                "SELECT %s, troncon_id FROM unnest(%s::uuid[]) "
                                "AS selected(troncon_id)",
                                (desordre_id, troncon_ids),
                            )
            return fetch_desordre(connection, desordre_id)
    except (PointDesordreNotFoundError, DesordreNotFoundError,
            PointDesordreUpdateError):
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
                    "SELECT GeometryType(geometry) FROM public.desordres "
                    "WHERE id = %s FOR UPDATE",
                    (desordre_id,),
                )
                row = cursor.fetchone()
                if row is None or row[0] not in ("POINT", "LINESTRING"):
                    raise PointDesordreNotFoundError("Désordre repérable introuvable.")
                geometry_type = row[0]
                has_end = update.borne_fin_id is not None
                if geometry_type == "POINT" and has_end:
                    raise PointReperageUpdateError(
                        "Un Point ne possède pas de bornage de fin."
                    )
                if geometry_type == "LINESTRING" and not has_end:
                    raise PointReperageUpdateError(
                        "Une LineString exige un bornage de fin complet."
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
                if update.borne_fin_id is not None:
                    cursor.execute(
                        "SELECT 1 FROM public.link_systemes_reperage_bornes "
                        "WHERE systeme_reperage_id = %s AND borne_id = %s",
                        (systeme_id, update.borne_fin_id),
                    )
                    if cursor.fetchone() is None:
                        raise PointReperageUpdateError(
                            "La borne de fin n'appartient pas au système "
                            "de repérage du tronçon associé."
                        )
                cursor.execute(
                    "UPDATE public.desordre_localisations_reperage SET "
                    "troncon_id = %s, systeme_reperage_id = %s, "
                    "borne_debut_id = %s, distance_debut_m = %s, "
                    "position_debut_relative = %s, borne_fin_id = %s, "
                    "distance_fin_m = %s, position_fin_relative = %s "
                    "WHERE desordre_id = %s RETURNING id",
                    (
                        troncon_id,
                        systeme_id,
                        update.borne_debut_id,
                        update.distance_debut_m,
                        update.position_debut_relative,
                        update.borne_fin_id,
                        update.distance_fin_m,
                        update.position_fin_relative,
                        desordre_id,
                    ),
                )
                if cursor.fetchone() is None:
                    cursor.execute(
                        "INSERT INTO public.desordre_localisations_reperage ("
                        "desordre_id, troncon_id, systeme_reperage_id, "
                        "borne_debut_id, distance_debut_m, "
                        "position_debut_relative, borne_fin_id, "
                        "distance_fin_m, position_fin_relative, valid) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, true) "
                        "RETURNING id",
                        (
                            desordre_id,
                            troncon_id,
                            systeme_id,
                            update.borne_debut_id,
                            update.distance_debut_m,
                            update.position_debut_relative,
                            update.borne_fin_id,
                            update.distance_fin_m,
                            update.position_fin_relative,
                        ),
                    )
                    cursor.fetchone()
            return fetch_desordre(connection, desordre_id)
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
    """Transforme le GeoJSON 4326 en 3950, écrit, puis relit l'objet."""

    geometry_json = json.dumps(update.geometry.model_dump(), allow_nan=False)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT ST_IsValid(candidate.geometry), "
                    "NOT ST_IsEmpty(candidate.geometry), "
                    "CASE WHEN GeometryType(candidate.geometry) = 'LINESTRING' "
                    "THEN ST_NPoints(ST_RemoveRepeatedPoints(candidate.geometry)) >= 2 "
                    "ELSE ST_Area(ST_Transform(candidate.geometry, 3950)) > 0 END "
                    "FROM (SELECT ST_SetSRID("
                    "ST_GeomFromGeoJSON(%s), 4326) AS geometry) AS candidate",
                    (geometry_json,),
                )
                is_valid, is_not_empty, has_distinct_vertices = cursor.fetchone()
                if not is_valid or not is_not_empty or not has_distinct_vertices:
                    raise LineDesordreUpdateError(
                        "La géométrie proposée est invalide ou dégénérée."
                    )
                cursor.execute(
                    "UPDATE public.desordres SET geometry = ST_Transform("
                    "ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 3950) "
                    "WHERE id = %s AND GeometryType(geometry) = "
                    "GeometryType(ST_GeomFromGeoJSON(%s)) "
                    "RETURNING id",
                    (geometry_json, desordre_id, geometry_json),
                )
                if cursor.fetchone() is None:
                    raise LineDesordreNotFoundError(
                        "Désordre introuvable ou type géométrique incompatible."
                    )
            return fetch_desordre(connection, desordre_id)
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


def update_line_desordre_endpoints(
    connection: Any,
    desordre_id: UUID,
    endpoints: LineEndpoints,
) -> dict[str, Any]:
    """Remplace uniquement début/fin et conserve les sommets intermédiaires."""

    debut_x, debut_y = endpoints.debut
    fin_x, fin_y = endpoints.fin
    point_sql = "ST_SetSRID(ST_Point(%s, %s), 3950)"
    if endpoints.crs == "EPSG:4326":
        point_sql = "ST_Transform(ST_SetSRID(ST_Point(%s, %s), 4326), 3950)"
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE public.desordres SET geometry = ST_SetPoint("
                    f"ST_SetPoint(geometry, 0, {point_sql}), "
                    f"ST_NPoints(geometry) - 1, {point_sql}) "
                    "WHERE id = %s AND GeometryType(geometry) = 'LINESTRING' "
                    "AND ST_NPoints(geometry) >= 2 RETURNING id",
                    (debut_x, debut_y, fin_x, fin_y, desordre_id),
                )
                if cursor.fetchone() is None:
                    raise LineDesordreNotFoundError(
                        "Désordre LineString introuvable."
                    )
            return fetch_line_desordre(connection, desordre_id)
    except (LineDesordreNotFoundError, WebDatabaseError):
        raise
    except Exception as exc:
        diagnostic = getattr(exc, "diag", None)
        message = getattr(diagnostic, "message_primary", None)
        raise LineDesordreUpdateError(
            str(message or "Modification des extrémités refusée par PostgreSQL.")
        ) from exc
