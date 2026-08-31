"""Prototype de migration du repérage historique des seuls désordres."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any
from uuid import UUID, uuid5

from .crs import CRSInfo, geometry_sql
from .reperage import PreparedReperageMigration


LOCALISATION_NAMESPACE = UUID("0479851b-c924-5c55-b1b8-49dbb20ee803")
COHERENCE_TOLERANCE = 1e-3
NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?"
POINT_WKT = re.compile(
    rf"^\s*POINT\s*\(\s*{NUMBER}\s+{NUMBER}\s*\)\s*$",
    re.IGNORECASE,
)
SOURCE_FIELDS = (
    "linearId",
    "foreignParentId",
    "systemeRepId",
    "borneDebutId",
    "borneFinId",
    "borne_debut_distance",
    "borne_fin_distance",
    "borne_debut_aval",
    "borne_fin_aval",
    "prDebut",
    "prFin",
    "positionDebut",
    "positionFin",
    "geometryMode",
    "editedGeoCoordinate",
)


class DesordreReperageMigrationError(RuntimeError):
    """Une localisation de désordre ne peut pas être préparée fidèlement."""


@dataclass(frozen=True)
class DesordreLocalisationReperageRow:
    id: UUID
    desordre_id: UUID
    troncon_id: UUID | None
    systeme_reperage_id: UUID | None
    borne_debut_id: UUID | None
    offset_debut_m: float | None
    borne_fin_id: UUID | None
    offset_fin_m: float | None
    pr_debut_source: Decimal | None
    pr_fin_source: Decimal | None
    position_debut_source_wkt: str | None
    position_fin_source_wkt: str | None
    mode_saisie_source: str
    politique_autorite: str
    qualite: str
    valid: bool
    source_document_id: str
    trace_source: Mapping[str, Any]
    diagnostic_conversion: Mapping[str, Any]


@dataclass(frozen=True)
class PreparedDesordreReperageMigration:
    localisations: tuple[DesordreLocalisationReperageRow, ...]
    source_complete_count: int
    source_partial_count: int
    source_without_reperage_count: int
    warnings: tuple[str, ...]

    @classmethod
    def empty(cls) -> "PreparedDesordreReperageMigration":
        return cls((), 0, 0, 0, ())

    @property
    def expected_counts(self) -> dict[str, int]:
        return {"desordre_localisations_reperage": len(self.localisations)}

    @property
    def structural_quality_counts(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for row in self.localisations:
            result[row.qualite] = result.get(row.qualite, 0) + 1
        return result


def _uuid(value: Any) -> UUID | None:
    if value in (None, ""):
        return None
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _decimal(value: Any) -> Decimal | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _point(value: Any) -> str | None:
    if not isinstance(value, str) or POINT_WKT.fullmatch(value) is None:
        return None
    return value


def _signed_offset(distance: Decimal | None, aval: Any) -> float | None:
    if distance is None or not isinstance(aval, bool):
        return None
    # Convention historique prouvée : aval=true signifie un delta négatif
    # dans le sens géométrique du LineString.
    return float(-distance if aval else distance)


def _distance_and_position(offset: float | None) -> tuple[float | None, str | None]:
    if offset is None:
        return None, None
    if offset < 0:
        return abs(offset), "AVANT_BORNE"
    if offset > 0:
        return offset, "APRES_BORNE"
    return 0.0, "SUR_BORNE"


def _quality_from_issues(issues: Sequence[str]) -> str:
    if any(issue.startswith("CONFLIT_SYSTEME") for issue in issues):
        return "CONFLIT_SYSTEME"
    if any(issue.startswith("REFERENCE_ABSENTE") for issue in issues):
        return "REFERENCE_ABSENTE"
    if issues:
        return "INCOMPLETE"
    return "A_CONTROLER"


def prepare_desordre_reperage_migration(
    documents: Sequence[Mapping[str, Any]],
    *,
    desordre_ids: set[UUID],
    troncon_ids: set[UUID],
    reperage: PreparedReperageMigration,
) -> PreparedDesordreReperageMigration:
    """Prépare une trace 1:N sans inventer de référence opérationnelle."""

    systemes = {row.id: row for row in reperage.systemes}
    borne_ids = {row.id for row in reperage.bornes}
    systeme_borne_pairs = {
        (row.systeme_reperage_id, row.borne_id)
        for row in reperage.systemes_bornes
    }
    rows: list[DesordreLocalisationReperageRow] = []
    warnings: list[str] = []
    complete_count = partial_count = without_reperage_count = 0

    for document in sorted(
        documents,
        key=lambda item: (_uuid(item.get("_id")) or UUID(int=0)).int,
    ):
        raw_id = document.get("_id")
        desordre_id = _uuid(raw_id)
        if desordre_id is None or desordre_id not in desordre_ids:
            raise DesordreReperageMigrationError(
                f"Desordre {raw_id}: identifiant préparé absent ou invalide"
            )
        if not isinstance(document.get("valid"), bool):
            raise DesordreReperageMigrationError(
                f"Desordre {raw_id}: valid absent ou invalide"
            )

        trace = {
            field: document.get(field)
            for field in SOURCE_FIELDS
            if field in document
        }
        if not trace:
            without_reperage_count += 1
            continue

        issues: list[str] = []
        raw_troncon_id = document.get("linearId")
        troncon_id = _uuid(raw_troncon_id)
        if raw_troncon_id in (None, ""):
            issues.append("INCOMPLETE:linearId")
        elif troncon_id is None or troncon_id not in troncon_ids:
            issues.append("REFERENCE_ABSENTE:linearId")
            troncon_id = None

        raw_systeme_id = document.get("systemeRepId")
        systeme_id = _uuid(raw_systeme_id)
        if raw_systeme_id in (None, ""):
            issues.append("INCOMPLETE:systemeRepId")
        elif systeme_id is None or systeme_id not in systemes:
            issues.append("REFERENCE_ABSENTE:systemeRepId")
            systeme_id = None
        elif troncon_id is None:
            systeme_id = None
        elif systemes[systeme_id].troncon_id != troncon_id:
            issues.append("CONFLIT_SYSTEME:troncon")
            systeme_id = None

        resolved_bornes: list[UUID | None] = []
        for field in ("borneDebutId", "borneFinId"):
            raw_borne_id = document.get(field)
            borne_id = _uuid(raw_borne_id)
            if raw_borne_id in (None, ""):
                issues.append(f"INCOMPLETE:{field}")
                borne_id = None
            elif borne_id is None or borne_id not in borne_ids:
                issues.append(f"REFERENCE_ABSENTE:{field}")
                borne_id = None
            elif systeme_id is None:
                borne_id = None
            elif (systeme_id, borne_id) not in systeme_borne_pairs:
                issues.append(f"CONFLIT_SYSTEME:{field}")
                borne_id = None
            resolved_bornes.append(borne_id)

        distance_debut = _decimal(document.get("borne_debut_distance"))
        distance_fin = _decimal(document.get("borne_fin_distance"))
        offset_debut = _signed_offset(
            distance_debut, document.get("borne_debut_aval")
        )
        offset_fin = _signed_offset(distance_fin, document.get("borne_fin_aval"))
        if offset_debut is None:
            issues.append("INCOMPLETE:borne_debut_distance/sens")
        if offset_fin is None:
            issues.append("INCOMPLETE:borne_fin_distance/sens")

        pr_debut = _decimal(document.get("prDebut"))
        pr_fin = _decimal(document.get("prFin"))
        if pr_debut is None:
            issues.append("INCOMPLETE:prDebut")
        if pr_fin is None:
            issues.append("INCOMPLETE:prFin")
        position_debut = _point(document.get("positionDebut"))
        position_fin = _point(document.get("positionFin"))
        if position_debut is None:
            issues.append("INCOMPLETE:positionDebut")
        if position_fin is None:
            issues.append("INCOMPLETE:positionFin")

        has_linear_reperage = any(
            document.get(field) not in (None, "")
            for field in (
                "systemeRepId",
                "borneDebutId",
                "borneFinId",
                "borne_debut_distance",
                "borne_fin_distance",
                "prDebut",
                "prFin",
            )
        )
        if not has_linear_reperage:
            without_reperage_count += 1

        qualite = _quality_from_issues(issues)
        if qualite == "A_CONTROLER":
            complete_count += 1
        elif has_linear_reperage:
            partial_count += 1
        if qualite != "A_CONTROLER":
            warnings.append(
                f"Desordre {raw_id}: localisation de repérage {qualite} "
                f"({', '.join(issues)})"
            )

        rows.append(
            DesordreLocalisationReperageRow(
                id=uuid5(LOCALISATION_NAMESPACE, f"desordre:{desordre_id}"),
                desordre_id=desordre_id,
                troncon_id=troncon_id,
                systeme_reperage_id=systeme_id,
                borne_debut_id=resolved_bornes[0],
                offset_debut_m=(
                    offset_debut if resolved_bornes[0] is not None else None
                ),
                borne_fin_id=resolved_bornes[1],
                offset_fin_m=(
                    offset_fin if resolved_bornes[1] is not None else None
                ),
                pr_debut_source=pr_debut,
                pr_fin_source=pr_fin,
                position_debut_source_wkt=position_debut,
                position_fin_source_wkt=position_fin,
                mode_saisie_source="IMPORT",
                politique_autorite="MANUELLE",
                qualite=qualite,
                valid=bool(document["valid"]),
                source_document_id=str(raw_id),
                trace_source=trace,
                diagnostic_conversion={"preparation": issues},
            )
        )

    ids = [row.id for row in rows]
    if len(ids) != len(set(ids)):
        raise DesordreReperageMigrationError(
            "Identifiants de localisation synthétiques dupliqués"
        )
    return PreparedDesordreReperageMigration(
        localisations=tuple(rows),
        source_complete_count=complete_count,
        source_partial_count=partial_count,
        source_without_reperage_count=without_reperage_count,
        warnings=tuple(warnings),
    )


def _engine_quality(cursor: Any, row: DesordreLocalisationReperageRow, crs_info: CRSInfo | None) -> tuple[str, Mapping[str, Any]]:
    if row.qualite != "A_CONTROLER":
        return row.qualite, row.diagnostic_conversion

    point_expression = geometry_sql(crs_info)
    cursor.execute(
        f"""
        SELECT
            xd.statut, xd.statut_pr, xd.borne_id,
            xd.offset_borne_m, xd.pr,
            xf.statut, xf.statut_pr, xf.borne_id,
            xf.offset_borne_m, xf.pr,
            bd.statut, bd.statut_pr, bd.pr,
            ST_Distance(xd.point_projete, bd.point_xy),
            bf.statut, bf.statut_pr, bf.pr,
            ST_Distance(xf.point_projete, bf.point_xy)
        FROM public.xy_vers_reperage(%s, %s, {point_expression}) AS xd
        CROSS JOIN public.xy_vers_reperage(%s, %s, {point_expression}) AS xf
        CROSS JOIN public.borne_offset_vers_xy(%s, %s, %s, %s) AS bd
        CROSS JOIN public.borne_offset_vers_xy(%s, %s, %s, %s) AS bf
        """,
        (
            row.troncon_id,
            row.systeme_reperage_id,
            row.position_debut_source_wkt,
            row.troncon_id,
            row.systeme_reperage_id,
            row.position_fin_source_wkt,
            row.troncon_id,
            row.systeme_reperage_id,
            row.borne_debut_id,
            row.offset_debut_m,
            row.troncon_id,
            row.systeme_reperage_id,
            row.borne_fin_id,
            row.offset_fin_m,
        ),
    )
    result = cursor.fetchone()
    if not result:
        return "INCOHERENT", {"cause": "MOTEUR_SANS_RESULTAT"}

    statuses = tuple(result[index] for index in (0, 1, 5, 6, 10, 11, 14, 15))
    diagnostics = {
        "statuts": statuses,
        "tolerance": COHERENCE_TOLERANCE,
        "borne_debut_calculee": str(result[2]) if result[2] else None,
        "borne_fin_calculee": str(result[7]) if result[7] else None,
        "ecart_position_debut_m": result[13],
        "ecart_position_fin_m": result[17],
    }
    for status in ("CONFLIT_SYSTEME", "REFERENCE_ABSENTE", "AMBIGU"):
        if status in statuses:
            return status, diagnostics
    if any(status != "OK" for status in statuses):
        return "INCOHERENT", diagnostics

    coherent = (
        UUID(str(result[2])) == row.borne_debut_id
        and UUID(str(result[7])) == row.borne_fin_id
        and abs(float(result[3]) - float(row.offset_debut_m)) <= COHERENCE_TOLERANCE
        and abs(float(result[8]) - float(row.offset_fin_m)) <= COHERENCE_TOLERANCE
        and abs(float(result[4]) - float(row.pr_debut_source)) <= COHERENCE_TOLERANCE
        and abs(float(result[9]) - float(row.pr_fin_source)) <= COHERENCE_TOLERANCE
        and abs(float(result[12]) - float(row.pr_debut_source)) <= COHERENCE_TOLERANCE
        and abs(float(result[16]) - float(row.pr_fin_source)) <= COHERENCE_TOLERANCE
        and float(result[13]) <= COHERENCE_TOLERANCE
        and float(result[17]) <= COHERENCE_TOLERANCE
    )
    return ("OK" if coherent else "INCOHERENT"), diagnostics


INSERT_STATEMENT = f"""
    INSERT INTO public.desordre_localisations_reperage (
        id, desordre_id, troncon_id, systeme_reperage_id,
        borne_debut_id, distance_debut_m, position_debut_relative,
        borne_fin_id, distance_fin_m, position_fin_relative,
        pr_debut_source, pr_fin_source,
        position_debut_source, position_fin_source,
        mode_saisie_source, politique_autorite, qualite, valid,
        source_document_id, trace_source, diagnostic_conversion
    )
    VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        {geometry_sql()}, {geometry_sql()},
        %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb
    )
"""


def insert_prepared_desordre_reperage(
    cursor: Any,
    prepared: PreparedDesordreReperageMigration,
    *,
    crs_info: CRSInfo | None = None,
) -> None:
    """Contrôle chaque chaîne avec le moteur du lot 2 puis l'insère."""

    statement = INSERT_STATEMENT.replace(geometry_sql(), geometry_sql(crs_info))
    rows = []
    for source_row in prepared.localisations:
        qualite, diagnostic = _engine_quality(cursor, source_row, crs_info)
        row = replace(
            source_row,
            qualite=qualite,
            diagnostic_conversion=diagnostic,
        )
        distance_debut, position_debut = _distance_and_position(
            row.offset_debut_m
        )
        distance_fin, position_fin = _distance_and_position(row.offset_fin_m)
        rows.append(
            (
                row.id,
                row.desordre_id,
                row.troncon_id,
                row.systeme_reperage_id,
                row.borne_debut_id,
                distance_debut,
                position_debut,
                row.borne_fin_id,
                distance_fin,
                position_fin,
                row.pr_debut_source,
                row.pr_fin_source,
                row.position_debut_source_wkt,
                row.position_fin_source_wkt,
                row.mode_saisie_source,
                row.politique_autorite,
                row.qualite,
                row.valid,
                row.source_document_id,
                json.dumps(row.trace_source, ensure_ascii=False, sort_keys=True),
                json.dumps(
                    row.diagnostic_conversion,
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                ),
            )
        )
    if rows:
        cursor.executemany(statement, rows)
