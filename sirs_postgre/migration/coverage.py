"""Diagnostic reproductible de la couverture réelle d'une base SIRS/CouchDB."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from sirs_postgre.source import CouchDBClient

from .amenagements import AMENAGEMENT_SOURCE_CLASSES
from .core import CORE_SOURCE_CLASSES, prepare_core_migration
from .ouvrages import OUVRAGE_SOURCE_CLASSES
from .vegetation import VEGETATION_SOURCE_CLASSES, prepare_vegetation_migration


REPORT_PATH = Path(__file__).resolve().parents[2] / "audits" / "bilan.md"
STATUSES = (
    "MIGREE",
    "PARTIELLE",
    "NON_MIGREE",
    "TECHNIQUE_IGNORE",
    "REFERENTIEL_IGNORE",
)

COMMON_IGNORED_FIELDS = frozenset(
    {
        "@class",
        "_rev",
        "author",
        "lastUpdateAuthor",
        "dateMaj",
        "editedGeoCoordinate",
        "geometryMode",
        "latitudeMin",
        "latitudeMax",
        "longitudeMin",
        "longitudeMax",
        "borneDebutId",
        "borneFinId",
        "borne_debut_aval",
        "borne_debut_distance",
        "borne_fin_aval",
        "borne_fin_distance",
        "prDebut",
        "prFin",
        "systemeRepId",
    }
)


@dataclass(frozen=True)
class CoverageRule:
    destination: str | None
    status: str
    consumed_fields: frozenset[str]
    ignored_fields: frozenset[str] = COMMON_IGNORED_FIELDS
    comment: str = ""


@dataclass(frozen=True)
class CoverageResult:
    path: Path
    total_documents: int
    total_classes: int
    status_class_counts: Mapping[str, int]
    migrated_business_objects: int
    non_migrated_documents: int
    non_migrated_business_objects: int
    total_field_pairs: int
    used_field_pairs: int
    ignored_field_pairs: int
    unanalysed_field_pairs: int
    direct_photos_unmigrated: int


def _fields(*names: str) -> frozenset[str]:
    return frozenset(names)


BASE_FIELDS = _fields("_id", "valid")
MEDIA_FIELDS = _fields("observations", "photos")

COVERAGE_REGISTRY: dict[str, CoverageRule] = {
    "RefCategorieDesordre": CoverageRule("ref_categories_desordre", "MIGREE", BASE_FIELDS | _fields("libelle")),
    "RefTypeDesordre": CoverageRule("ref_types_desordre", "MIGREE", BASE_FIELDS | _fields("categorieId", "libelle")),
    "RefUrgence": CoverageRule("ref_urgences", "MIGREE", BASE_FIELDS | _fields("libelle")),
    "SystemeEndiguement": CoverageRule("systemes", "MIGREE", BASE_FIELDS | _fields("libelle")),
    "Digue": CoverageRule("digues", "MIGREE", BASE_FIELDS | _fields("systemeEndiguementId", "libelle")),
    "TronconDigue": CoverageRule("troncons, observations, photos", "MIGREE", BASE_FIELDS | MEDIA_FIELDS | _fields("digueId", "libelle", "geometry")),
    "Desordre": CoverageRule(
        "desordres, link_desordres_troncons, observations, photos",
        "PARTIELLE",
        BASE_FIELDS | MEDIA_FIELDS | _fields(
            "typeDesordreId", "categorieDesordreId", "designation", "commentaire",
            "date_debut", "date_fin", "geometry", "positionDebut", "positionFin", "linearId"
        ),
        comment="Objet, rattachement, observations et photos migrés ; prestations et champs spécialisés différés.",
    ),
    "AmenagementHydraulique": CoverageRule(
        "amenagements_hydrauliques, link_amenagements_troncons, observations, photos",
        "PARTIELLE",
        BASE_FIELDS | MEDIA_FIELDS | _fields("designation", "date_debut", "geometry", "tronconIds", "typeAmenagementHydrauliqueId", "typeId"),
        comment="Objet et liens explicites migrés ; prestations différées.",
    ),
    "PrestationAmenagementHydraulique": CoverageRule(None, "NON_MIGREE", frozenset(), comment="Différée jusqu'au modèle général des prestations."),
    "TraitAmenagementHydraulique": CoverageRule(None, "TECHNIQUE_IGNORE", frozenset(), comment="Reliquat sans contenu métier utile dans le corpus courant."),
    "DesordreDependance": CoverageRule(None, "NON_MIGREE", frozenset(), comment="Dépendance différée."),
    "PlanVegetation": CoverageRule("plans_gestion_vegetation", "PARTIELLE", BASE_FIELDS | _fields("libelle", "anneeDebut", "anneeFin"), comment="Plan migré ; planifications/traitements sans contenu opérationnel différés."),
    "ParcelleVegetation": CoverageRule("parcelles_gestion_vegetation, link_parcelles_gestion_troncons", "PARTIELLE", BASE_FIELDS | _fields("planId", "designation", "date_debut", "geometry", "linearId"), comment="Parcelle et lien explicite migrés ; champs historiques documentés séparément."),
}

_OUVRAGE_DESTINATIONS = "famille Ouvrages cible, observations, photos"
for _class_name in OUVRAGE_SOURCE_CLASSES:
    if _class_name == "CheminAccesDependance":
        COVERAGE_REGISTRY[_class_name] = CoverageRule(
            None,
            "NON_MIGREE",
            frozenset(),
            comment="Différé : parent aménagement non explicitement stocké.",
        )
    else:
        COVERAGE_REGISTRY[_class_name] = CoverageRule(
            _OUVRAGE_DESTINATIONS,
            "PARTIELLE",
            BASE_FIELDS | MEDIA_FIELDS | _fields(
                "designation", "commentaire", "date_debut", "geometry", "linearId",
                "typeOuvrageParticulierId", "typeOuvrageHydroAssocieId",
                "typeOuvrageFranchissementId", "typeVoieDigueId",
                "typeReseauTelecomEnergieId", "amenagementHydrauliqueId", "typeId"
            ),
            comment="Objet et médias migrés ; champs spécialisés et prestations différés.",
        )

for _class_name in ("ArbreVegetation", "PeuplementVegetation", "InvasiveVegetation"):
    COVERAGE_REGISTRY[_class_name] = CoverageRule(
        "vegetation, observations, photos",
        "PARTIELLE",
        BASE_FIELDS | MEDIA_FIELDS | _fields(
            "designation", "commentaire", "date_debut", "geometry", "explicitGeometry",
            "positionDebut", "positionFin", "parcelleId", "typeVegetationId",
            "etatSanitaireId", "hauteurId", "diametreId", "classeHauteurId", "classeDiametreId"
        ),
        comment="Objet migré ; traitements/planifications et essences différés.",
    )

# Les référentiels de type d'aménagement sont lus pour un mapping explicite mais
# le nouveau catalogue PostgreSQL reste indépendant des anciens identifiants.
COVERAGE_REGISTRY["RefTypeAmenagementHydraulique"] = CoverageRule(
    "ref_types_amenagement_hydraulique (mapping)",
    "PARTIELLE",
    BASE_FIELDS | _fields("libelle", "abrege"),
    comment="Ancien identifiant utilisé seulement par le mapping.",
)


def short_class(document: Mapping[str, Any]) -> str:
    value = document.get("@class")
    if not isinstance(value, str) or not value:
        return "<SANS_@class>"
    return value.rsplit(".", 1)[-1]


def rule_for(class_name: str) -> CoverageRule:
    explicit = COVERAGE_REGISTRY.get(class_name)
    if explicit is not None:
        return explicit
    if class_name == "<SANS_@class>":
        return CoverageRule(None, "TECHNIQUE_IGNORE", frozenset(), comment="Document CouchDB sans classe métier.")
    if class_name.startswith("Ref"):
        return CoverageRule(None, "REFERENTIEL_IGNORE", frozenset(), comment="Référentiel découvert mais non pris en charge dans ce lot.")
    return CoverageRule(None, "NON_MIGREE", frozenset(), comment="Classe inconnue du registre de couverture.")


def _escape(value: Any) -> str:
    return str(value if value not in (None, "") else "—").replace("|", "\\|").replace("\n", " ")


def diagnose_documents(
    documents: Sequence[Mapping[str, Any]],
    *,
    output_path: Path = REPORT_PATH,
    source_database: str | None = None,
) -> CoverageResult:
    grouped: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for document in documents:
        grouped[short_class(document)].append(document)

    rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    total_fields = used_fields = ignored_fields = unanalysed_fields = 0
    direct_photos_unmigrated = 0
    direct_photos_unmigrated_by_class: Counter[str] = Counter()
    field_sections: list[str] = []
    covered_documents = migrated_objects = 0
    non_migrated_documents = non_migrated_business = 0

    for class_name in sorted(grouped):
        class_documents = grouped[class_name]
        rule = rule_for(class_name)
        status_counts[rule.status] += 1
        observed = set().union(*(document.keys() for document in class_documents))
        used = observed & set(rule.consumed_fields)
        ignored = observed & set(rule.ignored_fields)
        unanalysed = observed - used - ignored
        total_fields += len(observed)
        used_fields += len(used)
        ignored_fields += len(ignored)
        unanalysed_fields += len(unanalysed)
        if rule.status in {"MIGREE", "PARTIELLE"} and rule.destination:
            covered_documents += len(class_documents)
            if not class_name.startswith("Ref"):
                migrated_objects += len(class_documents)
            migrated_count = len(class_documents)
        else:
            migrated_count = 0
        if rule.status in {"NON_MIGREE", "TECHNIQUE_IGNORE", "REFERENTIEL_IGNORE"}:
            non_migrated_documents += len(class_documents)
        if rule.status == "NON_MIGREE":
            non_migrated_business += len(class_documents)
            remaining_direct_photos = sum(
                len(document.get("photos") or [])
                for document in class_documents
                if isinstance(document.get("photos") or [], list)
            )
            direct_photos_unmigrated += remaining_direct_photos
            if remaining_direct_photos:
                direct_photos_unmigrated_by_class[class_name] += remaining_direct_photos
        rows.append(
            {
                "class": class_name,
                "total": len(class_documents),
                "status": rule.status,
                "destination": rule.destination,
                "comment": rule.comment,
                "migrated": migrated_count,
                "remaining": len(class_documents) - migrated_count,
            }
        )
        if rule.status in {"MIGREE", "PARTIELLE"}:
            field_sections.extend(
                [
                    f"### {class_name}",
                    "",
                    f"- Champs observés : {', '.join(f'`{x}`' for x in sorted(observed)) or 'aucun'}",
                    f"- Champs utilisés : {', '.join(f'`{x}`' for x in sorted(used)) or 'aucun'}",
                    f"- Champs ignorés et documentés : {', '.join(f'`{x}`' for x in sorted(ignored)) or 'aucun'}",
                    f"- Champs non analysés/non migrés : {', '.join(f'`{x}`' for x in sorted(unanalysed)) or 'aucun'}",
                    "",
                ]
            )

    geometry_notes: list[str] = []
    vegetation_documents = {
        name: grouped.get(name, []) for name in VEGETATION_SOURCE_CLASSES
    }
    if any(vegetation_documents.values()):
        try:
            troncon_ids = {
                UUID(str(document.get("_id")))
                for document in grouped.get("TronconDigue", [])
            }
            prepared_vegetation = prepare_vegetation_migration(
                vegetation_documents,
                troncon_ids=troncon_ids,
                source_database=source_database,
            )
            geometry_notes.append(
                f"- Végétation MANUAL_REVIEW : {len(prepared_vegetation.manual_review_ids)}."
            )
            geometry_notes.append(
                f"- Végétation geometry NULL cible : {prepared_vegetation.geometry_counts['null']}."
            )
        except Exception as exc:
            geometry_notes.append(f"- Diagnostic géométrique végétation impossible : {_escape(exc)}.")
    geometry_notes.append(
        f"- Photos directes restant sur des classes non migrées : {direct_photos_unmigrated}."
    )
    for class_name, count in sorted(direct_photos_unmigrated_by_class.items()):
        geometry_notes.append(f"  - `{class_name}` : {count}.")

    migration_warnings: list[str] = []
    try:
        supported_documents = {
            class_name: grouped.get(class_name, [])
            for class_name in CORE_SOURCE_CLASSES
        }
        prepared_core = prepare_core_migration(
            supported_documents,
            source_database=source_database,
        )
        migration_warnings.extend(prepared_core.warnings)
    except Exception as exc:
        migration_warnings.append(
            f"Préparation complète impossible : {_escape(exc)}"
        )

    lines = [
        "# Bilan généré de couverture SIRS → PostgreSQL",
        "",
        "> Ce document est généré depuis les JSON réellement présents dans CouchDB. "
        "Il ne décrit pas un modèle Java théorique.",
        "",
        "## A. Synthèse",
        "",
        f"- Documents CouchDB : {len(documents)}",
        f"- Classes CouchDB distinctes : {len(grouped)}",
        f"- Classes MIGREE : {status_counts['MIGREE']}",
        f"- Classes PARTIELLE : {status_counts['PARTIELLE']}",
        f"- Classes NON_MIGREE : {status_counts['NON_MIGREE']}",
        f"- Classes TECHNIQUE_IGNORE : {status_counts['TECHNIQUE_IGNORE']}",
        f"- Classes REFERENTIEL_IGNORE : {status_counts['REFERENTIEL_IGNORE']}",
        f"- Documents pris en charge (métier et référentiels) : {covered_documents}",
        f"- Objets métier migrés : {migrated_objects}",
        f"- Documents non migrés (y compris techniques/référentiels ignorés) : {non_migrated_documents}",
        f"- Objets/documents de classes métier NON_MIGREE : {non_migrated_business}",
        "",
        "## B. Classes",
        "",
        "| Classe source | Documents | Statut | Destination PostgreSQL | Commentaire |",
        "|---|---:|---|---|---|",
    ]
    lines.extend(
        f"| {_escape(row['class'])} | {row['total']} | {row['status']} | {_escape(row['destination'])} | {_escape(row['comment'])} |"
        for row in rows
    )
    lines.extend(
        [
            "",
            "## C. Objets non migrés",
            "",
            "| Classe | Total | Migrés | Non migrés | Raison |",
            "|---|---:|---:|---:|---|",
        ]
    )
    lines.extend(
        f"| {_escape(row['class'])} | {row['total']} | {row['migrated']} | {row['remaining']} | {_escape(row['comment'])} |"
        for row in rows
        if row["status"] in {"PARTIELLE", "NON_MIGREE"}
    )
    lines.extend(
        [
            "",
            "## D. Champs des classes prises en charge",
            "",
            *field_sections,
            "### Totaux de couverture des champs",
            "",
            f"- Couples classe/champ source distincts observés : {total_fields}",
            f"- Couples utilisés : {used_fields}",
            f"- Couples volontairement ignorés/documentés : {ignored_fields}",
            f"- Couples non analysés/non migrés : {unanalysed_fields}",
            "",
            "## E. Relations et sous-structures non migrées",
            "",
            "- Prestations et `GlobalPrestation` : différées jusqu'au modèle général des prestations.",
            "- `PrestationAmenagementHydraulique` : différée.",
            "- `CheminAccesDependance` sans parent explicite : différé.",
            "- `DesordreDependance` : différé.",
            "- Traitements et planifications végétation : différés.",
            "- Référentiels à zéro usage ou non exploités : classés `REFERENTIEL_IGNORE` dans le tableau.",
            "",
            "## F. Géométries et données problématiques",
            "",
            *geometry_notes,
            "",
            "### Warnings reproductibles du préparateur",
            "",
            *(
                [f"- {_escape(warning)}" for warning in migration_warnings]
                if migration_warnings
                else ["- Aucun warning."]
            ),
            "- Toute nouvelle classe ou tout nouveau champ absent du registre apparaît automatiquement comme non couvert.",
            "",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return CoverageResult(
        path=output_path,
        total_documents=len(documents),
        total_classes=len(grouped),
        status_class_counts={status: status_counts[status] for status in STATUSES},
        migrated_business_objects=migrated_objects,
        non_migrated_documents=non_migrated_documents,
        non_migrated_business_objects=non_migrated_business,
        total_field_pairs=total_fields,
        used_field_pairs=used_fields,
        ignored_field_pairs=ignored_fields,
        unanalysed_field_pairs=unanalysed_fields,
        direct_photos_unmigrated=direct_photos_unmigrated,
    )


def generate_coverage_report(
    client: CouchDBClient,
    *,
    output_path: Path = REPORT_PATH,
) -> CoverageResult:
    return diagnose_documents(
        client.all_documents(),
        output_path=output_path,
        source_database=client.config.database,
    )
