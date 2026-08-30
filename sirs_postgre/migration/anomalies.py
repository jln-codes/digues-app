"""Registre persistant et exploitable des anomalies de migration.

Ce module ne corrige aucune donnée source ou cible. Il transforme des constats
structurés en identifiants stables, fusionne les décisions humaines existantes
et écrit les formats JSON/CSV utilisés par le diagnostic.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, fields, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence, TYPE_CHECKING
from uuid import UUID

from .source_overrides import get_source_overrides
from .vegetation import KEEP_NULL, MANUAL_REVIEW, inspect_wkt
from .crs import CRSInfo, CRSResolutionError, crs_hint_is_consistent

if TYPE_CHECKING:
    from .core import PreparedCoreMigration


AUDITS_DIRECTORY = Path(__file__).resolve().parents[2] / "audits"
DEFAULT_JSON_PATH = AUDITS_DIRECTORY / "anomalies.json"
DEFAULT_CSV_PATH = AUDITS_DIRECTORY / "anomalies.csv"


CATEGORIES = frozenset(
    {
        "INVALID_GEOMETRY",
        "MISSING_GEOMETRY",
        "AMBIGUOUS_GEOMETRY",
        "BROKEN_REFERENCE",
        "MISSING_REQUIRED_REFERENCE",
        "AMBIGUOUS_RELATION",
        "UNKNOWN_CLASS",
        "PARTIALLY_MIGRATED_CLASS",
        "UNKNOWN_FIELD",
        "UNMIGRATED_FIELD",
        "UNKNOWN_REFERENCE_VALUE",
        "MISSING_REFERENCE_VALUE",
        "UNMIGRATED_MEDIA",
        "DEFERRED_MEDIA",
        "PHOTO_WITHOUT_DATE",
        "MANUAL_REVIEW",
        "SOURCE_OVERRIDE",
        "DEFERRED_FEATURE",
        "MISSING_SOURCE_CRS",
        "INVALID_SOURCE_CRS",
        "CONFLICTING_SOURCE_CRS",
        "OBJECT_CRS_HINT_CONFLICT",
    }
)
SEVERITIES = frozenset({"INFO", "WARNING", "ERROR", "BLOCKING"})
STATUSES = frozenset(
    {
        "OPEN",
        "RESOLVED_IN_COUCHDB",
        "RESOLVED_IN_POSTGRES",
        "RESOLVED_BY_MIGRATOR",
        "ACCEPTED_AS_IS",
        "IGNORED",
    }
)
RESOLUTION_STATUSES = STATUSES - {"OPEN"}
CORRECTION_LOCATIONS = frozenset(
    {"COUCHDB", "POSTGRESQL", "MIGRATOR", "EITHER", "MANUAL_REVIEW", "NOT_APPLICABLE"}
)

FAMILY_BY_CATEGORY = {
    "INVALID_GEOMETRY": "DATA",
    "MISSING_GEOMETRY": "DATA",
    "AMBIGUOUS_GEOMETRY": "DATA",
    "BROKEN_REFERENCE": "DATA",
    "MISSING_REQUIRED_REFERENCE": "DATA",
    "AMBIGUOUS_RELATION": "DATA",
    "UNKNOWN_REFERENCE_VALUE": "DATA",
    "MISSING_REFERENCE_VALUE": "DATA",
    "UNMIGRATED_MEDIA": "DATA",
    "PHOTO_WITHOUT_DATE": "DATA",
    "MANUAL_REVIEW": "DATA",
    "MISSING_SOURCE_CRS": "DATA",
    "INVALID_SOURCE_CRS": "DATA",
    "CONFLICTING_SOURCE_CRS": "DATA",
    "OBJECT_CRS_HINT_CONFLICT": "DATA",
    "UNKNOWN_CLASS": "COVERAGE",
    "PARTIALLY_MIGRATED_CLASS": "COVERAGE",
    "UNKNOWN_FIELD": "COVERAGE",
    "UNMIGRATED_FIELD": "COVERAGE",
    "DEFERRED_FEATURE": "COVERAGE",
    "DEFERRED_MEDIA": "COVERAGE",
    "SOURCE_OVERRIDE": "MIGRATION_DECISION",
}
ACTIONABLE_CATEGORIES = frozenset(
    category for category, family in FAMILY_BY_CATEGORY.items() if family == "DATA"
)

PREFIX_BY_CATEGORY = {
    "INVALID_GEOMETRY": "GEOM",
    "MISSING_GEOMETRY": "GEOM",
    "AMBIGUOUS_GEOMETRY": "GEOM",
    "MANUAL_REVIEW": "GEOM",
    "BROKEN_REFERENCE": "REL",
    "MISSING_REQUIRED_REFERENCE": "REL",
    "AMBIGUOUS_RELATION": "REL",
    "UNKNOWN_REFERENCE_VALUE": "REF",
    "MISSING_REFERENCE_VALUE": "REF",
    "UNKNOWN_CLASS": "CLASS",
    "PARTIALLY_MIGRATED_CLASS": "CLASS",
    "UNKNOWN_FIELD": "FIELD",
    "UNMIGRATED_FIELD": "FIELD",
    "UNMIGRATED_MEDIA": "MEDIA",
    "DEFERRED_MEDIA": "MEDIA",
    "PHOTO_WITHOUT_DATE": "MEDIA",
    "SOURCE_OVERRIDE": "OVERRIDE",
    "DEFERRED_FEATURE": "DEFER",
    "MISSING_SOURCE_CRS": "CRS",
    "INVALID_SOURCE_CRS": "CRS",
    "CONFLICTING_SOURCE_CRS": "CRS",
    "OBJECT_CRS_HINT_CONFLICT": "CRS",
}

REGISTER_FIELDS = (
    "anomaly_id",
    "category",
    "severity",
    "status",
    "active",
    "source_database",
    "source_class",
    "source_document_id",
    "source_object_id",
    "source_field",
    "target_table",
    "target_id",
    "target_field",
    "message",
    "details",
    "suggested_action",
    "correction_location",
    "detected_value",
    "expected_value",
    "first_detected_at",
    "last_detected_at",
    "resolved_detected_at",
    "resolution_comment",
)

CSV_FIELDS = (
    "anomaly_id",
    "active",
    "actionable",
    "status",
    "severity",
    "family",
    "category",
    "source_class",
    "source_document_id",
    "source_object_id",
    *(
        field
        for field in REGISTER_FIELDS
        if field
        not in {
            "anomaly_id",
            "active",
            "status",
            "severity",
            "category",
            "source_class",
            "source_document_id",
            "source_object_id",
        }
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def make_anomaly_id(
    *,
    source_database: str | None,
    source_class: str | None,
    stable_subject_id: str | None,
    category: str,
    source_field: str | None,
) -> str:
    """Construit l'identité logique stable sans dépendre du message."""

    identity = "\x1f".join(
        (
            source_database or "",
            source_class or "",
            stable_subject_id or "",
            category,
            source_field or "",
        )
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20].upper()
    return f"{PREFIX_BY_CATEGORY.get(category, 'ANOM')}-{digest}"


@dataclass(frozen=True)
class Anomaly:
    anomaly_id: str
    category: str
    severity: str
    status: str = "OPEN"
    active: bool = True
    source_database: str | None = None
    source_class: str | None = None
    source_document_id: str | None = None
    source_object_id: str | None = None
    source_field: str | None = None
    target_table: str | None = None
    target_id: str | None = None
    target_field: str | None = None
    message: str = ""
    details: Any = None
    suggested_action: str | None = None
    correction_location: str = "NOT_APPLICABLE"
    detected_value: Any = None
    expected_value: Any = None
    first_detected_at: str | None = None
    last_detected_at: str | None = None
    resolved_detected_at: str | None = None
    resolution_comment: str | None = None

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise ValueError(f"Catégorie d'anomalie inconnue : {self.category}")
        if self.severity not in SEVERITIES:
            raise ValueError(f"Sévérité d'anomalie inconnue : {self.severity}")
        if self.status not in STATUSES:
            raise ValueError(f"Statut d'anomalie inconnu : {self.status}")
        if self.correction_location not in CORRECTION_LOCATIONS:
            raise ValueError(
                f"Lieu de correction inconnu : {self.correction_location}"
            )

    @classmethod
    def create(
        cls,
        *,
        category: str,
        severity: str,
        source_database: str | None,
        source_class: str | None,
        stable_subject_id: str | None = None,
        source_field: str | None = None,
        **values: Any,
    ) -> "Anomaly":
        return cls(
            anomaly_id=make_anomaly_id(
                source_database=source_database,
                source_class=source_class,
                stable_subject_id=stable_subject_id,
                category=category,
                source_field=source_field,
            ),
            category=category,
            severity=severity,
            source_database=source_database,
            source_class=source_class,
            source_field=source_field,
            **values,
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Anomaly":
        known = {field.name for field in fields(cls)}
        return cls(**{key: value[key] for key in known if key in value})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_actionable(anomaly: Anomaly) -> bool:
    """Règle unique partagée par la CLI et la vue CSV exploitable."""

    return (
        anomaly.active
        and anomaly.status == "OPEN"
        and anomaly.category in ACTIONABLE_CATEGORIES
    )


@dataclass(frozen=True)
class AnomalyRegisterResult:
    anomalies: tuple[Anomaly, ...]
    json_path: Path
    csv_path: Path

    @property
    def active(self) -> tuple[Anomaly, ...]:
        return tuple(anomaly for anomaly in self.anomalies if anomaly.active)

    @property
    def counts_by_severity(self) -> dict[str, int]:
        return {
            severity: sum(
                anomaly.active and anomaly.severity == severity
                for anomaly in self.anomalies
            )
            for severity in ("INFO", "WARNING", "ERROR", "BLOCKING")
        }

    @property
    def open_count(self) -> int:
        return sum(
            anomaly.active and anomaly.status == "OPEN"
            for anomaly in self.anomalies
        )

    @property
    def resolved_count(self) -> int:
        return sum(anomaly.status.startswith("RESOLVED_") for anomaly in self.anomalies)

    @property
    def active_counts_by_family(self) -> dict[str, int]:
        return {
            family: sum(
                anomaly.active
                and FAMILY_BY_CATEGORY[anomaly.category] == family
                for anomaly in self.anomalies
            )
            for family in ("DATA", "COVERAGE", "MIGRATION_DECISION")
        }


def _normal_uuid(value: Any) -> str | None:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return str(value) if value not in (None, "") else None


def _source_document_id(document: Mapping[str, Any]) -> str | None:
    """Retourne le ``_id`` CouchDB brut, sans aucune normalisation UUID."""

    value = document.get("_id")
    return str(value) if value not in (None, "") else None


def _source_object_id(value: Any) -> str | None:
    """Conserve l'identifiant exact d'un sous-objet JSON, sans normalisation."""

    return str(value) if value not in (None, "") else None


def _geometry_details(document: Mapping[str, Any]) -> dict[str, Any]:
    geometry = inspect_wkt(document.get("geometry"))
    if geometry is None:
        return {"geometry_type": None, "valid": None, "reason": "absente"}
    return {
        "geometry_type": geometry.kind,
        "valid": geometry.valid,
        "reason": geometry.reason,
        "coordinate_count": len(geometry.coordinates),
    }


def _document_index(
    documents: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], Mapping[str, Any]]:
    result: dict[tuple[str, str], Mapping[str, Any]] = {}
    for document in documents:
        class_name = str(document.get("@class") or "").rsplit(".", 1)[-1]
        source_id = _normal_uuid(document.get("_id"))
        if class_name and source_id:
            result[(class_name, source_id)] = document
    return result


def _embedded_photo_occurrences(
    grouped: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[
    dict[str, list[dict[str, str | None]]],
    list[dict[str, str | None]],
]:
    """Indexe les photos directes et sous observations sans lire les pièces jointes."""

    by_id: dict[str, list[dict[str, str | None]]] = {}
    missing_ids: list[dict[str, str | None]] = []
    for class_name, documents in grouped.items():
        for document in documents:
            source_document_id = _source_document_id(document)
            containers: list[tuple[str, Any]] = [("photos", document.get("photos"))]
            observations = document.get("observations") or ()
            if isinstance(observations, Sequence) and not isinstance(
                observations, (str, bytes)
            ):
                for observation_index, observation in enumerate(observations):
                    if isinstance(observation, Mapping):
                        containers.append(
                            (
                                f"observations[{observation_index}].photos",
                                observation.get("photos"),
                            )
                        )
            for container, raw_photos in containers:
                photos = raw_photos or ()
                if not isinstance(photos, Sequence) or isinstance(photos, (str, bytes)):
                    continue
                for photo_index, photo in enumerate(photos):
                    if not isinstance(photo, Mapping):
                        continue
                    occurrence = {
                        "source_class": class_name,
                        "source_document_id": source_document_id,
                        "source_object_id": _source_object_id(
                            photo.get("id") or photo.get("_id")
                        ),
                        "source_field": f"{container}[{photo_index}].id",
                    }
                    photo_id = _normal_uuid(photo.get("id") or photo.get("_id"))
                    if photo_id is None:
                        missing_ids.append(occurrence)
                    else:
                        by_id.setdefault(photo_id, []).append(occurrence)
    return by_id, missing_ids


REFERENCE_SPECS = {
    "Digue": (("systemeEndiguementId", "SystemeEndiguement", False),),
    "TronconDigue": (("digueId", "Digue", True),),
    "Desordre": (("linearId", "TronconDigue", True),),
    "ParcelleVegetation": (("planId", "PlanVegetation", False), ("linearId", "TronconDigue", True)),
    "ArbreVegetation": (("parcelleId", "ParcelleVegetation", True),),
    "PeuplementVegetation": (("parcelleId", "ParcelleVegetation", True),),
    "InvasiveVegetation": (("parcelleId", "ParcelleVegetation", True),),
}

NON_ACTIONABLE_FIELDS = frozenset(
    {
        "_attachments",
        "cartoEdited",
        "contactEau",
        "createFromMobile",
        "crsName",
        "foreignParentId",
        "lastDegreUrgence",
        "lastObservation",
        "positionId",
        "sourceId",
        "typeCoteId",
        "typePositionId",
    }
)


def collect_anomalies(
    documents: Sequence[Mapping[str, Any]],
    *,
    source_database: str | None,
    coverage_rows: Sequence[Mapping[str, Any]],
    prepared_core: "PreparedCoreMigration | None" = None,
    crs_info: CRSInfo | None = None,
    crs_error: CRSResolutionError | None = None,
) -> tuple[Anomaly, ...]:
    """Collecte des constats actionnables sans modifier les données."""

    anomalies: list[Anomaly] = []
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for document in documents:
        class_name = str(document.get("@class") or "<SANS_@class>").rsplit(".", 1)[-1]
        grouped.setdefault(class_name, []).append(document)
    coverage_by_class = {str(row["class"]): row for row in coverage_rows}

    if crs_error is not None:
        anomalies.append(
            Anomaly.create(
                category=crs_error.category,
                severity="BLOCKING",
                source_database=source_database,
                source_class="$sirs",
                stable_subject_id="$sirs",
                source_document_id=("$sirs" if any(
                    _source_document_id(document) == "$sirs" for document in documents
                ) else None),
                source_field="epsgCode",
                message=str(crs_error),
                suggested_action=(
                    "Corriger $sirs.epsgCode dans CouchDB ou configurer "
                    "explicitement SIRS_SOURCE_SRID."
                ),
                correction_location="EITHER",
                expected_value="code EPSG résolvable et non contradictoire",
            )
        )
    elif crs_info is not None:
        for class_name, class_documents in grouped.items():
            for document in class_documents:
                hint = document.get("crsName")
                if hint in (None, "") or crs_hint_is_consistent(hint, crs_info):
                    continue
                anomalies.append(
                    Anomaly.create(
                        category="OBJECT_CRS_HINT_CONFLICT",
                        severity="WARNING",
                        source_database=source_database,
                        source_class=class_name,
                        stable_subject_id=_normal_uuid(document.get("_id")) or str(document.get("_id") or ""),
                        source_document_id=_source_document_id(document),
                        source_field="crsName",
                        message="Le crsName objet contredit le CRS global sans le remplacer.",
                        details={"authority": crs_info.source},
                        suggested_action="Vérifier le contexte de saisie historique de cet objet.",
                        correction_location="COUCHDB",
                        detected_value=hint,
                        expected_value=f"indice compatible avec EPSG:{crs_info.source_srid}",
                    )
                )

    for row in coverage_rows:
        class_name = str(row["class"])
        status = str(row["status"])
        known = bool(row.get("known"))
        if status == "NON_MIGREE":
            category = "DEFERRED_FEATURE" if known else "UNKNOWN_CLASS"
            anomalies.append(
                Anomaly.create(
                    category=category,
                    severity="WARNING" if known else "ERROR",
                    source_database=source_database,
                    source_class=class_name,
                    message=(
                        f"Classe {class_name} connue mais différée."
                        if known
                        else f"Classe {class_name} inconnue du migrateur."
                    ),
                    details={"document_count": row["total"], "coverage_comment": row.get("comment")},
                    suggested_action="Analyser cette classe avant d'étendre le migrateur.",
                    correction_location="NOT_APPLICABLE" if known else "MIGRATOR",
                    detected_value=row["total"],
                    expected_value=0,
                )
            )
        elif status == "PARTIELLE" and not class_name.startswith("Ref"):
            anomalies.append(
                Anomaly.create(
                    category="PARTIALLY_MIGRATED_CLASS",
                    severity="INFO",
                    source_database=source_database,
                    source_class=class_name,
                    message=f"La classe {class_name} est partiellement migrée.",
                    details={"document_count": row["total"], "coverage_comment": row.get("comment")},
                    suggested_action="Consulter le bilan des champs avant de compléter ce domaine.",
                    correction_location="NOT_APPLICABLE",
                )
            )

        actionable_fields = [
            field
            for field in row.get("unanalysed", ())
            if not field.startswith("_")
            and field not in NON_ACTIONABLE_FIELDS
            and not field.startswith(("distanceDebut", "distanceFin"))
        ]
        if (
            actionable_fields
            and status in {"MIGREE", "PARTIELLE"}
            and not class_name.startswith("Ref")
        ):
            anomalies.append(
                Anomaly.create(
                    category="UNMIGRATED_FIELD",
                    severity="WARNING",
                    source_database=source_database,
                    source_class=class_name,
                    source_field="*",
                    message=f"{len(actionable_fields)} champ(s) métier restent non analysés pour {class_name}.",
                    details={"fields": sorted(actionable_fields)},
                    suggested_action="Qualifier ces champs puis les consommer ou les documenter explicitement.",
                    correction_location="MIGRATOR",
                    detected_value=sorted(actionable_fields),
                )
            )

    index = _document_index(documents)
    ids_by_class: dict[str, set[str]] = {}
    for class_name, source_id in index:
        ids_by_class.setdefault(class_name, set()).add(source_id)
    for source_class, specs in REFERENCE_SPECS.items():
        for document in grouped.get(source_class, ()):
            source_id = _normal_uuid(document.get("_id"))
            for field, target_class, required in specs:
                raw_value = document.get(field)
                if raw_value in (None, ""):
                    if required:
                        anomalies.append(
                            Anomaly.create(
                                category="MISSING_REQUIRED_REFERENCE",
                                severity="BLOCKING",
                                source_database=source_database,
                                source_class=source_class,
                                stable_subject_id=source_id,
                                source_document_id=_source_document_id(document),
                                source_field=field,
                                message=f"La référence obligatoire {field} est absente.",
                                suggested_action="Renseigner le parent explicite dans CouchDB.",
                                correction_location="COUCHDB",
                                expected_value=f"UUID {target_class}",
                            )
                        )
                    continue
                normalized = _normal_uuid(raw_value)
                if normalized not in ids_by_class.get(target_class, set()):
                    anomalies.append(
                        Anomaly.create(
                            category="BROKEN_REFERENCE",
                            severity="BLOCKING",
                            source_database=source_database,
                            source_class=source_class,
                            stable_subject_id=source_id,
                            source_document_id=_source_document_id(document),
                            source_field=field,
                            message=f"{field} référence un {target_class} absent.",
                            details={"target_source_class": target_class},
                            suggested_action="Corriger la référence ou restaurer l'objet parent dans CouchDB.",
                            correction_location="COUCHDB",
                            detected_value=normalized,
                            expected_value=f"UUID existant de {target_class}",
                        )
                    )

    for document in grouped.get("Desordre", ()):
        if document.get("categorieDesordreId") not in (None, "") and document.get("typeDesordreId") in (None, ""):
            source_id = _normal_uuid(document.get("_id"))
            anomalies.append(
                Anomaly.create(
                    category="MISSING_REFERENCE_VALUE",
                    severity="WARNING",
                    source_database=source_database,
                    source_class="Desordre",
                    stable_subject_id=source_id,
                    source_document_id=_source_document_id(document),
                    source_field="typeDesordreId",
                    target_table="desordres",
                    target_id=source_id,
                    target_field="type_desordre_id",
                    message="Une catégorie est renseignée sans type de désordre.",
                    details={"categorieDesordreId": document.get("categorieDesordreId")},
                    suggested_action="Renseigner le type dans CouchDB ou accepter explicitement la valeur NULL.",
                    correction_location="EITHER",
                    detected_value=None,
                    expected_value="RefTypeDesordre compatible avec la catégorie",
                )
            )

    prepared_geometry_ids: set[str] = set()
    if prepared_core is not None:
        for row in prepared_core.vegetation.vegetation:
            prepared_geometry_ids.add(str(row.id))
            key = (row.source_class, str(row.id))
            document = index.get(key, {})
            if row.geometry_method == MANUAL_REVIEW:
                anomalies.append(
                    Anomaly.create(
                        category="MANUAL_REVIEW",
                        severity="WARNING",
                        source_database=source_database,
                        source_class=row.source_class,
                        stable_subject_id=str(row.id),
                        source_document_id=_source_document_id(document),
                        source_field="geometry",
                        target_table="vegetation",
                        target_id=str(row.id),
                        target_field="geometry",
                        message="La géométrie nécessite une revue manuelle et reste NULL en cible.",
                        details=_geometry_details(document),
                        suggested_action="Comparer les représentations source et valider une géométrie métier.",
                        correction_location="MANUAL_REVIEW",
                        detected_value=_geometry_details(document),
                        expected_value="Point, LineString ou Polygon non ambigu",
                    )
                )
            elif row.geometry_method == KEEP_NULL:
                anomalies.append(
                    Anomaly.create(
                        category="MISSING_GEOMETRY",
                        severity="WARNING",
                        source_database=source_database,
                        source_class=row.source_class,
                        stable_subject_id=str(row.id),
                        source_document_id=_source_document_id(document),
                        source_field="geometry",
                        target_table="vegetation",
                        target_id=str(row.id),
                        target_field="geometry",
                        message="Aucune source géométrique fiable n'est disponible.",
                        details=_geometry_details(document),
                        suggested_action="Saisir une géométrie validée dans la source ou formaliser un override.",
                        correction_location="EITHER",
                        detected_value=None,
                        expected_value="Point, LineString ou Polygon",
                    )
                )

    overrides = get_source_overrides(source_database)
    override_geometry_ids = {
        _normal_uuid(raw_id)
        for raw_id in overrides.vegetation_geometry_source_by_id
    }
    # Le parseur léger est réservé aux géométries de végétation pour lesquelles
    # ses limites ont été auditées. Une ancienne version l'appliquait aussi aux
    # grands polygones d'aménagement : elle a produit un faux positif
    # INVALID_GEOMETRY pour bb404c68-6144-992f-f4ec-d939ea005d75, pourtant
    # accepté comme Polygon valide par la validation PostGIS de la migration.
    # Cette anomalie historique reste donc inactive et OPEN dans le registre.
    for source_class in (
        "ArbreVegetation",
        "PeuplementVegetation",
        "InvasiveVegetation",
    ):
        for document in grouped.get(source_class, ()):
            source_id = _normal_uuid(document.get("_id"))
            if source_id in prepared_geometry_ids or source_id in override_geometry_ids:
                continue
            raw_geometry = document.get("geometry")
            geometry = inspect_wkt(raw_geometry)
            if raw_geometry not in (None, "") and (
                geometry is None or not geometry.valid
            ):
                anomalies.append(
                    Anomaly.create(
                        category="INVALID_GEOMETRY",
                        severity="WARNING",
                        source_database=source_database,
                        source_class=source_class,
                        stable_subject_id=source_id,
                        source_document_id=_source_document_id(document),
                        source_field="geometry",
                        message="La géométrie source est invalide et ne doit pas être corrigée silencieusement.",
                        details=_geometry_details(document),
                        suggested_action="Corriger la géométrie dans CouchDB ou formaliser une décision de migration.",
                        correction_location="COUCHDB",
                        detected_value=_geometry_details(document),
                        expected_value="géométrie valide compatible avec le type métier",
                    )
                )
    for raw_id, target_type in overrides.amenagement_type_by_id.items():
        source_id = _normal_uuid(raw_id)
        if ("AmenagementHydraulique", source_id or "") not in index:
            continue
        anomalies.append(
            Anomaly.create(
                category="SOURCE_OVERRIDE",
                severity="INFO",
                source_database=source_database,
                source_class="AmenagementHydraulique",
                stable_subject_id=source_id,
                source_document_id=_source_document_id(
                    index[("AmenagementHydraulique", source_id or "")]
                ),
                source_field="type_id",
                target_table="amenagements_hydrauliques",
                target_id=source_id,
                target_field="type_id",
                message=f"Le type cible {target_type} provient d'un override spécifique à la source.",
                suggested_action="Valider ce classement lors du portage vers une autre base.",
                correction_location="MIGRATOR",
                detected_value=None,
                expected_value=target_type,
            )
        )
    for raw_id, selected_field in overrides.vegetation_geometry_source_by_id.items():
        source_id = _normal_uuid(raw_id)
        matches = [
            (source_class, index[(source_class, source_id or "")])
            for source_class in (
                "ArbreVegetation",
                "PeuplementVegetation",
                "InvasiveVegetation",
            )
            if (source_class, source_id or "") in index
        ]
        if not matches:
            continue
        if len(matches) != 1:
            raise ValueError(
                f"Override géométrique {source_id}: UUID présent dans plusieurs classes"
            )
        source_class, document = matches[0]
        anomalies.append(
            Anomaly.create(
                category="SOURCE_OVERRIDE",
                severity="WARNING",
                source_database=source_database,
                source_class=source_class,
                stable_subject_id=source_id,
                source_document_id=_source_document_id(document),
                source_field="geometry",
                target_table="vegetation",
                target_id=source_id,
                target_field="geometry",
                message=f"La géométrie cible utilise {selected_field} via un override spécifique.",
                details=_geometry_details(document),
                suggested_action="Conserver cet override documenté ou corriger la géométrie principale dans CouchDB.",
                correction_location="MIGRATOR",
                detected_value=_geometry_details(document),
                expected_value=f"géométrie issue de {selected_field}",
            )
        )

    prepared_photo_ids = (
        {str(row.id) for row in getattr(prepared_core, "photos", ())}
        if prepared_core is not None
        else None
    )
    for class_name, class_documents in grouped.items():
        coverage = coverage_by_class.get(class_name, {})
        parent_migrated = coverage.get("status") in {"MIGREE", "PARTIELLE"}
        parent_deferred = (
            coverage.get("status") == "NON_MIGREE"
            and bool(coverage.get("known"))
        )
        for document in class_documents:
            for photo in document.get("photos") or ():
                if not isinstance(photo, Mapping):
                    continue
                photo_id = _normal_uuid(photo.get("id") or photo.get("_id"))
                photo_source_object_id = _source_object_id(
                    photo.get("id") or photo.get("_id")
                )
                owner_document_id = _source_document_id(document)
                media_expected_but_missing = (
                    parent_migrated
                    and prepared_photo_ids is not None
                    and photo_id is not None
                    and photo_id not in prepared_photo_ids
                )
                if media_expected_but_missing:
                    anomalies.append(
                        Anomaly.create(
                            category="UNMIGRATED_MEDIA",
                            severity="ERROR",
                            source_database=source_database,
                            source_class=class_name,
                            stable_subject_id=photo_id,
                            source_document_id=_source_document_id(document),
                            source_object_id=photo_source_object_id,
                            source_field="photos",
                            message=(
                                "La photo d'un objet pris en charge est absente "
                                "de la migration préparée."
                            ),
                            details={"owner_document_id": owner_document_id},
                            suggested_action=(
                                "Corriger la prise en charge du média dans le migrateur."
                            ),
                            correction_location="MIGRATOR",
                            detected_value=photo.get("chemin"),
                            expected_value="photo rattachée à une observation cible",
                        )
                    )
                elif parent_migrated and photo.get("date") in (None, ""):
                    anomalies.append(
                        Anomaly.create(
                            category="PHOTO_WITHOUT_DATE",
                            severity="WARNING",
                            source_database=source_database,
                            source_class=class_name,
                            stable_subject_id=photo_id,
                            source_document_id=_source_document_id(document),
                            source_object_id=photo_source_object_id,
                            source_field="photos.date",
                            target_table="photos",
                            target_id=photo_id,
                            target_field="date",
                            message="La photo directe est migrée avec une date NULL.",
                            details={"owner_document_id": owner_document_id},
                            suggested_action="Renseigner la date dans CouchDB si elle est connue.",
                            correction_location="COUCHDB",
                            detected_value=None,
                            expected_value="date ISO ou NULL accepté explicitement",
                        )
                    )
                elif not parent_migrated:
                    # La catégorie participe à anomaly_id : une ancienne entrée
                    # UNMIGRATED_MEDIA reclassée reste donc dans l'historique
                    # inactive, tandis que DEFERRED_MEDIA reçoit son ID stable.
                    category = (
                        "DEFERRED_MEDIA" if parent_deferred else "UNMIGRATED_MEDIA"
                    )
                    anomalies.append(
                        Anomaly.create(
                            category=category,
                            severity="WARNING" if parent_deferred else "ERROR",
                            source_database=source_database,
                            source_class=class_name,
                            stable_subject_id=photo_id,
                            source_document_id=_source_document_id(document),
                            source_object_id=photo_source_object_id,
                            source_field="photos",
                            message=(
                                "Le média est différé car son objet parent est "
                                "volontairement différé par le migrateur."
                                if parent_deferred
                                else "La photo n'est pas migrée car son objet parent "
                                "n'est pas migré."
                            ),
                            details={"owner_document_id": owner_document_id},
                            suggested_action=(
                                "Migrer la famille parente ; le média sera reconnecté "
                                "lors de cette migration."
                                if parent_deferred
                                else "Migrer ou résoudre le parent avant de reconnecter "
                                "ce média."
                            ),
                            correction_location="MIGRATOR",
                            detected_value=photo.get("chemin"),
                            expected_value="photo rattachée à une observation cible",
                        )
                    )

    photo_occurrences, photos_without_id = _embedded_photo_occurrences(grouped)
    for occurrence in photos_without_id:
        owner_document_id = occurrence["source_document_id"]
        source_field = occurrence["source_field"]
        anomalies.append(
            Anomaly.create(
                category="UNMIGRATED_MEDIA",
                severity="BLOCKING",
                source_database=source_database,
                source_class=occurrence["source_class"],
                stable_subject_id=_normal_uuid(owner_document_id),
                source_document_id=occurrence["source_document_id"],
                source_field=source_field,
                message="La photo embarquée ne possède aucun identifiant source.",
                details={"owner_document_id": owner_document_id},
                suggested_action="Attribuer un UUID stable à la photo dans CouchDB.",
                correction_location="COUCHDB",
                detected_value=None,
                expected_value="UUID photo unique",
            )
        )
    for photo_id, occurrences in photo_occurrences.items():
        if len(occurrences) < 2:
            continue
        source_document_ids = {
            occurrence["source_document_id"]
            for occurrence in occurrences
            if occurrence["source_document_id"] is not None
        }
        source_object_ids = {
            occurrence["source_object_id"]
            for occurrence in occurrences
            if occurrence["source_object_id"] is not None
        }
        anomalies.append(
            Anomaly.create(
                category="UNMIGRATED_MEDIA",
                severity="BLOCKING",
                source_database=source_database,
                source_class="Photo",
                stable_subject_id=photo_id,
                source_document_id=(
                    next(iter(source_document_ids))
                    if len(source_document_ids) == 1
                    else None
                ),
                source_object_id=(
                    next(iter(source_object_ids))
                    if len(source_object_ids) == 1
                    else None
                ),
                source_field="id",
                message="Le même UUID photo apparaît plusieurs fois dans la source.",
                details={"occurrences": occurrences, "occurrence_count": len(occurrences)},
                suggested_action="Attribuer un UUID unique à chaque photo dans CouchDB.",
                correction_location="COUCHDB",
                detected_value=photo_id,
                expected_value="UUID photo unique",
            )
        )

    unique = {anomaly.anomaly_id: anomaly for anomaly in anomalies}
    if len(unique) != len(anomalies):
        raise ValueError("Deux anomalies collectées partagent la même identité logique")
    return tuple(sorted(unique.values(), key=lambda anomaly: anomaly.anomaly_id))


def load_anomalies(path: Path) -> tuple[Anomaly, ...]:
    if not path.exists():
        return ()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"Le registre {path} doit contenir une liste JSON")
    return tuple(Anomaly.from_dict(item) for item in raw)


def merge_previous_status(
    current: Sequence[Anomaly],
    previous: Sequence[Anomaly],
    *,
    detected_at: str | None = None,
) -> tuple[Anomaly, ...]:
    now = detected_at or utc_now()
    previous_by_id = {anomaly.anomaly_id: anomaly for anomaly in previous}
    current_ids = {anomaly.anomaly_id for anomaly in current}
    merged: list[Anomaly] = []
    for anomaly in current:
        old = previous_by_id.get(anomaly.anomaly_id)
        merged.append(
            replace(
                anomaly,
                status=old.status if old else "OPEN",
                resolution_comment=old.resolution_comment if old else None,
                first_detected_at=(old.first_detected_at if old else None) or now,
                last_detected_at=now,
                resolved_detected_at=old.resolved_detected_at if old else None,
                active=True,
            )
        )
    for anomaly in previous:
        if anomaly.anomaly_id not in current_ids:
            merged.append(
                replace(
                    anomaly,
                    active=False,
                    resolved_detected_at=anomaly.resolved_detected_at or now,
                )
            )
    return tuple(sorted(merged, key=lambda anomaly: anomaly.anomaly_id))


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, bool)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def write_anomalies_json(path: Path, anomalies: Sequence[Anomaly]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            [anomaly.to_dict() for anomaly in anomalies],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def write_anomalies_csv(path: Path, anomalies: Sequence[Anomaly]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for anomaly in anomalies:
            values = anomaly.to_dict()
            values["actionable"] = "TRUE" if is_actionable(anomaly) else "FALSE"
            values["family"] = FAMILY_BY_CATEGORY[anomaly.category]
            writer.writerow(
                {key: _csv_value(values.get(key)) for key in CSV_FIELDS}
            )
    temporary.replace(path)


def update_anomaly_register(
    current: Sequence[Anomaly],
    *,
    json_path: Path,
    csv_path: Path,
    detected_at: str | None = None,
) -> AnomalyRegisterResult:
    previous = load_anomalies(json_path)
    merged = merge_previous_status(current, previous, detected_at=detected_at)
    write_anomalies_json(json_path, merged)
    write_anomalies_csv(csv_path, merged)
    return AnomalyRegisterResult(merged, json_path, csv_path)


def resolve_anomaly(
    anomaly_id: str,
    *,
    status: str,
    comment: str | None,
    json_path: Path,
    csv_path: Path,
) -> Anomaly:
    if status not in RESOLUTION_STATUSES:
        raise ValueError(f"Statut de résolution interdit : {status}")
    anomalies = list(load_anomalies(json_path))
    for index, anomaly in enumerate(anomalies):
        if anomaly.anomaly_id == anomaly_id:
            updated = replace(
                anomaly,
                status=status,
                resolution_comment=comment,
                resolved_detected_at=utc_now(),
            )
            anomalies[index] = updated
            write_anomalies_json(json_path, anomalies)
            write_anomalies_csv(csv_path, anomalies)
            return updated
    raise KeyError(f"Anomalie inconnue : {anomaly_id}")
