"""Validations post-insertion du noyau migré."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from sirs_postgre.target.schema import EXPECTED_TABLES


class MigrationValidationError(RuntimeError):
    """La cible ne correspond pas aux données source préparées."""


@dataclass(frozen=True)
class CoreValidationResult:
    table_counts: dict[str, int]
    desordre_geometry_counts: dict[str, int]


INTEGRITY_CHECKS = {
    "digue → systeme_endiguement": """
        SELECT COUNT(*)
        FROM public.digue AS d
        LEFT JOIN public.systeme_endiguement AS s
          ON s.id = d.systeme_endiguement_id
        WHERE d.systeme_endiguement_id IS NOT NULL AND s.id IS NULL
    """,
    "troncon → digue": """
        SELECT COUNT(*)
        FROM public.troncon AS t
        LEFT JOIN public.digue AS d ON d.id = t.digue_id
        WHERE d.id IS NULL
    """,
    "liaison → desordre/troncon": """
        SELECT COUNT(*)
        FROM public.link_desordre_troncon AS l
        LEFT JOIN public.desordre AS d ON d.id = l.desordre_id
        LEFT JOIN public.troncon AS t ON t.id = l.troncon_id
        WHERE d.id IS NULL OR t.id IS NULL
    """,
    "observation → desordre": """
        SELECT COUNT(*)
        FROM public.observation AS o
        LEFT JOIN public.desordre AS d ON d.id = o.desordre_id
        WHERE d.id IS NULL
    """,
    "photo → observation": """
        SELECT COUNT(*)
        FROM public.photo AS p
        LEFT JOIN public.observation AS o ON o.id = p.observation_id
        WHERE o.id IS NULL
    """,
    "SRID troncon": """
        SELECT COUNT(*) FROM public.troncon
        WHERE geometry IS NULL OR ST_SRID(geometry) <> 3950
    """,
    "SRID desordre": """
        SELECT COUNT(*) FROM public.desordre
        WHERE geometry IS NOT NULL AND ST_SRID(geometry) <> 3950
    """,
}


def validate_core_migration(
    cursor: Any,
    *,
    expected_counts: Mapping[str, int],
    expected_desordre_geometries: Mapping[str, int],
) -> CoreValidationResult:
    """Compare la cible à la source avant le commit de la transaction."""

    actual_counts: dict[str, int] = {}
    for table in EXPECTED_TABLES:
        cursor.execute(f"SELECT COUNT(*) FROM public.{table}")
        row = cursor.fetchone()
        actual_counts[table] = int(row[0]) if row else -1

    count_errors = [
        f"{table}: attendu {expected_counts[table]}, obtenu {actual_counts[table]}"
        for table in EXPECTED_TABLES
        if actual_counts[table] != expected_counts[table]
    ]
    if count_errors:
        raise MigrationValidationError(
            "Comptes PostgreSQL incohérents : " + "; ".join(count_errors)
        )

    integrity_errors: list[str] = []
    for label, query in INTEGRITY_CHECKS.items():
        cursor.execute(query)
        row = cursor.fetchone()
        violations = int(row[0]) if row else -1
        if violations:
            integrity_errors.append(f"{label}: {violations} violation(s)")
    if integrity_errors:
        raise MigrationValidationError(
            "Intégrité PostgreSQL invalide : " + "; ".join(integrity_errors)
        )

    for table in (
        "systeme_endiguement",
        "digue",
        "troncon",
        "desordre",
        "observation",
        "photo",
    ):
        cursor.execute(
            f"SELECT COUNT(*) - COUNT(DISTINCT id) FROM public.{table}"
        )
        row = cursor.fetchone()
        if not row or int(row[0]) != 0:
            raise MigrationValidationError(f"Identifiants dupliqués dans {table}")
    cursor.execute(
        "SELECT COUNT(*) - COUNT(DISTINCT (desordre_id, troncon_id)) "
        "FROM public.link_desordre_troncon"
    )
    row = cursor.fetchone()
    if not row or int(row[0]) != 0:
        raise MigrationValidationError(
            "Liaisons desordre/troncon dupliquées"
        )

    cursor.execute(
        "SELECT GeometryType(geometry), COUNT(*) FROM public.desordre "
        "WHERE geometry IS NOT NULL GROUP BY GeometryType(geometry)"
    )
    actual_geometries = {
        str(geometry_type).upper(): int(count)
        for geometry_type, count in cursor.fetchall()
    }
    for geometry_type in ("POINT", "LINESTRING"):
        actual_geometries.setdefault(geometry_type, 0)
    expected_non_null = {
        "POINT": expected_desordre_geometries.get("point", 0),
        "LINESTRING": expected_desordre_geometries.get("linestring", 0),
    }
    if actual_geometries != expected_non_null:
        raise MigrationValidationError(
            "Types géométriques des désordres incohérents : "
            f"attendu {expected_non_null}, obtenu {actual_geometries}"
        )

    return CoreValidationResult(
        table_counts=actual_counts,
        desordre_geometry_counts=actual_geometries,
    )
