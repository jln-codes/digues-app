"""Migration générique des aménagements hydrauliques SIRS."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
import re
from typing import Any
from uuid import UUID

from .crs import CRSInfo, geometry_sql

from .ouvrages import (
    OuvrageRow,
    PreparedOuvragesMigration,
    transform_ouvrage_geometry,
)
from .source_overrides import SourceMigrationOverrides, get_source_overrides


AMENAGEMENT_SOURCE_CLASSES = {
    "AmenagementHydraulique": "fr.sirs.core.model.AmenagementHydraulique",
    "RefTypeAmenagementHydraulique": (
        "fr.sirs.core.model.RefTypeAmenagementHydraulique"
    ),
    "PrestationAmenagementHydraulique": (
        "fr.sirs.core.model.PrestationAmenagementHydraulique"
    ),
    "TraitAmenagementHydraulique": (
        "fr.sirs.core.model.TraitAmenagementHydraulique"
    ),
    "DesordreDependance": "fr.sirs.core.model.DesordreDependance",
}

TARGET_REFERENCE_TABLE = "ref_types_amenagement_hydraulique"
TARGET_AMENAGEMENT_TABLE = "amenagements_hydrauliques"
TARGET_LINK_TABLE = "link_amenagements_troncons"


class AmenagementsMigrationError(RuntimeError):
    """Une donnée aménagement ne peut pas être migrée sans perte silencieuse."""


@dataclass(frozen=True)
class AmenagementTypeReferenceRow:
    id: str
    code: str
    abrege: str
    libelle: str
    valid: bool = True


@dataclass(frozen=True)
class AmenagementHydrauliqueRow:
    id: UUID
    type_id: str
    designation: str | None
    date_debut: date | None
    geometry_wkt: str
    valid: bool


@dataclass(frozen=True)
class LinkAmenagementTronconRow:
    amenagement_hydraulique_id: UUID
    troncon_id: UUID


@dataclass(frozen=True)
class PreparedAmenagementsMigration:
    references: tuple[AmenagementTypeReferenceRow, ...]
    amenagements: tuple[AmenagementHydrauliqueRow, ...]
    links: tuple[LinkAmenagementTronconRow, ...]
    associated_ouvrages: tuple[OuvrageRow, ...]
    deferred_chemins: int
    deferred_prestations: int
    ignored_traits: int
    deferred_desordres_dependance: int
    warnings: tuple[str, ...]
    enabled: bool = True

    @classmethod
    def empty(cls) -> "PreparedAmenagementsMigration":
        return cls((), (), (), (), 0, 0, 0, 0, (), enabled=False)

    @property
    def expected_counts(self) -> dict[str, int]:
        return {
            TARGET_REFERENCE_TABLE: len(self.references),
            TARGET_AMENAGEMENT_TABLE: len(self.amenagements),
            TARGET_LINK_TABLE: len(self.links),
        }

    @property
    def associated_type_counts(self) -> dict[str, int]:
        return dict(Counter(row.type_id for row in self.associated_ouvrages))


TARGET_REFERENCES = (
    AmenagementTypeReferenceRow(
        "ZEC", "zec", "ZEC", "Zone d'expansion des crues"
    ),
    AmenagementTypeReferenceRow("IND", "indefini", "IND", "Indéfini"),
)

# Mapping générique minimal. Les applications peuvent injecter des mappings
# supplémentaires sans modifier le transformateur.
DEFAULT_SOURCE_TYPE_MAPPING: Mapping[str, str] = {
    "RefTypeAmenagementHydraulique:99": "IND",
}

ASSOCIATED_OUVRAGE_TYPE_MAPPING: Mapping[str, str] = {
    "RefOuvrageAssocieAH:1": "TVI",
    "RefOuvrageAssocieAH:2": "VAN",
    "RefOuvrageAssocieAH:3": "DVS",
}

POLYGON_WKT = re.compile(r"^\s*POLYGON\s*\(\s*\(", re.IGNORECASE)
SOURCE_TYPE_FIELDS = ("typeAmenagementHydrauliqueId", "typeId")


def _uuid(value: Any, *, context: str) -> UUID:
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise AmenagementsMigrationError(f"{context} invalide : {value!r}") from exc


def _optional_text(document: Mapping[str, Any], field: str, context: str) -> str | None:
    value = document.get(field)
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise AmenagementsMigrationError(f"{context}.{field} doit être du texte")
    return value


def _optional_date(document: Mapping[str, Any], field: str, context: str) -> date | None:
    value = document.get(field)
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise AmenagementsMigrationError(f"{context}.{field} doit être une date ISO")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise AmenagementsMigrationError(
            f"{context}.{field} date ISO invalide : {value!r}"
        ) from exc


def _required_bool(document: Mapping[str, Any], field: str, context: str) -> bool:
    value = document.get(field)
    if not isinstance(value, bool):
        raise AmenagementsMigrationError(f"{context}.{field} doit être un booléen")
    return value


def _polygon_wkt(value: Any, *, context: str) -> str:
    if not isinstance(value, str) or not POLYGON_WKT.match(value):
        raise AmenagementsMigrationError(
            f"{context}: geometry doit être un WKT POLYGON 2D non NULL"
        )
    return value


def _source_type(document: Mapping[str, Any], *, context: str) -> str | None:
    values = [
        document[field]
        for field in SOURCE_TYPE_FIELDS
        if document.get(field) not in (None, "")
    ]
    if not values:
        return None
    if not all(isinstance(value, str) for value in values):
        raise AmenagementsMigrationError(f"{context}: référence de type invalide")
    if len(set(values)) != 1:
        raise AmenagementsMigrationError(
            f"{context}: champs de type source contradictoires {values!r}"
        )
    return values[0]


def _resolve_type(
    document: Mapping[str, Any],
    *,
    object_id: UUID,
    source_type_mapping: Mapping[str, str],
    overrides: SourceMigrationOverrides,
    warnings: list[str],
) -> tuple[str, bool]:
    context = f"AmenagementHydraulique {object_id}"
    source_type = _source_type(document, context=context)
    if source_type is not None and source_type in source_type_mapping:
        return source_type_mapping[source_type], False

    override_type = overrides.amenagement_type_by_id.get(object_id.hex)
    if override_type is not None:
        return override_type, True

    if source_type is None:
        warnings.append(
            f"{context}: type source absent ; type_id=IND conservatoire"
        )
    else:
        warnings.append(
            f"{context}: type source inconnu {source_type!r} ; "
            "type_id=IND conservatoire"
        )
    return "IND", False


def prepare_amenagements_migration(
    source_documents: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    troncon_ids: set[UUID],
    source_database: str | None = None,
    source_type_mapping: Mapping[str, str] | None = None,
    overrides: SourceMigrationOverrides | None = None,
) -> PreparedAmenagementsMigration:
    """Prépare toutes les lignes sans déduire aucune relation spatiale."""

    selected_mapping = dict(DEFAULT_SOURCE_TYPE_MAPPING)
    if source_type_mapping:
        selected_mapping.update(source_type_mapping)
    selected_overrides = overrides or get_source_overrides(source_database)
    valid_target_types = {row.id for row in TARGET_REFERENCES}
    unknown_targets = set(selected_mapping.values()) - valid_target_types
    unknown_targets.update(
        set(selected_overrides.amenagement_type_by_id.values()) - valid_target_types
    )
    if unknown_targets:
        raise AmenagementsMigrationError(
            f"Types cibles absents du référentiel : {sorted(unknown_targets)!r}"
        )

    warnings: list[str] = []
    amenagements: list[AmenagementHydrauliqueRow] = []
    links: list[LinkAmenagementTronconRow] = []
    amenagement_ids: set[UUID] = set()
    override_count = 0
    documents = sorted(
        source_documents.get("AmenagementHydraulique", ()),
        key=lambda document: _uuid(
            document.get("_id"), context="AmenagementHydraulique._id"
        ).int,
    )
    for document in documents:
        object_id = _uuid(
            document.get("_id"), context="AmenagementHydraulique._id"
        )
        context = f"AmenagementHydraulique {object_id}"
        if object_id in amenagement_ids:
            raise AmenagementsMigrationError(f"UUID aménagement dupliqué : {object_id}")
        amenagement_ids.add(object_id)
        type_id, used_override = _resolve_type(
            document,
            object_id=object_id,
            source_type_mapping=selected_mapping,
            overrides=selected_overrides,
            warnings=warnings,
        )
        override_count += int(used_override)
        amenagements.append(
            AmenagementHydrauliqueRow(
                id=object_id,
                type_id=type_id,
                designation=_optional_text(document, "designation", context),
                date_debut=_optional_date(document, "date_debut", context),
                geometry_wkt=_polygon_wkt(document.get("geometry"), context=context),
                valid=_required_bool(document, "valid", context),
            )
        )
        raw_troncon_ids = document.get("tronconIds") or []
        if not isinstance(raw_troncon_ids, list):
            raise AmenagementsMigrationError(f"{context}.tronconIds doit être une liste")
        normalized_troncons = [
            _uuid(raw_id, context=f"{context}.tronconIds")
            for raw_id in raw_troncon_ids
        ]
        if len(normalized_troncons) != len(set(normalized_troncons)):
            raise AmenagementsMigrationError(f"{context}: tronconIds dupliqués")
        for troncon_id in normalized_troncons:
            if troncon_id not in troncon_ids:
                raise AmenagementsMigrationError(
                    f"{context}: tronconIds référence un tronçon absent"
                )
            links.append(LinkAmenagementTronconRow(object_id, troncon_id))

    if override_count:
        warnings.append(
            f"{override_count} aménagement(s) classé(s) par override spécifique "
            f"à la base {source_database!r}"
        )

    associated_ouvrages: list[OuvrageRow] = []
    associated_ids: set[UUID] = set()
    for document in sorted(
        source_documents.get("OuvrageAssocieAmenagementHydraulique", ()),
        key=lambda item: _uuid(
            item.get("_id"), context="OuvrageAssocieAmenagementHydraulique._id"
        ).int,
    ):
        object_id = _uuid(
            document.get("_id"), context="OuvrageAssocieAmenagementHydraulique._id"
        )
        context = f"OuvrageAssocieAmenagementHydraulique {object_id}"
        if object_id in associated_ids:
            raise AmenagementsMigrationError(f"UUID ouvrage associé dupliqué : {object_id}")
        associated_ids.add(object_id)
        parent_id = _uuid(
            document.get("amenagementHydrauliqueId"),
            context=f"{context}.amenagementHydrauliqueId",
        )
        if parent_id not in amenagement_ids:
            raise AmenagementsMigrationError(
                f"{context}: amenagementHydrauliqueId référence un parent absent"
            )
        source_type = document.get("typeId")
        target_type = ASSOCIATED_OUVRAGE_TYPE_MAPPING.get(str(source_type))
        if target_type is None:
            target_type = "IND"
            warnings.append(
                f"{context}: type source inconnu {source_type!r} ; "
                "ouvrage type_id=IND conservatoire"
            )
        geometry_wkt, geometry_kind = transform_ouvrage_geometry(
            document.get("geometry"), mode="preserve", context=context
        )
        associated_ouvrages.append(
            OuvrageRow(
                id=object_id,
                type_id=target_type,
                designation=_optional_text(document, "designation", context),
                commentaire=_optional_text(document, "commentaire", context),
                date_debut=_optional_date(document, "date_debut", context),
                geometry_wkt=geometry_wkt,
                geometry_kind=geometry_kind,
                troncon_id=None,
                amenagement_hydraulique_id=parent_id,
                valid=_required_bool(document, "valid", context),
                source_class="OuvrageAssocieAmenagementHydraulique",
            )
        )

    return PreparedAmenagementsMigration(
        references=TARGET_REFERENCES,
        amenagements=tuple(amenagements),
        links=tuple(
            sorted(
                links,
                key=lambda row: (
                    row.amenagement_hydraulique_id.int,
                    row.troncon_id.int,
                ),
            )
        ),
        associated_ouvrages=tuple(associated_ouvrages),
        # Les chemins d'accès techniques sont désormais migrés par le bloc
        # Cheminements. Ils ne dépendent pas d'un aménagement hydraulique.
        deferred_chemins=0,
        deferred_prestations=len(
            source_documents.get("PrestationAmenagementHydraulique", ())
        ),
        ignored_traits=len(source_documents.get("TraitAmenagementHydraulique", ())),
        deferred_desordres_dependance=len(
            source_documents.get("DesordreDependance", ())
        ),
        warnings=tuple(warnings),
    )


def attach_associated_ouvrages(
    ouvrages: PreparedOuvragesMigration,
    amenagements: PreparedAmenagementsMigration,
) -> PreparedOuvragesMigration:
    """Ajoute les ouvrages explicitement parents et retire leur report du compteur."""

    if not amenagements.associated_ouvrages:
        return ouvrages
    rows = dict(ouvrages.rows)
    hydraulic_rows = list(rows["ouvrages_hydrauliques"])
    existing_ids = {row.id for table_rows in rows.values() for row in table_rows}
    for row in amenagements.associated_ouvrages:
        if row.id in existing_ids:
            raise AmenagementsMigrationError(f"UUID ouvrage dupliqué : {row.id}")
        hydraulic_rows.append(row)
        existing_ids.add(row.id)
    rows["ouvrages_hydrauliques"] = tuple(
        sorted(hydraulic_rows, key=lambda row: row.id.int)
    )
    deferred_counts = dict(ouvrages.deferred_counts)
    deferred_counts["OuvrageAssocieAmenagementHydraulique"] = max(
        0,
        deferred_counts.get("OuvrageAssocieAmenagementHydraulique", 0)
        - len(amenagements.associated_ouvrages),
    )
    return replace(ouvrages, rows=rows, deferred_counts=deferred_counts)


INSERT_STATEMENTS = {
    TARGET_REFERENCE_TABLE: f"""
        INSERT INTO public.{TARGET_REFERENCE_TABLE}
            (id, code, abrege, libelle, valid)
        VALUES (%s, %s, %s, %s, %s)
    """,
    TARGET_AMENAGEMENT_TABLE: f"""
        INSERT INTO public.{TARGET_AMENAGEMENT_TABLE}
            (id, type_id, designation, date_debut, geometry, valid)
        VALUES (%s, %s, %s, %s, {geometry_sql()}, %s)
    """,
    TARGET_LINK_TABLE: f"""
        INSERT INTO public.{TARGET_LINK_TABLE}
            (amenagement_hydraulique_id, troncon_id)
        VALUES (%s, %s)
    """,
}


def insert_prepared_amenagements(
    cursor: Any,
    prepared: PreparedAmenagementsMigration,
    *,
    crs_info: CRSInfo | None = None,
) -> None:
    """Insère le bloc dans la transaction globale, avant les ouvrages associés."""

    if not prepared.enabled:
        return
    statements = dict(INSERT_STATEMENTS)
    statements[TARGET_AMENAGEMENT_TABLE] = statements[
        TARGET_AMENAGEMENT_TABLE
    ].replace(geometry_sql(), geometry_sql(crs_info))
    cursor.executemany(
        INSERT_STATEMENTS[TARGET_REFERENCE_TABLE],
        [
            (row.id, row.code, row.abrege, row.libelle, row.valid)
            for row in prepared.references
        ],
    )
    if prepared.amenagements:
        cursor.executemany(
            statements[TARGET_AMENAGEMENT_TABLE],
            [
                (
                    row.id,
                    row.type_id,
                    row.designation,
                    row.date_debut,
                    row.geometry_wkt,
                    row.valid,
                )
                for row in prepared.amenagements
            ],
        )
    if prepared.links:
        cursor.executemany(
            INSERT_STATEMENTS[TARGET_LINK_TABLE],
            [
                (row.amenagement_hydraulique_id, row.troncon_id)
                for row in prepared.links
            ],
        )
