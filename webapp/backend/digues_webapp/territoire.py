"""Persistance du territoire administratif singleton."""

from __future__ import annotations

import json
from typing import Any

from .database import WebDatabaseError
from .territoire_import import TARGET_TERRITORY_SRID


class TerritoireConflictError(ValueError):
    """Un territoire existe déjà et son remplacement n'a pas été demandé."""


class TerritoirePersistenceError(ValueError):
    """PostgreSQL a refusé la géométrie du territoire administratif."""


TERRITOIRE_GEOJSON_SQL = f"""
    SELECT jsonb_build_object(
        'type', 'FeatureCollection',
        'features', coalesce(jsonb_agg(
            jsonb_build_object(
                'type', 'Feature',
                'id', t.id,
                'geometry', ST_AsGeoJSON(ST_Transform(t.geometry, 4326))::jsonb,
                'properties', jsonb_build_object(
                    'id', t.id,
                    'libelle', t.libelle,
                    'srid', ST_SRID(t.geometry)
                )
            ) ORDER BY t.id
        ), '[]'::jsonb)
    )
    FROM public.territoires_administratifs AS t
    WHERE ST_SRID(t.geometry) = {TARGET_TERRITORY_SRID}
"""


TERRITOIRE_VALIDATE_WKB_SQL = f"""
    SELECT
        GeometryType(candidate.geometry),
        ST_IsValid(candidate.geometry),
        NOT ST_IsEmpty(candidate.geometry),
        ST_SRID(candidate.geometry)
    FROM (
        SELECT ST_SetSRID(ST_GeomFromWKB(%s), {TARGET_TERRITORY_SRID}) AS geometry
    ) AS candidate
"""


TERRITOIRE_INSERT_SQL = f"""
    INSERT INTO public.territoires_administratifs (id, libelle, geometry)
    VALUES (
        1,
        %s,
        ST_SetSRID(ST_GeomFromWKB(%s), {TARGET_TERRITORY_SRID})
            ::geometry(Polygon, {TARGET_TERRITORY_SRID})
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id
"""


TERRITOIRE_UPSERT_SQL = f"""
    INSERT INTO public.territoires_administratifs (id, libelle, geometry)
    VALUES (
        1,
        %s,
        ST_SetSRID(ST_GeomFromWKB(%s), {TARGET_TERRITORY_SRID})
            ::geometry(Polygon, {TARGET_TERRITORY_SRID})
    )
    ON CONFLICT (id) DO UPDATE SET
        libelle = EXCLUDED.libelle,
        geometry = EXCLUDED.geometry
    RETURNING id
"""


def fetch_territoire_administratif(connection: Any) -> dict[str, Any]:
    """Retourne le territoire courant en GeoJSON EPSG:4326, ou une collection vide."""

    try:
        with connection.cursor() as cursor:
            cursor.execute(TERRITOIRE_GEOJSON_SQL)
            row = cursor.fetchone()
    except Exception as exc:
        raise WebDatabaseError(
            "Lecture du territoire administratif impossible."
        ) from exc
    result = row[0] if row else None
    if isinstance(result, str):
        result = json.loads(result)
    if not isinstance(result, dict) or result.get("type") != "FeatureCollection":
        raise WebDatabaseError("Réponse GeoJSON du territoire invalide.")
    result.setdefault("features", [])
    return result


def replace_territoire_administratif(
    connection: Any,
    *,
    libelle: str,
    wkb: bytes,
    replace: bool,
) -> dict[str, Any]:
    """Insère ou remplace transactionnellement le singleton id=1."""

    normalized_libelle = libelle.strip()
    if not normalized_libelle:
        raise TerritoirePersistenceError("Le libellé du territoire est obligatoire.")
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(TERRITOIRE_VALIDATE_WKB_SQL, (wkb,))
                row = cursor.fetchone()
                if row is None:
                    raise TerritoirePersistenceError(
                        "La géométrie du territoire est invalide."
                    )
                geometry_type, is_valid, is_not_empty, srid = row
                if (
                    geometry_type != "POLYGON"
                    or not is_valid
                    or not is_not_empty
                    or srid != TARGET_TERRITORY_SRID
                ):
                    raise TerritoirePersistenceError(
                        "La géométrie du territoire est invalide."
                    )

                cursor.execute(
                    TERRITOIRE_UPSERT_SQL if replace else TERRITOIRE_INSERT_SQL,
                    (normalized_libelle, wkb),
                )
                if cursor.fetchone() is None:
                    raise TerritoireConflictError(
                        "Un territoire administratif existe déjà ; "
                        "demander explicitement son remplacement."
                    )
            return fetch_territoire_administratif(connection)
    except (TerritoireConflictError, TerritoirePersistenceError, WebDatabaseError):
        raise
    except Exception as exc:
        diagnostic = getattr(exc, "diag", None)
        message = getattr(diagnostic, "message_primary", None)
        raise TerritoirePersistenceError(
            str(message or "Écriture du territoire refusée par PostgreSQL.")
        ) from exc
