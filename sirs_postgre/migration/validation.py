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
    "ref_types_desordre → ref_categories_desordre": """
        SELECT COUNT(*)
        FROM public.ref_types_desordre AS t
        LEFT JOIN public.ref_categories_desordre AS c ON c.id = t.categorie_id
        WHERE c.id IS NULL
    """,
    "digues → systemes": """
        SELECT COUNT(*)
        FROM public.digues AS d
        LEFT JOIN public.systemes AS s
          ON s.id = d.systeme_endiguement_id
        WHERE d.systeme_endiguement_id IS NOT NULL AND s.id IS NULL
    """,
    "troncons → digues": """
        SELECT COUNT(*)
        FROM public.troncons AS t
        LEFT JOIN public.digues AS d ON d.id = t.digue_id
        WHERE d.id IS NULL
    """,
    "liaison → desordres/troncons": """
        SELECT COUNT(*)
        FROM public.link_desordres_troncons AS l
        LEFT JOIN public.desordres AS d ON d.id = l.desordre_id
        LEFT JOIN public.troncons AS t ON t.id = l.troncon_id
        WHERE d.id IS NULL OR t.id IS NULL
    """,
    "observations → desordres": """
        SELECT COUNT(*)
        FROM public.observations AS o
        LEFT JOIN public.desordres AS d ON d.id = o.desordre_id
        WHERE d.id IS NULL
    """,
    "desordres → ref_types_desordre": """
        SELECT COUNT(*)
        FROM public.desordres AS d
        LEFT JOIN public.ref_types_desordre AS t ON t.id = d.type_desordre_id
        WHERE d.type_desordre_id IS NOT NULL AND t.id IS NULL
    """,
    "observations → ref_urgences": """
        SELECT COUNT(*)
        FROM public.observations AS o
        LEFT JOIN public.ref_urgences AS u ON u.id = o.urgence_id
        WHERE o.urgence_id IS NOT NULL AND u.id IS NULL
    """,
    "photos → observations": """
        SELECT COUNT(*)
        FROM public.photos AS p
        LEFT JOIN public.observations AS o ON o.id = p.observation_id
        WHERE o.id IS NULL
    """,
    "SRID troncons": """
        SELECT COUNT(*) FROM public.troncons
        WHERE geometry IS NULL OR ST_SRID(geometry) <> 3950
    """,
    "SRID desordres": """
        SELECT COUNT(*) FROM public.desordres
        WHERE geometry IS NOT NULL AND ST_SRID(geometry) <> 3950
    """,
    "absence categorie_desordre_id dans desordres": """
        SELECT COUNT(*)
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'desordres'
          AND column_name = 'categorie_desordre_id'
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
        "ref_categories_desordre",
        "ref_types_desordre",
        "ref_urgences",
        "systemes",
        "digues",
        "troncons",
        "desordres",
        "observations",
        "photos",
    ):
        cursor.execute(
            f"SELECT COUNT(*) - COUNT(DISTINCT id) FROM public.{table}"
        )
        row = cursor.fetchone()
        if not row or int(row[0]) != 0:
            raise MigrationValidationError(f"Identifiants dupliqués dans {table}")
    cursor.execute(
        "SELECT COUNT(*), COUNT(id), COUNT(DISTINCT id), "
        "COUNT(*) - COUNT(DISTINCT (desordre_id, troncon_id)) "
        "FROM public.link_desordres_troncons"
    )
    row = cursor.fetchone()
    expected_links = expected_counts["link_desordres_troncons"]
    if (
        not row
        or int(row[0]) != expected_links
        or int(row[1]) != expected_links
        or int(row[2]) != expected_links
        or int(row[3]) != 0
    ):
        raise MigrationValidationError(
            "Identifiants techniques ou couples desordre/troncon invalides"
        )

    cursor.execute(
        "SELECT GeometryType(geometry), COUNT(*) FROM public.desordres "
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
