"""Migration du noyau transversal de repérage linéaire SIRS.

Ce module conserve uniquement les systèmes, les bornes et leurs relations
explicites. Il ne migre aucune localisation d'objet ``Positionable`` et ne
déduit jamais une relation depuis une géométrie.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import re
from typing import Any
from uuid import UUID

from .crs import CRSInfo, geometry_sql


SYSTEME_REPERAGE_CLASS = "fr.sirs.core.model.SystemeReperage"
BORNE_DIGUE_CLASS = "fr.sirs.core.model.BorneDigue"

NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?"
POINT_WKT = re.compile(
    rf"^\s*POINT\s*\(\s*{NUMBER}\s+{NUMBER}\s*\)\s*$",
    re.IGNORECASE,
)


class ReperageMigrationError(RuntimeError):
    """Une donnée source empêche une migration fidèle du repérage."""


@dataclass(frozen=True)
class SystemeReperageRow:
    id: UUID
    troncon_id: UUID
    libelle: str | None
    commentaire: str | None
    valid: bool


@dataclass(frozen=True)
class BorneReperageRow:
    id: UUID
    libelle: str | None
    commentaire: str | None
    geometry_wkt: str | None
    fictive: bool | None
    date_debut: date | None
    date_fin: date | None
    valid: bool


@dataclass(frozen=True)
class LinkTronconBorneRow:
    troncon_id: UUID
    borne_id: UUID


@dataclass(frozen=True)
class LinkSystemeReperageBorneRow:
    id: UUID
    systeme_reperage_id: UUID
    borne_id: UUID
    valeur_pr: Decimal
    valid: bool


@dataclass(frozen=True)
class TronconSystemeReperageDefautRow:
    troncon_id: UUID
    systeme_reperage_id: UUID


@dataclass(frozen=True)
class SystemeBorneInconsistency:
    systeme_reperage_id: UUID
    troncon_id: UUID
    borne_id: UUID
    source_object_id: UUID


@dataclass(frozen=True)
class PreparedReperageMigration:
    systemes: tuple[SystemeReperageRow, ...]
    bornes: tuple[BorneReperageRow, ...]
    troncons_bornes: tuple[LinkTronconBorneRow, ...]
    systemes_bornes: tuple[LinkSystemeReperageBorneRow, ...]
    systemes_defaut: tuple[TronconSystemeReperageDefautRow, ...]
    inconsistencies: tuple[SystemeBorneInconsistency, ...]
    warnings: tuple[str, ...]

    @classmethod
    def empty(cls) -> "PreparedReperageMigration":
        return cls((), (), (), (), (), (), ())

    @property
    def expected_counts(self) -> dict[str, int]:
        return {
            "systemes_reperage": len(self.systemes),
            "bornes_reperage": len(self.bornes),
            "link_troncons_bornes": len(self.troncons_bornes),
            "link_systemes_reperage_bornes": len(self.systemes_bornes),
        }

    @property
    def default_system_count(self) -> int:
        return len(self.systemes_defaut)

    @property
    def borne_geometry_counts(self) -> dict[str, int]:
        return {
            "point": sum(row.geometry_wkt is not None for row in self.bornes),
            "null": sum(row.geometry_wkt is None for row in self.bornes),
        }

    @property
    def valeur_pr_by_id(self) -> dict[UUID, Decimal]:
        return {row.id: row.valeur_pr for row in self.systemes_bornes}


def _uuid(value: Any, *, context: str) -> UUID:
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ReperageMigrationError(f"{context}: UUID absent ou invalide : {value!r}") from exc


def _optional_text(document: Mapping[str, Any], field: str, *, context: str) -> str | None:
    value = document.get(field)
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ReperageMigrationError(f"{context}: texte invalide : {field}")
    return value


def _required_bool(document: Mapping[str, Any], field: str, *, context: str) -> bool:
    value = document.get(field)
    if not isinstance(value, bool):
        raise ReperageMigrationError(f"{context}: booléen obligatoire absent : {field}")
    return value


def _optional_bool(document: Mapping[str, Any], field: str, *, context: str) -> bool | None:
    value = document.get(field)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ReperageMigrationError(f"{context}: booléen invalide : {field}")
    return value


def _optional_date(document: Mapping[str, Any], field: str, *, context: str) -> date | None:
    value = document.get(field)
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ReperageMigrationError(f"{context}: date invalide : {field}={value!r}")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ReperageMigrationError(
            f"{context}: date ISO invalide : {field}={value!r}"
        ) from exc


def _optional_point_wkt(value: Any, *, context: str) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or POINT_WKT.fullmatch(value) is None:
        raise ReperageMigrationError(f"{context}: géométrie Point invalide")
    return value


def _decimal(value: Any, *, context: str) -> Decimal:
    if isinstance(value, bool) or value in (None, ""):
        raise ReperageMigrationError(f"{context}: valeurPR absente ou invalide")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ReperageMigrationError(f"{context}: valeurPR invalide : {value!r}") from exc
    if not result.is_finite():
        raise ReperageMigrationError(f"{context}: valeurPR non finie : {value!r}")
    return result


def _mapping_list(value: Any, *, context: str) -> Sequence[Mapping[str, Any]]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, Mapping) for item in value):
        raise ReperageMigrationError(f"{context}: liste invalide")
    return value


def _uuid_list(value: Any, *, context: str) -> tuple[UUID, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ReperageMigrationError(f"{context}: liste invalide")
    return tuple(_uuid(item, context=f"{context}[{index}]") for index, item in enumerate(value))


def prepare_reperage_migration(
    source_documents: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    troncon_ids: set[UUID],
) -> PreparedReperageMigration:
    """Prépare les relations explicites sans aucune inférence spatiale."""

    warnings: list[str] = []

    borne_rows: list[BorneReperageRow] = []
    for document in sorted(
        source_documents.get("BorneDigue", ()),
        key=lambda item: _uuid(item.get("_id"), context="BorneDigue._id").int,
    ):
        borne_id = _uuid(document.get("_id"), context="BorneDigue._id")
        context = f"BorneDigue {document.get('_id')}"
        borne_rows.append(
            BorneReperageRow(
                id=borne_id,
                libelle=_optional_text(document, "libelle", context=context),
                commentaire=_optional_text(document, "commentaire", context=context),
                geometry_wkt=_optional_point_wkt(
                    document.get("geometry"), context=f"{context}.geometry"
                ),
                fictive=_optional_bool(document, "fictive", context=context),
                date_debut=_optional_date(document, "date_debut", context=context),
                date_fin=_optional_date(document, "date_fin", context=context),
                valid=_required_bool(document, "valid", context=context),
            )
        )
    bornes = tuple(borne_rows)
    borne_ids = {row.id for row in bornes}
    if len(borne_ids) != len(bornes):
        raise ReperageMigrationError("BorneDigue: identifiants source dupliqués")

    systeme_rows: list[SystemeReperageRow] = []
    system_documents: dict[UUID, Mapping[str, Any]] = {}
    for document in sorted(
        source_documents.get("SystemeReperage", ()),
        key=lambda item: _uuid(item.get("_id"), context="SystemeReperage._id").int,
    ):
        systeme_id = _uuid(document.get("_id"), context="SystemeReperage._id")
        context = f"SystemeReperage {document.get('_id')}"
        troncon_id = _uuid(document.get("linearId"), context=f"{context}.linearId")
        if troncon_id not in troncon_ids:
            raise ReperageMigrationError(
                f"{context}: linearId référence un tronçon absent"
            )
        systeme_rows.append(
            SystemeReperageRow(
                id=systeme_id,
                troncon_id=troncon_id,
                libelle=_optional_text(document, "libelle", context=context),
                commentaire=_optional_text(document, "commentaire", context=context),
                valid=_required_bool(document, "valid", context=context),
            )
        )
        system_documents[systeme_id] = document
    systemes = tuple(systeme_rows)
    systeme_by_id = {row.id: row for row in systemes}
    if len(systeme_by_id) != len(systemes):
        raise ReperageMigrationError("SystemeReperage: identifiants source dupliqués")

    troncon_links: list[LinkTronconBorneRow] = []
    default_rows: list[TronconSystemeReperageDefautRow] = []
    troncon_borne_pairs: set[tuple[UUID, UUID]] = set()
    for document in source_documents.get("TronconDigue", ()):
        troncon_id = _uuid(document.get("_id"), context="TronconDigue._id")
        if troncon_id not in troncon_ids:
            raise ReperageMigrationError(
                f"TronconDigue {document.get('_id')}: tronçon préparé absent"
            )
        for borne_id in _uuid_list(
            document.get("borneIds"),
            context=f"TronconDigue {document.get('_id')}.borneIds",
        ):
            if borne_id not in borne_ids:
                raise ReperageMigrationError(
                    f"TronconDigue {document.get('_id')}: borneIds référence une borne absente"
                )
            pair = (troncon_id, borne_id)
            if pair in troncon_borne_pairs:
                raise ReperageMigrationError(
                    f"TronconDigue {document.get('_id')}: borneIds contient un doublon"
                )
            troncon_borne_pairs.add(pair)
            troncon_links.append(LinkTronconBorneRow(*pair))

        raw_default_id = document.get("systemeRepDefautId")
        if raw_default_id not in (None, ""):
            default_id = _uuid(
                raw_default_id,
                context=f"TronconDigue {document.get('_id')}.systemeRepDefautId",
            )
            systeme = systeme_by_id.get(default_id)
            if systeme is None:
                raise ReperageMigrationError(
                    f"TronconDigue {document.get('_id')}: système par défaut absent"
                )
            if systeme.troncon_id != troncon_id:
                raise ReperageMigrationError(
                    f"TronconDigue {document.get('_id')}: système par défaut rattaché à un autre tronçon"
                )
            default_rows.append(
                TronconSystemeReperageDefautRow(
                    troncon_id=troncon_id,
                    systeme_reperage_id=default_id,
                )
            )

    system_links: list[LinkSystemeReperageBorneRow] = []
    inconsistencies: list[SystemeBorneInconsistency] = []
    source_link_ids: set[UUID] = set()
    system_borne_pairs: set[tuple[UUID, UUID]] = set()
    for systeme in systemes:
        document = system_documents[systeme.id]
        associations = _mapping_list(
            document.get("systemeReperageBornes"),
            context=f"SystemeReperage {document.get('_id')}.systemeReperageBornes",
        )
        for ordre_source, association in enumerate(associations):
            context = (
                f"SystemeReperage {document.get('_id')}"
                f".systemeReperageBornes[{ordre_source}]"
            )
            source_object_id = _uuid(association.get("id"), context=f"{context}.id")
            if source_object_id in source_link_ids:
                raise ReperageMigrationError(
                    f"{context}: identifiant d'association dupliqué"
                )
            source_link_ids.add(source_object_id)
            borne_id = _uuid(association.get("borneId"), context=f"{context}.borneId")
            if borne_id not in borne_ids:
                raise ReperageMigrationError(
                    f"{context}: borneId référence une borne absente"
                )
            pair = (systeme.id, borne_id)
            if pair in system_borne_pairs:
                raise ReperageMigrationError(
                    f"{context}: couple système-borne dupliqué"
                )
            system_borne_pairs.add(pair)
            system_links.append(
                LinkSystemeReperageBorneRow(
                    id=source_object_id,
                    systeme_reperage_id=systeme.id,
                    borne_id=borne_id,
                    valeur_pr=_decimal(
                        association.get("valeurPR"), context=f"{context}.valeurPR"
                    ),
                    valid=_required_bool(association, "valid", context=context),
                )
            )
            if (systeme.troncon_id, borne_id) not in troncon_borne_pairs:
                inconsistencies.append(
                    SystemeBorneInconsistency(
                        systeme_reperage_id=systeme.id,
                        troncon_id=systeme.troncon_id,
                        borne_id=borne_id,
                        source_object_id=source_object_id,
                    )
                )
                warnings.append(
                    f"SystemeReperage {systeme.id}: borne {borne_id} absente de "
                    f"TronconDigue.borneIds ; relations conservées sans correction"
                )

    return PreparedReperageMigration(
        systemes=systemes,
        bornes=bornes,
        troncons_bornes=tuple(troncon_links),
        systemes_bornes=tuple(system_links),
        systemes_defaut=tuple(default_rows),
        inconsistencies=tuple(inconsistencies),
        warnings=tuple(warnings),
    )


INSERT_STATEMENTS = {
    "systemes_reperage": """
        INSERT INTO public.systemes_reperage
            (id, troncon_id, libelle, commentaire, valid)
        VALUES (%s, %s, %s, %s, %s)
    """,
    "bornes_reperage": f"""
        INSERT INTO public.bornes_reperage
            (id, libelle, commentaire, geometry, fictive,
             date_debut, date_fin, valid)
        VALUES (%s, %s, %s, {geometry_sql()}, %s, %s, %s, %s)
    """,
    "link_troncons_bornes": """
        INSERT INTO public.link_troncons_bornes (troncon_id, borne_id)
        VALUES (%s, %s)
    """,
    "link_systemes_reperage_bornes": """
        INSERT INTO public.link_systemes_reperage_bornes
            (id, systeme_reperage_id, borne_id, valeur_pr, valid)
        VALUES (%s, %s, %s, %s, %s)
    """,
    "troncons_systeme_reperage_defaut": """
        UPDATE public.troncons
        SET systeme_reperage_defaut_id = %s
        WHERE id = %s
    """,
}


def insert_prepared_reperage(
    cursor: Any,
    prepared: PreparedReperageMigration,
    *,
    crs_info: CRSInfo | None = None,
) -> None:
    """Insère le référentiel puis renseigne le système par défaut en dernier."""

    statements = dict(INSERT_STATEMENTS)
    statements["bornes_reperage"] = statements["bornes_reperage"].replace(
        geometry_sql(), geometry_sql(crs_info)
    )
    batches = (
        (
            "systemes_reperage",
            [
                (row.id, row.troncon_id, row.libelle, row.commentaire, row.valid)
                for row in prepared.systemes
            ],
        ),
        (
            "bornes_reperage",
            [
                (
                    row.id,
                    row.libelle,
                    row.commentaire,
                    row.geometry_wkt,
                    row.fictive,
                    row.date_debut,
                    row.date_fin,
                    row.valid,
                )
                for row in prepared.bornes
            ],
        ),
        (
            "link_troncons_bornes",
            [(row.troncon_id, row.borne_id) for row in prepared.troncons_bornes],
        ),
        (
            "link_systemes_reperage_bornes",
            [
                (
                    row.id,
                    row.systeme_reperage_id,
                    row.borne_id,
                    row.valeur_pr,
                    row.valid,
                )
                for row in prepared.systemes_bornes
            ],
        ),
        (
            "troncons_systeme_reperage_defaut",
            [
                (row.systeme_reperage_id, row.troncon_id)
                for row in prepared.systemes_defaut
            ],
        ),
    )
    for name, rows in batches:
        if rows:
            cursor.executemany(statements[name], rows)
