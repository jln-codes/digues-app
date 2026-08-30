"""Migration déterministe du noyau SIRS CouchDB vers PostgreSQL/PostGIS."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import re
from typing import Any
from uuid import UUID

from sirs_postgre.source import CouchDBClient, connect_couchdb
from sirs_postgre.target import PostgreSQLConfig
from sirs_postgre.target.schema import EXPECTED_TABLES

from .amenagements import (
    AMENAGEMENT_SOURCE_CLASSES,
    PreparedAmenagementsMigration,
    attach_associated_ouvrages,
    insert_prepared_amenagements,
    prepare_amenagements_migration,
)
from .crs import CRSInfo, resolve_source_crs, validate_crs, geometry_sql
from .ouvrages import (
    OUVRAGE_SOURCE_CLASSES,
    PreparedOuvragesMigration,
    insert_prepared_ouvrages,
    prepare_ouvrages_migration,
)
from .media import (
    OWNER_FIELDS,
    MediaMigrationError,
    ObservationRow,
    OwnerBinding,
    PhotoRow,
    prepare_media_migration,
)
from .vegetation import (
    VEGETATION_SOURCE_CLASSES,
    PreparedVegetationMigration,
    insert_prepared_vegetation,
    inspect_wkt,
    prepare_vegetation_migration,
)
from .validation import CoreValidationResult, validate_core_migration


CORE_SOURCE_CLASSES = {
    "RefCategorieDesordre": "fr.sirs.core.model.RefCategorieDesordre",
    "RefTypeDesordre": "fr.sirs.core.model.RefTypeDesordre",
    "RefUrgence": "fr.sirs.core.model.RefUrgence",
    "SystemeEndiguement": "fr.sirs.core.model.SystemeEndiguement",
    "Digue": "fr.sirs.core.model.Digue",
    "TronconDigue": "fr.sirs.core.model.TronconDigue",
    "Desordre": "fr.sirs.core.model.Desordre",
    **OUVRAGE_SOURCE_CLASSES,
    **AMENAGEMENT_SOURCE_CLASSES,
    **VEGETATION_SOURCE_CLASSES,
}

CORE_FIELD_MAPPINGS = {
    "ref_categories_desordre": (
        "_id → texte littéral → id",
        "libelle → texte inchangé → libelle",
        "valid → booléen inchangé → valid",
    ),
    "ref_types_desordre": (
        "_id → texte littéral → id",
        "categorieId → référence texte vérifiée → categorie_id",
        "libelle → texte inchangé → libelle",
        "valid → booléen inchangé → valid",
    ),
    "ref_urgences": (
        "_id → texte littéral → id",
        "libelle → texte inchangé → libelle",
        "valid → booléen inchangé → valid",
    ),
    "systemes": (
        "_id → UUID → id",
        "libelle → texte inchangé → libelle",
        "valid → booléen inchangé → valid",
    ),
    "digues": (
        "_id → UUID → id",
        "systemeEndiguementId absent ou UUID → systeme_endiguement_id nullable",
        "libelle → texte inchangé → libelle",
        "valid → booléen inchangé → valid",
    ),
    "troncons": (
        "_id → UUID → id",
        "digueId → UUID vérifié → digue_id",
        "libelle → texte inchangé → libelle",
        "geometry WKT LINESTRING + CRS global → assignation/reprojection centralisée → geometry EPSG:3950",
        "valid → booléen inchangé → valid",
    ),
    "desordres": (
        "_id → UUID → id",
        "typeDesordreId absent ou référence texte vérifiée → type_desordre_id",
        "categorieDesordreId → contrôle de cohérence uniquement, non stocké",
        "designation/commentaire → textes inchangés → colonnes homonymes",
        "date_debut/date_fin ISO → DATE → colonnes homonymes",
        "positionDebut/positionFin + CRS global → POINT ou LINESTRING reprojeté en 3950 → geometry",
        "valid → booléen inchangé → valid",
        "geometry source Polygon valide → conservée ; autres formes historiques → positions",
    ),
    "link_desordres_troncons": (
        "aucune source → gen_random_uuid() PostgreSQL → id technique",
        "Desordre._id → UUID → desordre_id",
        "Desordre.linearId → UUID de TronconDigue vérifié → troncon_id",
    ),
    "observations": (
        "Objet.observations[].id → UUID → id",
        "UUID de l'objet → exactement une FK métier explicite",
        "urgenceId des désordres absent ou référence texte vérifiée → urgence_id",
        "designation → texte inchangé ou absent → designation nullable",
        "date ISO → DATE → date",
        "evolution → texte inchangé → evolution",
        "valid → booléen inchangé → valid",
        "photos directes objet/date → observation synthétique UUID v5 déterministe",
    ),
    "photos": (
        "Observation.photos[].id ou Objet.photos[].id → UUID → id",
        "Observation.id → UUID injecté → observation_id",
        "chemin → texte inchangé sans déduplication → chemin_source",
        "date ISO → DATE → date",
        "designation → texte inchangé → designation",
        "valid → booléen inchangé → valid",
    ),
    "amenagements_hydrauliques": (
        "_id → UUID historique → id",
        "type source connu → mapping explicite ; absent/inconnu → IND + warning",
        "override nommé par base source → type provisoire isolé",
        "designation/date_debut/valid → colonnes homonymes",
        "geometry WKT POLYGON + CRS global → geometry EPSG:3950",
    ),
    "link_amenagements_troncons": (
        "AmenagementHydraulique._id → amenagement_hydraulique_id",
        "tronconIds explicites uniquement → troncon_id",
        "aucune intersection spatiale utilisée",
    ),
    "ouvrage_associe_amenagement": (
        "amenagementHydrauliqueId explicite → amenagement_hydraulique_id",
        "RefOuvrageAssocieAH:3 → DVS",
        "UUID et WKT historiques conservés dans ouvrages_hydrauliques",
    ),
    "cheminements": (
        "classes/type source explicites → PNT/ESC/CHE/VAC/CAC → type_cheminement_id",
        "_id → UUID historique → id",
        "attributs communs et spécialisés source → colonnes nullables distinctes",
        "geometry WKT + CRS global → assignation/reprojection centralisée → EPSG:3950",
        "aucune géométrie ou relation spatiale n'est inventée",
    ),
    "link_cheminements_troncons": (
        "linearId explicite et valide uniquement → troncon_id",
        "UUID du cheminement source → cheminement_id",
    ),
    "link_cheminements_desordres": (
        "desordreIds explicites et valides uniquement → desordre_id",
        "UUID du cheminement source → cheminement_id",
    ),
    "vegetation": (
        "classes source → nature structurelle ARB/PEU/INV",
        "parcelleId explicite → parcelle_gestion_id",
        "géométrie valide conservée ; reconstruction déterministe sinon",
        "overrides propres à la source isolés dans source_overrides.py",
        "MANUAL_REVIEW → ligne métier conservée avec geometry NULL",
    ),
    "parcelles_gestion_vegetation": (
        "PlanVegetation.planId → plan_id nullable vérifié",
        "geometry WKT LINESTRING + CRS global → geometry EPSG:3950",
        "linearId non stocké directement : relation portée par une table de lien",
    ),
    "link_parcelles_gestion_troncons": (
        "ParcelleVegetation.linearId explicite uniquement → troncon_id",
        "aucune intersection spatiale utilisée",
    ),
}

NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
POINT_WKT = re.compile(
    rf"^\s*POINT\s*\(\s*({NUMBER})\s+({NUMBER})\s*\)\s*$",
    re.IGNORECASE,
)
LINESTRING_WKT = re.compile(r"^\s*LINESTRING\s*\(", re.IGNORECASE)


class CoreMigrationError(RuntimeError):
    """Une donnée source ou une opération cible bloque la migration."""


class TargetNotEmptyError(CoreMigrationError):
    """La cible contient déjà au moins une ligne métier."""


@dataclass(frozen=True)
class ReferenceRow:
    id: str
    libelle: str
    valid: bool


@dataclass(frozen=True)
class TypeDesordreReferenceRow:
    id: str
    categorie_id: str
    libelle: str
    valid: bool


@dataclass(frozen=True)
class SystemeEndiguementRow:
    id: UUID
    libelle: str
    valid: bool


@dataclass(frozen=True)
class DigueRow:
    id: UUID
    systeme_endiguement_id: UUID | None
    libelle: str
    valid: bool


@dataclass(frozen=True)
class TronconRow:
    id: UUID
    digue_id: UUID
    libelle: str
    geometry_wkt: str
    valid: bool


@dataclass(frozen=True)
class DesordreRow:
    id: UUID
    type_desordre_id: str | None
    designation: str | None
    commentaire: str | None
    date_debut: date | None
    date_fin: date | None
    geometry_wkt: str | None
    geometry_kind: str
    valid: bool


@dataclass(frozen=True)
class LinkDesordreTronconRow:
    desordre_id: UUID
    troncon_id: UUID


@dataclass(frozen=True)
class PreparedCoreMigration:
    categories_desordre: tuple[ReferenceRow, ...]
    types_desordre: tuple[TypeDesordreReferenceRow, ...]
    urgences: tuple[ReferenceRow, ...]
    systemes: tuple[SystemeEndiguementRow, ...]
    digues: tuple[DigueRow, ...]
    troncons: tuple[TronconRow, ...]
    desordres: tuple[DesordreRow, ...]
    links: tuple[LinkDesordreTronconRow, ...]
    observations: tuple[ObservationRow, ...]
    photos: tuple[PhotoRow, ...]
    ouvrages: PreparedOuvragesMigration
    amenagements: PreparedAmenagementsMigration
    vegetation: PreparedVegetationMigration
    digues_without_system: int
    desordre_source_geometry_present: int
    desordre_source_geometry_absent: int
    synthetic_observations: int
    direct_troncon_photos: int
    direct_other_photos: int
    warnings: tuple[str, ...]

    @property
    def expected_counts(self) -> dict[str, int]:
        counts = {
            "ref_categories_desordre": len(self.categories_desordre),
            "ref_types_desordre": len(self.types_desordre),
            "ref_urgences": len(self.urgences),
            "systemes": len(self.systemes),
            "digues": len(self.digues),
            "troncons": len(self.troncons),
            "desordres": len(self.desordres),
            "link_desordres_troncons": len(self.links),
            "observations": len(self.observations),
            "photos": len(self.photos),
        }
        counts.update(self.ouvrages.expected_counts)
        counts.update(self.amenagements.expected_counts)
        counts.update(self.vegetation.expected_counts)
        return counts

    @property
    def desordre_geometry_counts(self) -> dict[str, int]:
        return {
            "point": sum(row.geometry_kind == "point" for row in self.desordres),
            "linestring": sum(
                row.geometry_kind == "linestring" for row in self.desordres
            ),
            "polygon": sum(row.geometry_kind == "polygon" for row in self.desordres),
            "null": sum(row.geometry_kind == "null" for row in self.desordres),
        }


@dataclass(frozen=True)
class CoreMigrationReport:
    prepared: PreparedCoreMigration
    validation: CoreValidationResult
    crs_info: CRSInfo | None = None


def couchdb_id_to_uuid(value: Any, *, context: str = "identifiant") -> UUID:
    """Normalise un UUID CouchDB sans modifier ses 128 bits."""

    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise CoreMigrationError(f"{context} invalide : {value!r}") from exc


def validate_troncon_wkt(value: Any, *, context: str = "tronçon") -> str:
    """Valide un WKT LINESTRING 2D sans le réécrire ni le reprojeter."""

    if not isinstance(value, str) or not LINESTRING_WKT.match(value):
        raise CoreMigrationError(f"Géométrie LINESTRING invalide pour {context}")
    return value


def desordre_geometry_from_positions(
    position_debut: Any,
    position_fin: Any,
    *,
    desordre_id: Any,
) -> tuple[str | None, str, str | None]:
    """Construit le WKT cible à partir des deux positions réellement observées."""

    start = POINT_WKT.match(position_debut) if isinstance(position_debut, str) else None
    end = POINT_WKT.match(position_fin) if isinstance(position_fin, str) else None
    if not start or not end:
        warning = (
            f"Desordre {desordre_id}: positions inexploitables ; geometry cible NULL"
        )
        return None, "null", warning
    try:
        start_xy = (Decimal(start.group(1)), Decimal(start.group(2)))
        end_xy = (Decimal(end.group(1)), Decimal(end.group(2)))
    except InvalidOperation:
        warning = (
            f"Desordre {desordre_id}: coordonnées invalides ; geometry cible NULL"
        )
        return None, "null", warning
    if start_xy == end_xy:
        return f"POINT ({start.group(1)} {start.group(2)})", "point", None
    return (
        "LINESTRING "
        f"({start.group(1)} {start.group(2)}, {end.group(1)} {end.group(2)})",
        "linestring",
        None,
    )


def desordre_geometry_from_source(
    source_geometry: Any,
    position_debut: Any,
    position_fin: Any,
    *,
    desordre_id: Any,
) -> tuple[str | None, str, str | None]:
    """Préserve un Polygon source valide, sinon applique le repérage historique.

    Les sources cabbalr ponctuelles et linéaires restent reconstruites depuis
    leurs positions, conformément à la migration historique. Un Polygon SIRS
    explicite et valide est en revanche une géométrie métier autonome.
    """

    if isinstance(source_geometry, str) and source_geometry.lstrip().upper().startswith("POLYGON"):
        geometry = inspect_wkt(source_geometry)
        if geometry is not None and geometry.kind == "POLYGON" and geometry.valid:
            return source_geometry, "polygon", None
        return (
            None,
            "null",
            f"Desordre {desordre_id}: Polygon source invalide ; geometry cible NULL",
        )
    return desordre_geometry_from_positions(
        position_debut,
        position_fin,
        desordre_id=desordre_id,
    )


def _required_text(document: Mapping[str, Any], field: str, context: str) -> str:
    value = document.get(field)
    if not isinstance(value, str) or not value:
        raise CoreMigrationError(f"{context}: champ texte obligatoire absent : {field}")
    return value


def _optional_text(document: Mapping[str, Any], field: str, context: str) -> str | None:
    value = document.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise CoreMigrationError(f"{context}: champ texte invalide : {field}")
    return value


def _required_bool(document: Mapping[str, Any], field: str, context: str) -> bool:
    value = document.get(field)
    if not isinstance(value, bool):
        raise CoreMigrationError(f"{context}: booléen obligatoire absent : {field}")
    return value


def _source_reference_id(value: Any, *, context: str) -> str:
    """Conserve littéralement un identifiant CouchDB de référentiel."""

    if not isinstance(value, str) or not value:
        raise CoreMigrationError(f"{context}: identifiant texte absent ou invalide")
    return value


def _optional_source_reference_id(value: Any, *, context: str) -> str | None:
    if value in (None, ""):
        return None
    return _source_reference_id(value, context=context)


def _optional_date(document: Mapping[str, Any], field: str, context: str) -> date | None:
    value = document.get(field)
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise CoreMigrationError(f"{context}: date invalide : {field}={value!r}")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CoreMigrationError(
            f"{context}: date ISO invalide : {field}={value!r}"
        ) from exc


def _embedded_items(
    document: Mapping[str, Any], field: str, context: str
) -> Sequence[Mapping[str, Any]]:
    value = document.get(field)
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise CoreMigrationError(f"{context}: liste embarquée invalide : {field}")
    return value


def _ensure_unique_ids(rows: Sequence[Any], table: str) -> None:
    ids = [row.id for row in rows]
    if len(ids) != len(set(ids)):
        raise CoreMigrationError(f"Identifiants source dupliqués pour {table}")


def _sorted_documents(
    documents: Sequence[Mapping[str, Any]], *, id_field: str, context: str
) -> list[Mapping[str, Any]]:
    return sorted(
        documents,
        key=lambda document: couchdb_id_to_uuid(
            document.get(id_field), context=f"{context}.{id_field}"
        ).int,
    )


def _sorted_reference_documents(
    documents: Sequence[Mapping[str, Any]], *, context: str
) -> list[Mapping[str, Any]]:
    return sorted(
        documents,
        key=lambda document: _source_reference_id(
            document.get("_id"), context=f"{context}._id"
        ),
    )


def prepare_core_migration(
    source_documents: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    source_database: str | None = None,
) -> PreparedCoreMigration:
    """Transforme les documents live en lignes typées, sans accès PostgreSQL."""

    warnings: list[str] = []

    categories_desordre = tuple(
        ReferenceRow(
            id=_source_reference_id(
                doc.get("_id"), context="RefCategorieDesordre._id"
            ),
            libelle=_required_text(doc, "libelle", "RefCategorieDesordre"),
            valid=_required_bool(doc, "valid", "RefCategorieDesordre"),
        )
        for doc in _sorted_reference_documents(
            source_documents.get("RefCategorieDesordre", ()),
            context="RefCategorieDesordre",
        )
    )
    _ensure_unique_ids(categories_desordre, "ref_categories_desordre")
    categorie_ids = {row.id for row in categories_desordre}

    types_desordre_list: list[TypeDesordreReferenceRow] = []
    for doc in _sorted_reference_documents(
        source_documents.get("RefTypeDesordre", ()), context="RefTypeDesordre"
    ):
        type_id = _source_reference_id(
            doc.get("_id"), context="RefTypeDesordre._id"
        )
        context = f"RefTypeDesordre {type_id}"
        categorie_id = _source_reference_id(
            doc.get("categorieId"), context=f"{context}.categorieId"
        )
        if categorie_id not in categorie_ids:
            raise CoreMigrationError(
                f"{context}: categorieId référence une catégorie absente"
            )
        types_desordre_list.append(
            TypeDesordreReferenceRow(
                id=type_id,
                categorie_id=categorie_id,
                libelle=_required_text(doc, "libelle", context),
                valid=_required_bool(doc, "valid", context),
            )
        )
    types_desordre = tuple(types_desordre_list)
    _ensure_unique_ids(types_desordre, "ref_types_desordre")
    type_categories = {row.id: row.categorie_id for row in types_desordre}

    urgences = tuple(
        ReferenceRow(
            id=_source_reference_id(doc.get("_id"), context="RefUrgence._id"),
            libelle=_required_text(doc, "libelle", "RefUrgence"),
            valid=_required_bool(doc, "valid", "RefUrgence"),
        )
        for doc in _sorted_reference_documents(
            source_documents.get("RefUrgence", ()), context="RefUrgence"
        )
    )
    _ensure_unique_ids(urgences, "ref_urgences")
    urgence_ids = {row.id for row in urgences}

    systemes = tuple(
        SystemeEndiguementRow(
            id=couchdb_id_to_uuid(doc.get("_id"), context="SystemeEndiguement._id"),
            libelle=_required_text(doc, "libelle", "SystemeEndiguement"),
            valid=_required_bool(doc, "valid", "SystemeEndiguement"),
        )
        for doc in _sorted_documents(
            source_documents.get("SystemeEndiguement", ()),
            id_field="_id",
            context="SystemeEndiguement",
        )
    )
    _ensure_unique_ids(systemes, "systemes")
    systeme_ids = {row.id for row in systemes}

    digues_list: list[DigueRow] = []
    digues_without_system = 0
    for doc in _sorted_documents(
        source_documents.get("Digue", ()), id_field="_id", context="Digue"
    ):
        context = f"Digue {doc.get('_id')}"
        raw_systeme_id = doc.get("systemeEndiguementId")
        systeme_id = (
            couchdb_id_to_uuid(raw_systeme_id, context=f"{context}.systemeEndiguementId")
            if raw_systeme_id
            else None
        )
        if systeme_id is None:
            digues_without_system += 1
        elif systeme_id not in systeme_ids:
            raise CoreMigrationError(
                f"{context}: systemeEndiguementId référence un système absent"
            )
        digues_list.append(
            DigueRow(
                id=couchdb_id_to_uuid(doc.get("_id"), context=f"{context}._id"),
                systeme_endiguement_id=systeme_id,
                libelle=_required_text(doc, "libelle", context),
                valid=_required_bool(doc, "valid", context),
            )
        )
    digues = tuple(digues_list)
    _ensure_unique_ids(digues, "digues")
    digue_ids = {row.id for row in digues}

    troncons_list: list[TronconRow] = []
    for doc in _sorted_documents(
        source_documents.get("TronconDigue", ()),
        id_field="_id",
        context="TronconDigue",
    ):
        context = f"TronconDigue {doc.get('_id')}"
        digue_id = couchdb_id_to_uuid(doc.get("digueId"), context=f"{context}.digueId")
        if digue_id not in digue_ids:
            raise CoreMigrationError(f"{context}: digueId référence une digue absente")
        troncons_list.append(
            TronconRow(
                id=couchdb_id_to_uuid(doc.get("_id"), context=f"{context}._id"),
                digue_id=digue_id,
                libelle=_required_text(doc, "libelle", context),
                geometry_wkt=validate_troncon_wkt(doc.get("geometry"), context=context),
                valid=_required_bool(doc, "valid", context),
            )
        )
    troncons = tuple(troncons_list)
    _ensure_unique_ids(troncons, "troncons")
    troncon_ids = {row.id for row in troncons}

    desordres_list: list[DesordreRow] = []
    links_list: list[LinkDesordreTronconRow] = []
    source_geometry_present = 0
    source_geometry_absent = 0
    for doc in _sorted_documents(
        source_documents.get("Desordre", ()), id_field="_id", context="Desordre"
    ):
        raw_id = doc.get("_id")
        context = f"Desordre {raw_id}"
        desordre_id = couchdb_id_to_uuid(raw_id, context=f"{context}._id")
        geometry_wkt, geometry_kind, warning = desordre_geometry_from_source(
            doc.get("geometry"),
            doc.get("positionDebut"),
            doc.get("positionFin"),
            desordre_id=raw_id,
        )
        if warning:
            warnings.append(warning)
        if doc.get("geometry"):
            source_geometry_present += 1
        else:
            source_geometry_absent += 1
        type_desordre_id = _optional_source_reference_id(
            doc.get("typeDesordreId"), context=f"{context}.typeDesordreId"
        )
        source_categorie_id = _optional_source_reference_id(
            doc.get("categorieDesordreId"),
            context=f"{context}.categorieDesordreId",
        )
        if type_desordre_id is not None:
            if type_desordre_id not in type_categories:
                raise CoreMigrationError(
                    f"{context}: typeDesordreId référence un type absent"
                )
            inferred_categorie_id = type_categories[type_desordre_id]
            if (
                source_categorie_id is not None
                and source_categorie_id != inferred_categorie_id
            ):
                warnings.append(
                    f"{context}: categorieDesordreId={source_categorie_id!r} "
                    f"incohérent avec typeDesordreId={type_desordre_id!r} "
                    f"(catégorie du type={inferred_categorie_id!r}) ; "
                    "catégorie source non stockée"
                )
        elif source_categorie_id is not None:
            warnings.append(
                f"{context}: categorieDesordreId={source_categorie_id!r} "
                "renseigné sans typeDesordreId ; type_desordre_id cible NULL"
            )
        desordres_list.append(
            DesordreRow(
                id=desordre_id,
                type_desordre_id=type_desordre_id,
                designation=_optional_text(doc, "designation", context),
                commentaire=_optional_text(doc, "commentaire", context),
                date_debut=_optional_date(doc, "date_debut", context),
                date_fin=_optional_date(doc, "date_fin", context),
                geometry_wkt=geometry_wkt,
                geometry_kind=geometry_kind,
                valid=_required_bool(doc, "valid", context),
            )
        )
        troncon_id = couchdb_id_to_uuid(
            doc.get("linearId"), context=f"{context}.linearId"
        )
        if troncon_id not in troncon_ids:
            raise CoreMigrationError(f"{context}: linearId référence un tronçon absent")
        links_list.append(
            LinkDesordreTronconRow(
                desordre_id=desordre_id,
                troncon_id=troncon_id,
            )
        )

    desordres = tuple(desordres_list)
    links = tuple(links_list)
    _ensure_unique_ids(desordres, "desordres")
    if len(links) != len({(row.desordre_id, row.troncon_id) for row in links}):
        raise CoreMigrationError("Liaisons source desordre/troncon dupliquées")

    if any(label in source_documents for label in OUVRAGE_SOURCE_CLASSES):
        try:
            ouvrages = prepare_ouvrages_migration(
                source_documents,
                troncon_ids=troncon_ids,
                desordre_ids={row.id for row in desordres},
                strict_counts=False,
            )
        except Exception as exc:
            raise CoreMigrationError(f"Bloc Ouvrages invalide : {exc}") from exc
    else:
        ouvrages = PreparedOuvragesMigration.empty()

    if any(label in source_documents for label in AMENAGEMENT_SOURCE_CLASSES):
        try:
            amenagements = prepare_amenagements_migration(
                source_documents,
                troncon_ids=troncon_ids,
                source_database=source_database,
            )
            ouvrages = attach_associated_ouvrages(ouvrages, amenagements)
            warnings.extend(amenagements.warnings)
        except Exception as exc:
            raise CoreMigrationError(
                f"Bloc Aménagements hydrauliques invalide : {exc}"
            ) from exc
    else:
        amenagements = PreparedAmenagementsMigration.empty()

    if any(label in source_documents for label in VEGETATION_SOURCE_CLASSES):
        try:
            vegetation = prepare_vegetation_migration(
                source_documents,
                troncon_ids=troncon_ids,
                source_database=source_database,
            )
            warnings.extend(vegetation.warnings)
        except Exception as exc:
            raise CoreMigrationError(f"Bloc Végétation invalide : {exc}") from exc
    else:
        vegetation = PreparedVegetationMigration.empty()

    owner_bindings: dict[tuple[str, UUID], OwnerBinding] = {}
    owner_bindings.update(
        {("TronconDigue", row.id): OwnerBinding("troncon_id", row.id) for row in troncons}
    )
    owner_bindings.update(
        {("Desordre", row.id): OwnerBinding("desordre_id", row.id) for row in desordres}
    )
    ouvrage_owner_fields = {
        "ouvrages_hydrauliques": "ouvrage_hydraulique_id",
        "equipements_mesure": "equipement_mesure_id",
        "cheminements": "cheminement_id",
        "mobilier": "mobilier_id",
        "reseaux_techniques": "reseau_technique_id",
    }
    for table, rows in ouvrages.rows.items():
        owner_field = ouvrage_owner_fields[table]
        owner_bindings.update(
            {
                (row.source_class, row.id): OwnerBinding(owner_field, row.id)
                for row in rows
            }
        )
    owner_bindings.update(
        {
            ("AmenagementHydraulique", row.id): OwnerBinding(
                "amenagement_hydraulique_id", row.id
            )
            for row in amenagements.amenagements
        }
    )
    owner_bindings.update(
        {
            (row.source_class, row.id): OwnerBinding("vegetation_id", row.id)
            for row in vegetation.vegetation
        }
    )
    try:
        media = prepare_media_migration(
            source_documents,
            owner_bindings=owner_bindings,
            urgence_ids=urgence_ids,
        )
    except MediaMigrationError as exc:
        raise CoreMigrationError(f"Bloc Observations/photos invalide : {exc}") from exc
    warnings.extend(media.warnings)

    return PreparedCoreMigration(
        categories_desordre=categories_desordre,
        types_desordre=types_desordre,
        urgences=urgences,
        systemes=systemes,
        digues=digues,
        troncons=troncons,
        desordres=desordres,
        links=links,
        observations=media.observations,
        photos=media.photos,
        ouvrages=ouvrages,
        amenagements=amenagements,
        vegetation=vegetation,
        digues_without_system=digues_without_system,
        desordre_source_geometry_present=source_geometry_present,
        desordre_source_geometry_absent=source_geometry_absent,
        synthetic_observations=media.synthetic_observation_count,
        direct_troncon_photos=media.direct_troncon_photos,
        direct_other_photos=media.direct_other_photos,
        warnings=tuple(warnings),
    )


INSERT_STATEMENTS = {
    "ref_categories_desordre": """
        INSERT INTO public.ref_categories_desordre (id, libelle, valid)
        VALUES (%s, %s, %s)
    """,
    "ref_types_desordre": """
        INSERT INTO public.ref_types_desordre
            (id, categorie_id, libelle, valid)
        VALUES (%s, %s, %s, %s)
    """,
    "ref_urgences": """
        INSERT INTO public.ref_urgences (id, libelle, valid)
        VALUES (%s, %s, %s)
    """,
    "systemes": """
        INSERT INTO public.systemes (id, libelle, valid)
        VALUES (%s, %s, %s)
    """,
    "digues": """
        INSERT INTO public.digues (id, systeme_endiguement_id, libelle, valid)
        VALUES (%s, %s, %s, %s)
    """,
    "troncons": f"""
        INSERT INTO public.troncons (id, digue_id, libelle, geometry, valid)
        VALUES (%s, %s, %s, {geometry_sql()}, %s)
    """,
    "desordres": f"""
        INSERT INTO public.desordres
            (id, type_desordre_id, designation, commentaire,
             date_debut, date_fin, geometry, valid)
        VALUES (%s, %s, %s, %s, %s, %s, {geometry_sql()}, %s)
    """,
    "link_desordres_troncons": """
        INSERT INTO public.link_desordres_troncons (desordre_id, troncon_id)
        VALUES (%s, %s)
    """,
    "observations": """
        INSERT INTO public.observations
            (id, desordre_id, troncon_id, ouvrage_hydraulique_id,
             equipement_mesure_id, cheminement_id, mobilier_id,
             reseau_technique_id, amenagement_hydraulique_id, vegetation_id,
             urgence_id, designation, date, evolution, valid)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """,
    "photos": """
        INSERT INTO public.photos
            (id, observation_id, chemin_source, date, designation, valid)
        VALUES (%s, %s, %s, %s, %s, %s)
    """,
}


def ensure_target_empty(cursor: Any) -> None:
    non_empty: list[str] = []
    for table in EXPECTED_TABLES:
        cursor.execute(f"SELECT COUNT(*) FROM public.{table}")
        row = cursor.fetchone()
        if row and int(row[0]) > 0:
            non_empty.append(f"{table} ({int(row[0])})")
    if non_empty:
        raise TargetNotEmptyError(
            "La base cible contient déjà des données : " + ", ".join(non_empty)
        )


def _insert_prepared_core(
    cursor: Any,
    prepared: PreparedCoreMigration,
    crs_info: CRSInfo | None = None,
) -> None:
    statements = dict(INSERT_STATEMENTS)
    geometry_expression = geometry_sql(crs_info)
    for table in ("troncons", "desordres"):
        statements[table] = statements[table].replace(
            geometry_sql(), geometry_expression
        )
    batches = (
        (
            "ref_categories_desordre",
            [(row.id, row.libelle, row.valid) for row in prepared.categories_desordre],
        ),
        (
            "ref_types_desordre",
            [
                (row.id, row.categorie_id, row.libelle, row.valid)
                for row in prepared.types_desordre
            ],
        ),
        (
            "ref_urgences",
            [(row.id, row.libelle, row.valid) for row in prepared.urgences],
        ),
        (
            "systemes",
            [(row.id, row.libelle, row.valid) for row in prepared.systemes],
        ),
        (
            "digues",
            [
                (row.id, row.systeme_endiguement_id, row.libelle, row.valid)
                for row in prepared.digues
            ],
        ),
        (
            "troncons",
            [
                (row.id, row.digue_id, row.libelle, row.geometry_wkt, row.valid)
                for row in prepared.troncons
            ],
        ),
        (
            "desordres",
            [
                (
                    row.id,
                    row.type_desordre_id,
                    row.designation,
                    row.commentaire,
                    row.date_debut,
                    row.date_fin,
                    row.geometry_wkt,
                    row.valid,
                )
                for row in prepared.desordres
            ],
        ),
        (
            "link_desordres_troncons",
            [(row.desordre_id, row.troncon_id) for row in prepared.links],
        ),
    )
    for table, rows in batches:
        if rows:
            cursor.executemany(statements[table], rows)
    insert_prepared_amenagements(cursor, prepared.amenagements, crs_info=crs_info)
    insert_prepared_ouvrages(cursor, prepared.ouvrages, crs_info=crs_info)
    insert_prepared_vegetation(cursor, prepared.vegetation, crs_info=crs_info)
    observation_rows = [
        (
            row.id,
            *row.parent_values,
            row.urgence_id,
            row.designation,
            row.date,
            row.evolution,
            row.valid,
        )
        for row in prepared.observations
    ]
    if observation_rows:
        cursor.executemany(statements["observations"], observation_rows)
    photo_rows = [
        (
            row.id,
            row.observation_id,
            row.chemin_source,
            row.date,
            row.designation,
            row.valid,
        )
        for row in prepared.photos
    ]
    if photo_rows:
        cursor.executemany(statements["photos"], photo_rows)


def _default_connector() -> Callable[..., Any]:
    try:
        import psycopg
    except ImportError as exc:
        raise CoreMigrationError("Le pilote psycopg n'est pas installé") from exc
    return psycopg.connect


def execute_core_migration(
    prepared: PreparedCoreMigration,
    config: PostgreSQLConfig | None = None,
    *,
    connector: Callable[..., Any] | None = None,
    crs_info: CRSInfo | None = None,
) -> CoreValidationResult:
    """Insère et valide tout le noyau dans une transaction PostgreSQL unique."""

    selected = config or PostgreSQLConfig.from_env()
    connect = connector or _default_connector()
    try:
        with connect(**selected.connect_kwargs(autocommit=False)) as connection:
            with connection.cursor() as cursor:
                if crs_info is not None:
                    validate_crs(cursor, crs_info)
                ensure_target_empty(cursor)
                _insert_prepared_core(cursor, prepared, crs_info)
                return validate_core_migration(
                    cursor,
                    expected_counts=prepared.expected_counts,
                    expected_desordre_geometries=prepared.desordre_geometry_counts,
                    expected_ouvrage_geometries=prepared.ouvrages.geometry_counts,
                    expected_ouvrage_invalid=prepared.ouvrages.invalid_counts,
                    ouvrages_enabled=prepared.ouvrages.enabled,
                    amenagements_enabled=prepared.amenagements.enabled,
                    expected_amenagement_links=len(prepared.amenagements.links),
                    expected_deferred_chemins=(
                        prepared.amenagements.deferred_chemins
                    ),
                    expected_deferred_prestations=(
                        prepared.amenagements.deferred_prestations
                    ),
                    expected_associated_ouvrage_types=(
                        prepared.amenagements.associated_type_counts
                    ),
                    vegetation_enabled=prepared.vegetation.enabled,
                    expected_vegetation_geometries=(
                        prepared.vegetation.geometry_counts
                    ),
                    expected_vegetation_invalid=(
                        prepared.vegetation.invalid_count
                    ),
                    expected_vegetation_links=len(prepared.vegetation.links),
                    expected_manual_review_ids=(
                        prepared.vegetation.manual_review_ids
                    ),
                )
    except (CoreMigrationError, TargetNotEmptyError):
        raise
    except Exception as exc:
        error = selected.redact_secrets(str(exc))
        raise CoreMigrationError(f"Migration PostgreSQL annulée : {error}") from exc


def fetch_core_documents(client: CouchDBClient) -> dict[str, list[dict[str, Any]]]:
    """Lit uniquement les classes métier et de référence du noyau."""

    return {
        label: client.find_by_class(class_name)
        for label, class_name in CORE_SOURCE_CLASSES.items()
    }


def migrate_core(
    *,
    source_client: CouchDBClient | None = None,
    target_config: PostgreSQLConfig | None = None,
    connector: Callable[..., Any] | None = None,
) -> CoreMigrationReport:
    """Lit CouchDB, transforme, puis migre atomiquement vers PostgreSQL."""

    client = source_client or connect_couchdb()
    crs_info = resolve_source_crs(client.get_database_info())
    documents = fetch_core_documents(client)
    prepared = prepare_core_migration(
        documents,
        source_database=client.config.database,
    )
    validation = execute_core_migration(
        prepared,
        target_config,
        connector=connector,
        crs_info=crs_info,
    )
    return CoreMigrationReport(
        prepared=prepared,
        validation=validation,
        crs_info=crs_info,
    )
