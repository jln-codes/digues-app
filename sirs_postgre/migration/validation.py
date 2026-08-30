"""Validations post-insertion du noyau migré."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence
from typing import Any, Mapping
from uuid import UUID

from sirs_postgre.target.schema import EXPECTED_TABLES


class MigrationValidationError(RuntimeError):
    """La cible ne correspond pas aux données source préparées."""


@dataclass(frozen=True)
class CoreValidationResult:
    table_counts: dict[str, int]
    desordre_geometry_counts: dict[str, int]
    vegetation_geometry_counts: dict[str, int]


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
    "observations exactement un parent": """
        SELECT COUNT(*) FROM public.observations
        WHERE num_nonnulls(
            desordre_id, troncon_id, ouvrage_hydraulique_id,
            equipement_mesure_id, ouvrage_franchissement_id, mobilier_id,
            reseau_technique_id, amenagement_hydraulique_id, vegetation_id
        ) <> 1
    """,
    "observations → parents métier": """
        SELECT COUNT(*)
        FROM public.observations AS o
        LEFT JOIN public.desordres AS d ON d.id = o.desordre_id
        LEFT JOIN public.troncons AS t ON t.id = o.troncon_id
        LEFT JOIN public.ouvrages_hydrauliques AS oh
          ON oh.id = o.ouvrage_hydraulique_id
        LEFT JOIN public.equipements_mesure AS em
          ON em.id = o.equipement_mesure_id
        LEFT JOIN public.ouvrages_franchissement AS ofr
          ON ofr.id = o.ouvrage_franchissement_id
        LEFT JOIN public.mobilier AS m ON m.id = o.mobilier_id
        LEFT JOIN public.reseaux_techniques AS rt
          ON rt.id = o.reseau_technique_id
        LEFT JOIN public.amenagements_hydrauliques AS ah
          ON ah.id = o.amenagement_hydraulique_id
        LEFT JOIN public.vegetation AS v ON v.id = o.vegetation_id
        WHERE (o.desordre_id IS NOT NULL AND d.id IS NULL)
           OR (o.troncon_id IS NOT NULL AND t.id IS NULL)
           OR (o.ouvrage_hydraulique_id IS NOT NULL AND oh.id IS NULL)
           OR (o.equipement_mesure_id IS NOT NULL AND em.id IS NULL)
           OR (o.ouvrage_franchissement_id IS NOT NULL AND ofr.id IS NULL)
           OR (o.mobilier_id IS NOT NULL AND m.id IS NULL)
           OR (o.reseau_technique_id IS NOT NULL AND rt.id IS NULL)
           OR (o.amenagement_hydraulique_id IS NOT NULL AND ah.id IS NULL)
           OR (o.vegetation_id IS NOT NULL AND v.id IS NULL)
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
    "types geometry desordres": """
        SELECT COUNT(*) FROM public.desordres
        WHERE geometry IS NOT NULL
          AND GeometryType(geometry) NOT IN ('POINT', 'LINESTRING', 'POLYGON')
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
    expected_ouvrage_geometries: Mapping[str, Mapping[str, int]],
    expected_ouvrage_invalid: Mapping[str, int],
    ouvrages_enabled: bool,
    amenagements_enabled: bool,
    expected_amenagement_links: int,
    expected_deferred_chemins: int,
    expected_deferred_prestations: int,
    expected_associated_ouvrage_types: Mapping[str, int],
    vegetation_enabled: bool,
    expected_vegetation_geometries: Mapping[str, int],
    expected_vegetation_invalid: int,
    expected_vegetation_links: int,
    expected_manual_review_ids: Sequence[UUID],
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

    id_tables = [
        "ref_categories_desordre",
        "ref_types_desordre",
        "ref_urgences",
        "systemes",
        "digues",
        "troncons",
        "desordres",
        "observations",
        "photos",
    ]
    if ouvrages_enabled:
        id_tables.extend(
            (
                "ref_types_ouvrage_hydraulique",
                "ref_types_equipement_mesure",
                "ref_types_ouvrage_franchissement",
                "ref_types_mobilier",
                "ref_types_reseau_technique",
                "ouvrages_hydrauliques",
                "equipements_mesure",
                "ouvrages_franchissement",
                "mobilier",
                "reseaux_techniques",
            )
        )
    if amenagements_enabled:
        id_tables.extend(
            (
                "ref_types_amenagement_hydraulique",
                "amenagements_hydrauliques",
            )
        )
    if vegetation_enabled:
        id_tables.extend(
            (
                "ref_natures_vegetation",
                "ref_etats_sanitaires_vegetation",
                "ref_classes_hauteur_vegetation",
                "ref_classes_diametre_vegetation",
                "plans_gestion_vegetation",
                "parcelles_gestion_vegetation",
                "vegetation",
            )
        )
    for table in id_tables:
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
    for geometry_type in ("POINT", "LINESTRING", "POLYGON"):
        actual_geometries.setdefault(geometry_type, 0)
    expected_non_null = {
        "POINT": expected_desordre_geometries.get("point", 0),
        "LINESTRING": expected_desordre_geometries.get("linestring", 0),
        "POLYGON": expected_desordre_geometries.get("polygon", 0),
    }
    if actual_geometries != expected_non_null:
        raise MigrationValidationError(
            "Types géométriques des désordres incohérents : "
            f"attendu {expected_non_null}, obtenu {actual_geometries}"
        )

    if ouvrages_enabled:
        ouvrage_ref_tables = {
            "ouvrages_hydrauliques": "ref_types_ouvrage_hydraulique",
            "equipements_mesure": "ref_types_equipement_mesure",
            "ouvrages_franchissement": "ref_types_ouvrage_franchissement",
            "mobilier": "ref_types_mobilier",
            "reseaux_techniques": "ref_types_reseau_technique",
        }
        ouvrage_errors: list[str] = []
        for reference_table in ouvrage_ref_tables.values():
            cursor.execute(
                f"SELECT COUNT(*) FROM public.{reference_table} "
                "WHERE id <> abrege OR NOT valid"
            )
            row = cursor.fetchone()
            if not row or int(row[0]) != 0:
                ouvrage_errors.append(
                    f"{reference_table}: id/abrege/valid non conforme"
                )
        for table, reference_table in ouvrage_ref_tables.items():
            cursor.execute(
                f"""
                SELECT COUNT(*)
                FROM public.{table} AS o
                LEFT JOIN public.{reference_table} AS r ON r.id = o.type_id
                WHERE r.id IS NULL
                """
            )
            row = cursor.fetchone()
            if not row or int(row[0]) != 0:
                ouvrage_errors.append(f"{table}: type_id invalide")
            cursor.execute(
                f"""
                SELECT COUNT(*)
                FROM public.{table} AS o
                LEFT JOIN public.troncons AS t ON t.id = o.troncon_id
                WHERE o.troncon_id IS NOT NULL AND t.id IS NULL
                """
            )
            row = cursor.fetchone()
            if not row or int(row[0]) != 0:
                ouvrage_errors.append(f"{table}: troncon_id invalide")
            cursor.execute(
                f"SELECT COUNT(*) FROM public.{table} "
                "WHERE geometry IS NOT NULL AND ST_SRID(geometry) <> 3950"
            )
            row = cursor.fetchone()
            if not row or int(row[0]) != 0:
                ouvrage_errors.append(f"{table}: SRID différent de 3950")
            cursor.execute(
                f"SELECT GeometryType(geometry), COUNT(*) FROM public.{table} "
                "WHERE geometry IS NOT NULL GROUP BY GeometryType(geometry)"
            )
            actual = {
                str(geometry_type).lower(): int(count)
                for geometry_type, count in cursor.fetchall()
            }
            expected = {
                kind: count
                for kind, count in expected_ouvrage_geometries[table].items()
                if kind != "null" and count
            }
            if actual != expected:
                ouvrage_errors.append(
                    f"{table}: géométries attendues {expected}, obtenues {actual}"
                )
            cursor.execute(f"SELECT COUNT(*) FROM public.{table} WHERE NOT valid")
            row = cursor.fetchone()
            actual_invalid = int(row[0]) if row else -1
            if actual_invalid != expected_ouvrage_invalid[table]:
                ouvrage_errors.append(
                    f"{table}: valid=false attendus "
                    f"{expected_ouvrage_invalid[table]}, obtenus {actual_invalid}"
                )

        for table in ("equipements_mesure", "mobilier"):
            cursor.execute(
                f"SELECT COUNT(*) FROM public.{table} "
                "WHERE geometry IS NOT NULL AND GeometryType(geometry) <> 'POINT'"
            )
            row = cursor.fetchone()
            if not row or int(row[0]) != 0:
                ouvrage_errors.append(f"{table}: géométrie autre que Point")

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT id FROM public.ouvrages_hydrauliques
                UNION ALL SELECT id FROM public.equipements_mesure
                UNION ALL SELECT id FROM public.ouvrages_franchissement
                UNION ALL SELECT id FROM public.mobilier
                UNION ALL SELECT id FROM public.reseaux_techniques
            ) AS all_ouvrages
            """
        )
        total_row = cursor.fetchone()
        cursor.execute(
            """
            SELECT COUNT(DISTINCT id)
            FROM (
                SELECT id FROM public.ouvrages_hydrauliques
                UNION ALL SELECT id FROM public.equipements_mesure
                UNION ALL SELECT id FROM public.ouvrages_franchissement
                UNION ALL SELECT id FROM public.mobilier
                UNION ALL SELECT id FROM public.reseaux_techniques
            ) AS all_ouvrages
            """
        )
        distinct_row = cursor.fetchone()
        expected_ouvrage_total = sum(
            expected_counts[table]
            for table in (
                "ouvrages_hydrauliques",
                "equipements_mesure",
                "ouvrages_franchissement",
                "mobilier",
                "reseaux_techniques",
            )
        )
        if (
            not total_row
            or not distinct_row
            or int(total_row[0]) != expected_ouvrage_total
            or int(distinct_row[0]) != expected_ouvrage_total
        ):
            ouvrage_errors.append(
                "UUID Ouvrages non uniques ou total différent de "
                f"{expected_ouvrage_total}"
            )

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM public.ouvrages_hydrauliques AS o
            LEFT JOIN public.amenagements_hydrauliques AS a
              ON a.id = o.amenagement_hydraulique_id
            WHERE o.amenagement_hydraulique_id IS NOT NULL AND a.id IS NULL
            """
        )
        row = cursor.fetchone()
        if not row or int(row[0]) != 0:
            ouvrage_errors.append(
                "ouvrages_hydrauliques: amenagement_hydraulique_id invalide"
            )

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN ('borne_digue', 'bornes_digue')
            """
        )
        row = cursor.fetchone()
        if not row or int(row[0]) != 0:
            ouvrage_errors.append("BorneDigue présent dans le schéma cible")
        if ouvrage_errors:
            raise MigrationValidationError(
                "Validation du bloc Ouvrages invalide : " + "; ".join(ouvrage_errors)
            )

    if amenagements_enabled:
        amenagement_errors: list[str] = []
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM public.ref_types_amenagement_hydraulique
            WHERE id <> abrege OR NOT valid
            """
        )
        row = cursor.fetchone()
        if not row or int(row[0]) != 0:
            amenagement_errors.append("référentiel id/abrege/valid non conforme")

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM public.amenagements_hydrauliques AS a
            LEFT JOIN public.ref_types_amenagement_hydraulique AS r
              ON r.id = a.type_id
            WHERE a.type_id IS NOT NULL AND r.id IS NULL
            """
        )
        row = cursor.fetchone()
        if not row or int(row[0]) != 0:
            amenagement_errors.append("type_id invalide")

        for label, predicate in (
            ("géométrie NULL", "geometry IS NULL"),
            ("SRID différent de 3950", "ST_SRID(geometry) <> 3950"),
            ("géométrie non Polygon", "GeometryType(geometry) <> 'POLYGON'"),
            ("géométrie invalide", "NOT ST_IsValid(geometry)"),
        ):
            cursor.execute(
                "SELECT COUNT(*) FROM public.amenagements_hydrauliques "
                f"WHERE {predicate}"
            )
            row = cursor.fetchone()
            if not row or int(row[0]) != 0:
                amenagement_errors.append(label)

        cursor.execute(
            """
            SELECT COUNT(*), COUNT(id), COUNT(DISTINCT id),
                   COUNT(*) - COUNT(DISTINCT (
                       amenagement_hydraulique_id, troncon_id
                   ))
            FROM public.link_amenagements_troncons
            """
        )
        row = cursor.fetchone()
        if (
            not row
            or int(row[0]) != expected_amenagement_links
            or int(row[1]) != expected_amenagement_links
            or int(row[2]) != expected_amenagement_links
            or int(row[3]) != 0
        ):
            amenagement_errors.append(
                "nombre, identifiants ou couples de liaison invalides"
            )
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM public.link_amenagements_troncons AS l
            LEFT JOIN public.amenagements_hydrauliques AS a
              ON a.id = l.amenagement_hydraulique_id
            LEFT JOIN public.troncons AS t ON t.id = l.troncon_id
            WHERE a.id IS NULL OR t.id IS NULL
            """
        )
        row = cursor.fetchone()
        if not row or int(row[0]) != 0:
            amenagement_errors.append("relation vers aménagement/tronçon invalide")

        cursor.execute(
            """
            SELECT type_id, COUNT(*)
            FROM public.ouvrages_hydrauliques
            WHERE amenagement_hydraulique_id IS NOT NULL
            GROUP BY type_id
            """
        )
        actual_associated_types = {
            str(type_id): int(count) for type_id, count in cursor.fetchall()
        }
        if actual_associated_types != dict(expected_associated_ouvrage_types):
            amenagement_errors.append(
                "ouvrages associés attendus "
                f"{dict(expected_associated_ouvrage_types)}, "
                f"obtenus {actual_associated_types}"
            )

        if expected_deferred_chemins < 0 or expected_deferred_prestations < 0:
            amenagement_errors.append("compteur différé négatif")
        if amenagement_errors:
            raise MigrationValidationError(
                "Validation du bloc Aménagements hydrauliques invalide : "
                + "; ".join(amenagement_errors)
            )

    actual_vegetation_geometries: dict[str, int] = {}
    if vegetation_enabled:
        vegetation_errors: list[str] = []
        for table in (
            "ref_natures_vegetation",
            "ref_etats_sanitaires_vegetation",
            "ref_classes_hauteur_vegetation",
            "ref_classes_diametre_vegetation",
        ):
            cursor.execute(
                f"SELECT COUNT(*) FROM public.{table} "
                "WHERE id <> abrege OR NOT valid"
            )
            row = cursor.fetchone()
            if not row or int(row[0]) != 0:
                vegetation_errors.append(f"{table}: id/abrege/valid non conforme")

        for label, query in (
            (
                "parcelle → plan",
                """
                SELECT COUNT(*)
                FROM public.parcelles_gestion_vegetation AS p
                LEFT JOIN public.plans_gestion_vegetation AS g ON g.id = p.plan_id
                WHERE p.plan_id IS NOT NULL AND g.id IS NULL
                """,
            ),
            (
                "lien parcelle → parcelle/tronçon",
                """
                SELECT COUNT(*)
                FROM public.link_parcelles_gestion_troncons AS l
                LEFT JOIN public.parcelles_gestion_vegetation AS p
                  ON p.id = l.parcelle_gestion_id
                LEFT JOIN public.troncons AS t ON t.id = l.troncon_id
                WHERE p.id IS NULL OR t.id IS NULL
                """,
            ),
            (
                "vegetation → parcelle",
                """
                SELECT COUNT(*)
                FROM public.vegetation AS v
                LEFT JOIN public.parcelles_gestion_vegetation AS p
                  ON p.id = v.parcelle_gestion_id
                WHERE p.id IS NULL
                """,
            ),
            (
                "vegetation → nature",
                """
                SELECT COUNT(*)
                FROM public.vegetation AS v
                LEFT JOIN public.ref_natures_vegetation AS r ON r.id = v.nature_id
                WHERE r.id IS NULL
                """,
            ),
            (
                "vegetation → état sanitaire",
                """
                SELECT COUNT(*)
                FROM public.vegetation AS v
                LEFT JOIN public.ref_etats_sanitaires_vegetation AS r
                  ON r.id = v.etat_sanitaire_id
                WHERE v.etat_sanitaire_id IS NOT NULL AND r.id IS NULL
                """,
            ),
            (
                "vegetation → classe hauteur",
                """
                SELECT COUNT(*)
                FROM public.vegetation AS v
                LEFT JOIN public.ref_classes_hauteur_vegetation AS r
                  ON r.id = v.classe_hauteur_id
                WHERE v.classe_hauteur_id IS NOT NULL AND r.id IS NULL
                """,
            ),
            (
                "vegetation → classe diamètre",
                """
                SELECT COUNT(*)
                FROM public.vegetation AS v
                LEFT JOIN public.ref_classes_diametre_vegetation AS r
                  ON r.id = v.classe_diametre_id
                WHERE v.classe_diametre_id IS NOT NULL AND r.id IS NULL
                """,
            ),
        ):
            cursor.execute(query)
            row = cursor.fetchone()
            if not row or int(row[0]) != 0:
                vegetation_errors.append(f"{label}: référence invalide")

        cursor.execute(
            """
            SELECT COUNT(*), COUNT(id), COUNT(DISTINCT id),
                   COUNT(*) - COUNT(DISTINCT (parcelle_gestion_id, troncon_id))
            FROM public.link_parcelles_gestion_troncons
            """
        )
        row = cursor.fetchone()
        if (
            not row
            or int(row[0]) != expected_vegetation_links
            or int(row[1]) != expected_vegetation_links
            or int(row[2]) != expected_vegetation_links
            or int(row[3]) != 0
        ):
            vegetation_errors.append(
                "nombre, identifiants ou couples parcelle/tronçon invalides"
            )

        for label, predicate in (
            ("parcelle geometry NULL", "geometry IS NULL"),
            ("parcelle SRID différent de 3950", "ST_SRID(geometry) <> 3950"),
            (
                "parcelle géométrie non LineString",
                "GeometryType(geometry) <> 'LINESTRING'",
            ),
            ("parcelle géométrie invalide", "NOT ST_IsValid(geometry)"),
        ):
            cursor.execute(
                "SELECT COUNT(*) FROM public.parcelles_gestion_vegetation "
                f"WHERE {predicate}"
            )
            row = cursor.fetchone()
            if not row or int(row[0]) != 0:
                vegetation_errors.append(label)

        cursor.execute(
            "SELECT GeometryType(geometry), COUNT(*) FROM public.vegetation "
            "WHERE geometry IS NOT NULL GROUP BY GeometryType(geometry)"
        )
        actual_vegetation_geometries = {
            str(geometry_type).lower(): int(count)
            for geometry_type, count in cursor.fetchall()
        }
        for geometry_type in ("point", "linestring", "polygon"):
            actual_vegetation_geometries.setdefault(geometry_type, 0)
        cursor.execute("SELECT COUNT(*) FROM public.vegetation WHERE geometry IS NULL")
        row = cursor.fetchone()
        actual_vegetation_geometries["null"] = int(row[0]) if row else -1
        expected_geometry_counts = {
            geometry_type: int(expected_vegetation_geometries.get(geometry_type, 0))
            for geometry_type in ("point", "linestring", "polygon", "null")
        }
        if actual_vegetation_geometries != expected_geometry_counts:
            vegetation_errors.append(
                "géométries attendues "
                f"{expected_geometry_counts}, obtenues {actual_vegetation_geometries}"
            )

        for label, predicate in (
            ("SRID différent de 3950", "ST_SRID(geometry) <> 3950"),
            (
                "type géométrique interdit",
                "GeometryType(geometry) NOT IN ('POINT', 'LINESTRING', 'POLYGON')",
            ),
            ("géométrie invalide", "NOT ST_IsValid(geometry)"),
        ):
            cursor.execute(
                "SELECT COUNT(*) FROM public.vegetation "
                f"WHERE geometry IS NOT NULL AND {predicate}"
            )
            row = cursor.fetchone()
            if not row or int(row[0]) != 0:
                vegetation_errors.append(label)

        cursor.execute("SELECT COUNT(*) FROM public.vegetation WHERE NOT valid")
        row = cursor.fetchone()
        if not row or int(row[0]) != expected_vegetation_invalid:
            vegetation_errors.append(
                f"valid=false attendus {expected_vegetation_invalid}, "
                f"obtenus {int(row[0]) if row else -1}"
            )

        if expected_manual_review_ids:
            cursor.execute(
                "SELECT COUNT(*) FROM public.vegetation "
                "WHERE id = ANY(%s::uuid[]) AND geometry IS NULL",
                ([str(object_id) for object_id in expected_manual_review_ids],),
            )
            row = cursor.fetchone()
            if not row or int(row[0]) != len(expected_manual_review_ids):
                vegetation_errors.append(
                    "les objets MANUAL_REVIEW ne sont pas tous stockés avec geometry NULL"
                )

        if vegetation_errors:
            raise MigrationValidationError(
                "Validation du bloc Végétation invalide : "
                + "; ".join(vegetation_errors)
            )

    return CoreValidationResult(
        table_counts=actual_counts,
        desordre_geometry_counts=actual_geometries,
        vegetation_geometry_counts=actual_vegetation_geometries,
    )
