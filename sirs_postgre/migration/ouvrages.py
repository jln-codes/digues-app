"""Migration du bloc Ouvrages selon ``audits/mapping_ouvrages.md``."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import re
from typing import Any
from uuid import UUID

from .crs import CRSInfo, geometry_sql


OUVRAGE_SOURCE_CLASSES = {
    "OuvrageParticulier": "fr.sirs.core.model.OuvrageParticulier",
    "OuvrageHydrauliqueAssocie": (
        "fr.sirs.core.model.OuvrageHydrauliqueAssocie"
    ),
    "OuvrageFranchissement": "fr.sirs.core.model.OuvrageFranchissement",
    "EchelleLimnimetrique": "fr.sirs.core.model.EchelleLimnimetrique",
    "StationPompage": "fr.sirs.core.model.StationPompage",
    "Deversoir": "fr.sirs.core.model.Deversoir",
    "OuvertureBatardable": "fr.sirs.core.model.OuvertureBatardable",
    "VoieAcces": "fr.sirs.core.model.VoieAcces",
    "VoieDigue": "fr.sirs.core.model.VoieDigue",
    "ReseauTelecomEnergie": "fr.sirs.core.model.ReseauTelecomEnergie",
    "CheminAccesDependance": "fr.sirs.core.model.CheminAccesDependance",
    "OuvrageAssocieAmenagementHydraulique": (
        "fr.sirs.core.model.OuvrageAssocieAmenagementHydraulique"
    ),
}

IMMEDIATE_SOURCE_COUNTS = {
    "OuvrageParticulier": 45,
    "OuvrageHydrauliqueAssocie": 26,
    "OuvrageFranchissement": 6,
    "EchelleLimnimetrique": 6,
    "StationPompage": 1,
    "Deversoir": 9,
    "OuvertureBatardable": 1,
    "VoieAcces": 10,
    "VoieDigue": 2,
    "ReseauTelecomEnergie": 3,
    "CheminAccesDependance": 8,
}

DEFERRED_SOURCE_COUNTS = {
    "OuvrageAssocieAmenagementHydraulique": 1,
}

EXPECTED_BUSINESS_COUNTS = {
    "ouvrages_hydrauliques": 34,
    "equipements_mesure": 47,
    "cheminements": 28,
    "mobilier": 1,
    "reseaux_techniques": 7,
}


class OuvragesMigrationError(RuntimeError):
    """Une donnée Ouvrages ne respecte pas la matrice validée."""


@dataclass(frozen=True)
class OuvrageTypeReferenceRow:
    id: str
    code: str
    abrege: str
    libelle: str
    valid: bool = True


@dataclass(frozen=True)
class OuvrageRow:
    id: UUID
    type_id: str
    designation: str | None
    commentaire: str | None
    date_debut: date | None
    geometry_wkt: str | None
    geometry_kind: str
    troncon_id: UUID | None
    valid: bool
    source_class: str
    amenagement_hydraulique_id: UUID | None = None


@dataclass(frozen=True)
class CheminementRow:
    id: UUID
    type_cheminement_id: str
    designation: str | None
    libelle: str | None
    commentaire: str | None
    date_debut: date | None
    date_fin: date | None
    largeur: float | None
    usage_source_id: str | None
    statut_source: bool | None
    materiau_source_id: str | None
    revetement_source_id: str | None
    position_source_id: str | None
    cote_source_id: str | None
    securite_source_id: str | None
    orientation_ouvrage_source_id: str | None
    position_haut_source_id: str | None
    position_bas_source_id: str | None
    revetement_haut_source_id: str | None
    revetement_bas_source_id: str | None
    dimension_horizontale: float | None
    dimension_verticale: float | None
    numero_secteur: int | None
    geometry_wkt: str | None
    geometry_kind: str
    valid: bool
    source_class: str


@dataclass(frozen=True)
class LinkCheminementTronconRow:
    cheminement_id: UUID
    troncon_id: UUID


@dataclass(frozen=True)
class LinkCheminementDesordreRow:
    cheminement_id: UUID
    desordre_id: UUID


@dataclass(frozen=True)
class PreparedOuvragesMigration:
    references: Mapping[str, tuple[OuvrageTypeReferenceRow, ...]]
    rows: Mapping[str, tuple[OuvrageRow | CheminementRow, ...]]
    cheminement_troncon_links: tuple[LinkCheminementTronconRow, ...]
    cheminement_desordre_links: tuple[LinkCheminementDesordreRow, ...]
    source_counts: Mapping[str, int]
    deferred_counts: Mapping[str, int]
    enabled: bool = True

    @classmethod
    def empty(cls) -> "PreparedOuvragesMigration":
        return cls(
            references={table: () for table in TARGET_REFERENCES},
            rows={table: () for table in EXPECTED_BUSINESS_COUNTS},
            cheminement_troncon_links=(),
            cheminement_desordre_links=(),
            source_counts={},
            deferred_counts={},
            enabled=False,
        )

    @property
    def migrated_count(self) -> int:
        return sum(len(rows) for rows in self.rows.values())

    @property
    def deferred_count(self) -> int:
        return sum(self.deferred_counts.values())

    @property
    def explained_count(self) -> int:
        return self.migrated_count + self.deferred_count

    @property
    def expected_counts(self) -> dict[str, int]:
        counts = {
            table: len(rows) for table, rows in self.references.items()
        }
        counts.update({table: len(rows) for table, rows in self.rows.items()})
        counts["link_cheminements_troncons"] = len(
            self.cheminement_troncon_links
        )
        counts["link_cheminements_desordres"] = len(
            self.cheminement_desordre_links
        )
        return counts

    @property
    def geometry_counts(self) -> dict[str, dict[str, int]]:
        return {
            table: dict(Counter(row.geometry_kind for row in rows))
            for table, rows in self.rows.items()
        }

    @property
    def invalid_counts(self) -> dict[str, int]:
        return {
            table: sum(not row.valid for row in rows)
            for table, rows in self.rows.items()
        }


TARGET_REFERENCES = {
    "ref_types_ouvrage_hydraulique": (
        OuvrageTypeReferenceRow("VAN", "vanne", "VAN", "Vanne"),
        OuvrageTypeReferenceRow("CLA", "clapet", "CLA", "Clapet"),
        OuvrageTypeReferenceRow("POS", "poste_refoulement", "POS", "Poste de refoulement"),
        OuvrageTypeReferenceRow("STP", "station_pompage", "STP", "Station de pompage"),
        OuvrageTypeReferenceRow("SIH", "siphon", "SIH", "Siphon"),
        OuvrageTypeReferenceRow("EXR", "exutoire", "EXR", "Exutoire"),
        OuvrageTypeReferenceRow("DEV", "deversoir", "DEV", "Déversoir"),
        OuvrageTypeReferenceRow("DVS", "deversoir_securite", "DVS", "Déversoir de sécurité"),
        OuvrageTypeReferenceRow("VBT", "ouverture_batardable", "VBT", "Ouverture batardable"),
        OuvrageTypeReferenceRow("PAF", "porte_a_flot", "PAF", "Porte à flot"),
        OuvrageTypeReferenceRow("BBN", "barbacane", "BBN", "Barbacane"),
        OuvrageTypeReferenceRow("TTB", "tete_buse", "TTB", "Tête de buse"),
        OuvrageTypeReferenceRow("TVI", "tour_vidange", "TVI", "Tour de vidange"),
        OuvrageTypeReferenceRow("FOD", "fosse_decantation", "FOD", "Fosse de décantation"),
        OuvrageTypeReferenceRow("PAS", "passe_poissons", "PAS", "Passe à poissons"),
        OuvrageTypeReferenceRow("AUT", "autre", "AUT", "Autre ouvrage hydraulique"),
        OuvrageTypeReferenceRow("IND", "indefini", "IND", "Ouvrage hydraulique indéfini"),
    ),
    "ref_types_equipement_mesure": (
        OuvrageTypeReferenceRow("PIE", "piezometre", "PIE", "Piézomètre"),
        OuvrageTypeReferenceRow("ECH", "echelle_limnimetrique", "ECH", "Échelle limnimétrique"),
        OuvrageTypeReferenceRow("STA", "station_mesure", "STA", "Station de mesure"),
        OuvrageTypeReferenceRow("RDN", "repere_nivellement", "RDN", "Repère de nivellement"),
        OuvrageTypeReferenceRow("AUT", "autre", "AUT", "Autre équipement de mesure"),
        OuvrageTypeReferenceRow("IND", "indefini", "IND", "Équipement de mesure indéfini"),
    ),
    "ref_types_cheminement": (
        OuvrageTypeReferenceRow("PNT", "pont", "PNT", "Pont"),
        OuvrageTypeReferenceRow("RAM", "rampe", "RAM", "Rampe"),
        OuvrageTypeReferenceRow("TUN", "tunnel", "TUN", "Tunnel"),
        OuvrageTypeReferenceRow("PAS", "passage_gue", "PAS", "Passage à gué"),
        OuvrageTypeReferenceRow("ESC", "escalier_acces", "ESC", "Escalier d'accès"),
        OuvrageTypeReferenceRow("CAL", "cale", "CAL", "Cale"),
        OuvrageTypeReferenceRow("VAC", "voie_acces", "VAC", "Voie d'accès"),
        OuvrageTypeReferenceRow(
            "CAC", "chemin_acces_technique", "CAC", "Chemin d'accès technique"
        ),
        OuvrageTypeReferenceRow("CHE", "voie_sur_digue", "CHE", "Voie sur digue"),
        OuvrageTypeReferenceRow("AUT", "autre", "AUT", "Autre cheminement"),
        OuvrageTypeReferenceRow("IND", "indefini", "IND", "Cheminement indéfini"),
    ),
    "ref_types_mobilier": (
        OuvrageTypeReferenceRow("MRE", "mobilier_recreatif", "MRE", "Mobilier récréatif"),
        OuvrageTypeReferenceRow("PAN", "panneau", "PAN", "Panneau"),
        OuvrageTypeReferenceRow("CLO", "cloture", "CLO", "Clôture"),
        OuvrageTypeReferenceRow("MOU", "monument", "MOU", "Monument"),
        OuvrageTypeReferenceRow("SOB", "socle", "SOB", "Socle"),
        OuvrageTypeReferenceRow("PON", "ponton", "PON", "Ponton"),
        OuvrageTypeReferenceRow("AUT", "autre", "AUT", "Autre mobilier"),
        OuvrageTypeReferenceRow("IND", "indefini", "IND", "Mobilier indéfini"),
    ),
    "ref_types_reseau_technique": (
        OuvrageTypeReferenceRow("REG", "regard_reseau", "REG", "Regard ou bouche à clef"),
        OuvrageTypeReferenceRow("BRE", "borne_reseau_eau", "BRE", "Borne de réseau d'eau"),
        OuvrageTypeReferenceRow("BIN", "borne_incendie", "BIN", "Borne incendie"),
        OuvrageTypeReferenceRow("EFT", "ligne_energie_telecom", "EFT", "Ligne énergie ou télécom"),
        OuvrageTypeReferenceRow("GDF", "reseau_gaz", "GDF", "Réseau de gaz"),
        OuvrageTypeReferenceRow("FIB", "fibre_optique", "FIB", "Fibre optique"),
        OuvrageTypeReferenceRow("HYD", "conduite_hydrocarbure", "HYD", "Conduite d'hydrocarbure"),
        OuvrageTypeReferenceRow("AUT", "autre", "AUT", "Autre réseau technique"),
        OuvrageTypeReferenceRow("IND", "indefini", "IND", "Réseau technique indéfini"),
    ),
}


@dataclass(frozen=True)
class MappingRule:
    table: str
    type_id: str
    geometry_mode: str


OP_RULES = {
    "RefOuvrageParticulier:9": MappingRule("equipements_mesure", "PIE", "point"),
    "RefOuvrageParticulier:5": MappingRule("equipements_mesure", "ECH", "point"),
    "RefOuvrageParticulier:3": MappingRule("cheminements", "ESC", "preserve"),
    "RefOuvrageParticulier:20": MappingRule("mobilier", "MRE", "point"),
    "RefOuvrageParticulier:10": MappingRule("reseaux_techniques", "IND", "point"),
    None: MappingRule("equipements_mesure", "IND", "point"),
}

OHA_RULES = {
    "RefOuvrageHydrauliqueAssocie:1": MappingRule("ouvrages_hydrauliques", "VAN", "degenerate"),
    "RefOuvrageHydrauliqueAssocie:5": MappingRule("ouvrages_hydrauliques", "CLA", "degenerate"),
    "RefOuvrageHydrauliqueAssocie:6": MappingRule("ouvrages_hydrauliques", "POS", "degenerate"),
    "RefOuvrageHydrauliqueAssocie:10": MappingRule("ouvrages_hydrauliques", "SIH", "degenerate"),
    "RefOuvrageHydrauliqueAssocie:11": MappingRule("ouvrages_hydrauliques", "EXR", "degenerate"),
    "RefOuvrageHydrauliqueAssocie:3": MappingRule("reseaux_techniques", "REG", "point"),
    "RefOuvrageHydrauliqueAssocie:99": MappingRule("ouvrages_hydrauliques", "IND", "degenerate"),
}

SOURCE_TYPE_FIELDS = {
    "OuvrageParticulier": "typeOuvrageParticulierId",
    "OuvrageHydrauliqueAssocie": "typeOuvrageHydroAssocieId",
    "OuvrageFranchissement": "typeOuvrageFranchissementId",
    "VoieDigue": "typeVoieDigueId",
    "ReseauTelecomEnergie": "typeReseauTelecomEnergieId",
}

EXPECTED_TYPE_COUNTS = {
    "OuvrageParticulier": Counter({
        "RefOuvrageParticulier:9": 30,
        "RefOuvrageParticulier:5": 9,
        "RefOuvrageParticulier:3": 2,
        "RefOuvrageParticulier:20": 1,
        "RefOuvrageParticulier:10": 1,
        None: 2,
    }),
    "OuvrageHydrauliqueAssocie": Counter({
        "RefOuvrageHydrauliqueAssocie:1": 5,
        "RefOuvrageHydrauliqueAssocie:5": 7,
        "RefOuvrageHydrauliqueAssocie:6": 2,
        "RefOuvrageHydrauliqueAssocie:10": 2,
        "RefOuvrageHydrauliqueAssocie:11": 6,
        "RefOuvrageHydrauliqueAssocie:3": 3,
        "RefOuvrageHydrauliqueAssocie:99": 1,
    }),
    "OuvrageFranchissement": Counter({"RefOuvrageFranchissement:4": 6}),
    "VoieDigue": Counter({"RefVoieDigue:2": 2}),
    "ReseauTelecomEnergie": Counter({"RefReseauTelecomEnergie:1": 3}),
}

IMPLICIT_RULES = {
    "EchelleLimnimetrique": MappingRule("equipements_mesure", "ECH", "point"),
    "StationPompage": MappingRule("ouvrages_hydrauliques", "STP", "preserve"),
    "Deversoir": MappingRule("ouvrages_hydrauliques", "DEV", "preserve"),
    "OuvertureBatardable": MappingRule("ouvrages_hydrauliques", "VBT", "preserve"),
    "VoieAcces": MappingRule("cheminements", "VAC", "preserve"),
    "CheminAccesDependance": MappingRule("cheminements", "CAC", "preserve"),
}

NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
POINT_WKT = re.compile(
    rf"^\s*POINT\s*\(\s*({NUMBER})\s+({NUMBER})\s*\)\s*$", re.IGNORECASE
)
LINESTRING_WKT = re.compile(
    rf"^\s*LINESTRING\s*\(\s*((?:{NUMBER}\s+{NUMBER}\s*,\s*)+{NUMBER}\s+{NUMBER})\s*\)\s*$",
    re.IGNORECASE,
)
GENERIC_WKT = re.compile(
    r"^\s*(POINT|LINESTRING|POLYGON|MULTIPOINT|MULTILINESTRING|MULTIPOLYGON|GEOMETRYCOLLECTION)\s*\(",
    re.IGNORECASE,
)


def _uuid(value: Any, *, context: str) -> UUID:
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise OuvragesMigrationError(f"{context} invalide : {value!r}") from exc


def _optional_text(document: Mapping[str, Any], field: str, context: str) -> str | None:
    value = document.get(field)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise OuvragesMigrationError(f"{context}.{field} doit être du texte")
    return value


def _optional_date(document: Mapping[str, Any], field: str, context: str) -> date | None:
    value = document.get(field)
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise OuvragesMigrationError(f"{context}.{field} doit être une date ISO")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise OuvragesMigrationError(f"{context}.{field} date ISO invalide : {value!r}") from exc


def _required_bool(document: Mapping[str, Any], field: str, context: str) -> bool:
    value = document.get(field)
    if not isinstance(value, bool):
        raise OuvragesMigrationError(f"{context}.{field} doit être un booléen")
    return value


def _optional_bool(
    document: Mapping[str, Any], field: str, context: str
) -> bool | None:
    value = document.get(field)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise OuvragesMigrationError(f"{context}.{field} doit être un booléen")
    return value


def _optional_float(
    document: Mapping[str, Any], field: str, context: str
) -> float | None:
    value = document.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OuvragesMigrationError(f"{context}.{field} doit être numérique")
    return float(value)


def _optional_int(
    document: Mapping[str, Any], field: str, context: str
) -> int | None:
    value = document.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise OuvragesMigrationError(f"{context}.{field} doit être un entier")
    return value


def _optional_source_reference(
    document: Mapping[str, Any], field: str, context: str
) -> str | None:
    value = document.get(field)
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise OuvragesMigrationError(
            f"{context}.{field} doit être un identifiant source texte"
        )
    return value


def _explicit_relation_ids(
    document: Mapping[str, Any], field: str, context: str
) -> tuple[UUID, ...]:
    value = document.get(field)
    if value is None:
        return ()
    if not isinstance(value, list):
        raise OuvragesMigrationError(f"{context}.{field} doit être une liste")
    return tuple(
        _uuid(item, context=f"{context}.{field}") for item in value
    )


def _line_coordinates(wkt: str, *, context: str) -> list[tuple[str, str]]:
    match = LINESTRING_WKT.match(wkt)
    if not match:
        raise OuvragesMigrationError(f"{context}: LINESTRING 2D invalide")
    coordinates: list[tuple[str, str]] = []
    for pair in match.group(1).split(","):
        x, y = pair.split()
        coordinates.append((x, y))
    return coordinates


def _decimal_pair(pair: tuple[str, str], *, context: str) -> tuple[Decimal, Decimal]:
    try:
        return Decimal(pair[0]), Decimal(pair[1])
    except InvalidOperation as exc:
        raise OuvragesMigrationError(f"{context}: coordonnées invalides") from exc


def transform_ouvrage_geometry(
    value: Any, *, mode: str, context: str
) -> tuple[str | None, str]:
    """Applique seulement les transformations explicitement validées."""

    if value in (None, ""):
        return None, "null"
    if not isinstance(value, str):
        raise OuvragesMigrationError(f"{context}: géométrie WKT invalide")
    point = POINT_WKT.match(value)
    line = LINESTRING_WKT.match(value)
    if mode == "point":
        if point:
            return value, "point"
        if not line:
            raise OuvragesMigrationError(
                f"{context}: géométrie incompatible avec une cible Point"
            )
        first = _line_coordinates(value, context=context)[0]
        return f"POINT ({first[0]} {first[1]})", "point"
    if mode == "degenerate" and line:
        coordinates = _line_coordinates(value, context=context)
        normalized = [_decimal_pair(pair, context=context) for pair in coordinates]
        if all(pair == normalized[0] for pair in normalized[1:]):
            first = coordinates[0]
            return f"POINT ({first[0]} {first[1]})", "point"
    if mode not in {"preserve", "degenerate"}:
        raise OuvragesMigrationError(f"{context}: mode géométrique inconnu {mode!r}")
    generic = GENERIC_WKT.match(value)
    if not generic:
        raise OuvragesMigrationError(f"{context}: WKT 2D non pris en charge")
    return value, generic.group(1).lower()


def _mapping_rule(source_class: str, document: Mapping[str, Any]) -> MappingRule:
    if source_class == "OuvrageParticulier":
        source_type = document.get(SOURCE_TYPE_FIELDS[source_class])
        try:
            return OP_RULES[source_type]
        except KeyError as exc:
            raise OuvragesMigrationError(
                f"{source_class} {document.get('_id')}: type non mappé {source_type!r}"
            ) from exc
    if source_class == "OuvrageHydrauliqueAssocie":
        source_type = document.get(SOURCE_TYPE_FIELDS[source_class])
        try:
            return OHA_RULES[source_type]
        except KeyError as exc:
            raise OuvragesMigrationError(
                f"{source_class} {document.get('_id')}: type non mappé {source_type!r}"
            ) from exc
    if source_class == "OuvrageFranchissement":
        if document.get(SOURCE_TYPE_FIELDS[source_class]) != "RefOuvrageFranchissement:4":
            raise OuvragesMigrationError("OuvrageFranchissement: seul le type pont est attendu")
        return MappingRule("cheminements", "PNT", "preserve")
    if source_class == "VoieDigue":
        if document.get(SOURCE_TYPE_FIELDS[source_class]) != "RefVoieDigue:2":
            raise OuvragesMigrationError("VoieDigue: seul le type voie sur digue est attendu")
        return MappingRule("cheminements", "CHE", "preserve")
    if source_class == "ReseauTelecomEnergie":
        if document.get(SOURCE_TYPE_FIELDS[source_class]) != "RefReseauTelecomEnergie:1":
            raise OuvragesMigrationError("ReseauTelecomEnergie: seul le type EFT est attendu")
        return MappingRule("reseaux_techniques", "EFT", "point")
    return IMPLICIT_RULES[source_class]


def _validate_target_references() -> None:
    expected_lengths = {
        "ref_types_ouvrage_hydraulique": 17,
        "ref_types_equipement_mesure": 6,
        "ref_types_cheminement": 11,
        "ref_types_mobilier": 8,
        "ref_types_reseau_technique": 9,
    }
    for table, rows in TARGET_REFERENCES.items():
        if len(rows) != expected_lengths[table]:
            raise OuvragesMigrationError(f"{table}: nombre de lignes de référence invalide")
        if any(row.id != row.abrege for row in rows):
            raise OuvragesMigrationError(f"{table}: id doit être égal à abrege")
        if len({row.id for row in rows}) != len(rows):
            raise OuvragesMigrationError(f"{table}: id/abrege dupliqué")
        if len({row.code for row in rows}) != len(rows):
            raise OuvragesMigrationError(f"{table}: code dupliqué")


def prepare_ouvrages_migration(
    source_documents: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    troncon_ids: set[UUID],
    desordre_ids: set[UUID] | None = None,
    strict_counts: bool = True,
) -> PreparedOuvragesMigration:
    """Prépare les familles Ouvrages et Cheminements, sans accès cible.

    Les liens sont créés exclusivement depuis les identifiants explicitement
    stockés dans les documents source. Aucune opération spatiale n'intervient.
    """

    _validate_target_references()
    source_counts = {
        source_class: len(source_documents.get(source_class, ()))
        for source_class in IMMEDIATE_SOURCE_COUNTS
    }
    deferred_counts = {
        source_class: len(source_documents.get(source_class, ()))
        for source_class in DEFERRED_SOURCE_COUNTS
    }
    if strict_counts:
        if source_counts != IMMEDIATE_SOURCE_COUNTS:
            raise OuvragesMigrationError(
                f"Comptes source Ouvrages inattendus : {source_counts!r}"
            )
        if deferred_counts != DEFERRED_SOURCE_COUNTS:
            raise OuvragesMigrationError(
                f"Comptes différés inattendus : {deferred_counts!r}"
            )
        for source_class, expected in EXPECTED_TYPE_COUNTS.items():
            field = SOURCE_TYPE_FIELDS[source_class]
            actual = Counter(doc.get(field) for doc in source_documents[source_class])
            if actual != expected:
                raise OuvragesMigrationError(
                    f"Distribution des types de {source_class} inattendue : {actual!r}"
                )

    known_desordre_ids = desordre_ids or set()
    rows_by_table: dict[str, list[OuvrageRow | CheminementRow]] = {
        table: [] for table in EXPECTED_BUSINESS_COUNTS
    }
    cheminement_troncon_links: list[LinkCheminementTronconRow] = []
    cheminement_desordre_links: list[LinkCheminementDesordreRow] = []
    seen_ids: set[UUID] = set()
    for source_class in IMMEDIATE_SOURCE_COUNTS:
        documents = sorted(
            source_documents.get(source_class, ()),
            key=lambda document: _uuid(
                document.get("_id"), context=f"{source_class}._id"
            ).int,
        )
        for document in documents:
            raw_id = document.get("_id")
            context = f"{source_class} {raw_id}"
            object_id = _uuid(raw_id, context=f"{context}._id")
            if object_id in seen_ids:
                raise OuvragesMigrationError(f"UUID objet dupliqué : {object_id}")
            seen_ids.add(object_id)
            rule = _mapping_rule(source_class, document)
            geometry_wkt, geometry_kind = transform_ouvrage_geometry(
                document.get("geometry"), mode=rule.geometry_mode, context=context
            )
            raw_troncon_id = document.get("linearId")
            troncon_id = (
                _uuid(raw_troncon_id, context=f"{context}.linearId")
                if raw_troncon_id not in (None, "")
                else None
            )
            if troncon_id is not None and troncon_id not in troncon_ids:
                raise OuvragesMigrationError(
                    f"{context}: linearId référence un tronçon absent"
                )
            if rule.table == "cheminements":
                rows_by_table[rule.table].append(
                    CheminementRow(
                        id=object_id,
                        type_cheminement_id=rule.type_id,
                        designation=_optional_text(document, "designation", context),
                        libelle=_optional_text(document, "libelle", context),
                        commentaire=_optional_text(document, "commentaire", context),
                        date_debut=_optional_date(document, "date_debut", context),
                        date_fin=_optional_date(document, "date_fin", context),
                        largeur=_optional_float(document, "largeur", context),
                        usage_source_id=_optional_source_reference(
                            document, "usageId", context
                        ),
                        statut_source=_optional_bool(document, "statut", context),
                        materiau_source_id=_optional_source_reference(
                            document, "materiauId", context
                        ),
                        revetement_source_id=_optional_source_reference(
                            document, "revetementId", context
                        ),
                        position_source_id=_optional_source_reference(
                            document, "positionId", context
                        ),
                        cote_source_id=_optional_source_reference(
                            document, "coteId", context
                        ),
                        securite_source_id=_optional_source_reference(
                            document, "securiteId", context
                        ),
                        orientation_ouvrage_source_id=_optional_source_reference(
                            document, "orientationOuvrageId", context
                        ),
                        position_haut_source_id=_optional_source_reference(
                            document, "positionHautId", context
                        ),
                        position_bas_source_id=_optional_source_reference(
                            document, "positionBasId", context
                        ),
                        revetement_haut_source_id=_optional_source_reference(
                            document, "revetementHautId", context
                        ),
                        revetement_bas_source_id=_optional_source_reference(
                            document, "revetementBasId", context
                        ),
                        dimension_horizontale=_optional_float(
                            document, "dimensionHorizontale", context
                        ),
                        dimension_verticale=_optional_float(
                            document, "dimensionVerticale", context
                        ),
                        numero_secteur=_optional_int(
                            document, "numeroSecteur", context
                        ),
                        geometry_wkt=geometry_wkt,
                        geometry_kind=geometry_kind,
                        valid=_required_bool(document, "valid", context),
                        source_class=source_class,
                    )
                )
                if troncon_id is not None:
                    cheminement_troncon_links.append(
                        LinkCheminementTronconRow(object_id, troncon_id)
                    )
                for desordre_id in _explicit_relation_ids(
                    document, "desordreIds", context
                ):
                    if desordre_id not in known_desordre_ids:
                        raise OuvragesMigrationError(
                            f"{context}: desordreIds référence un désordre absent"
                        )
                    cheminement_desordre_links.append(
                        LinkCheminementDesordreRow(object_id, desordre_id)
                    )
            else:
                rows_by_table[rule.table].append(OuvrageRow(
                    id=object_id,
                    type_id=rule.type_id,
                    designation=_optional_text(document, "designation", context),
                    commentaire=_optional_text(document, "commentaire", context),
                    date_debut=_optional_date(document, "date_debut", context),
                    geometry_wkt=geometry_wkt,
                    geometry_kind=geometry_kind,
                    troncon_id=troncon_id,
                    valid=_required_bool(document, "valid", context),
                    source_class=source_class,
                ))

    rows = {
        table: tuple(sorted(table_rows, key=lambda row: row.id.int))
        for table, table_rows in rows_by_table.items()
    }
    if len(cheminement_troncon_links) != len(
        {(row.cheminement_id, row.troncon_id) for row in cheminement_troncon_links}
    ):
        raise OuvragesMigrationError("Liaisons cheminement/tronçon dupliquées")
    if len(cheminement_desordre_links) != len(
        {(row.cheminement_id, row.desordre_id) for row in cheminement_desordre_links}
    ):
        raise OuvragesMigrationError("Liaisons cheminement/désordre dupliquées")
    prepared = PreparedOuvragesMigration(
        references=TARGET_REFERENCES,
        rows=rows,
        cheminement_troncon_links=tuple(sorted(
            cheminement_troncon_links,
            key=lambda row: (row.cheminement_id.int, row.troncon_id.int),
        )),
        cheminement_desordre_links=tuple(sorted(
            cheminement_desordre_links,
            key=lambda row: (row.cheminement_id.int, row.desordre_id.int),
        )),
        source_counts=source_counts,
        deferred_counts=deferred_counts,
    )
    if strict_counts:
        actual_counts = {table: len(table_rows) for table, table_rows in rows.items()}
        if actual_counts != EXPECTED_BUSINESS_COUNTS:
            raise OuvragesMigrationError(
                f"Comptes cibles Ouvrages inattendus : {actual_counts!r}"
            )
        if prepared.migrated_count != 117 or prepared.deferred_count != 1:
            raise OuvragesMigrationError("La décomposition 118 = 117 + 1 est invalide")
    return prepared


INSERT_STATEMENTS = {
    table: f"""
        INSERT INTO public.{table} (id, code, abrege, libelle, valid)
        VALUES (%s, %s, %s, %s, %s)
    """
    for table in TARGET_REFERENCES
}
INSERT_STATEMENTS.update(
    {
        table: f"""
            INSERT INTO public.{table}
                (id, type_id, designation, commentaire, date_debut,
                 geometry, troncon_id, valid)
            VALUES (%s, %s, %s, %s, %s, {geometry_sql()}, %s, %s)
        """
        for table in EXPECTED_BUSINESS_COUNTS
        if table != "cheminements"
    }
)
INSERT_STATEMENTS["cheminements"] = f"""
    INSERT INTO public.cheminements
        (id, type_cheminement_id, designation, libelle, commentaire,
         date_debut, date_fin, largeur, usage_source_id, statut_source,
         materiau_source_id, revetement_source_id, position_source_id,
         cote_source_id, securite_source_id, orientation_ouvrage_source_id,
         position_haut_source_id, position_bas_source_id,
         revetement_haut_source_id, revetement_bas_source_id,
         dimension_horizontale, dimension_verticale, numero_secteur,
         geometry, valid)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, {geometry_sql()}, %s)
"""
INSERT_STATEMENTS["link_cheminements_troncons"] = """
    INSERT INTO public.link_cheminements_troncons
        (cheminement_id, troncon_id)
    VALUES (%s, %s)
"""
INSERT_STATEMENTS["link_cheminements_desordres"] = """
    INSERT INTO public.link_cheminements_desordres
        (cheminement_id, desordre_id)
    VALUES (%s, %s)
"""
INSERT_STATEMENTS["ouvrages_hydrauliques"] = f"""
    INSERT INTO public.ouvrages_hydrauliques
        (id, type_id, designation, commentaire, date_debut,
         geometry, troncon_id, amenagement_hydraulique_id, valid)
    VALUES (%s, %s, %s, %s, %s, {geometry_sql()}, %s, %s, %s)
"""


def insert_prepared_ouvrages(
    cursor: Any,
    prepared: PreparedOuvragesMigration,
    *,
    crs_info: CRSInfo | None = None,
) -> None:
    """Insère le lot dans la transaction du noyau appelant."""

    if not prepared.enabled:
        return
    statements = dict(INSERT_STATEMENTS)
    expression = geometry_sql(crs_info)
    for table in EXPECTED_BUSINESS_COUNTS:
        statements[table] = statements[table].replace(geometry_sql(), expression)
    for table, rows in prepared.references.items():
        cursor.executemany(
            INSERT_STATEMENTS[table],
            [(row.id, row.code, row.abrege, row.libelle, row.valid) for row in rows],
        )
    for table, rows in prepared.rows.items():
        if rows:
            if table == "ouvrages_hydrauliques":
                values = [
                    (
                        row.id,
                        row.type_id,
                        row.designation,
                        row.commentaire,
                        row.date_debut,
                        row.geometry_wkt,
                        row.troncon_id,
                        row.amenagement_hydraulique_id,
                        row.valid,
                    )
                    for row in rows
                ]
            elif table == "cheminements":
                values = [
                    (
                        row.id,
                        row.type_cheminement_id,
                        row.designation,
                        row.libelle,
                        row.commentaire,
                        row.date_debut,
                        row.date_fin,
                        row.largeur,
                        row.usage_source_id,
                        row.statut_source,
                        row.materiau_source_id,
                        row.revetement_source_id,
                        row.position_source_id,
                        row.cote_source_id,
                        row.securite_source_id,
                        row.orientation_ouvrage_source_id,
                        row.position_haut_source_id,
                        row.position_bas_source_id,
                        row.revetement_haut_source_id,
                        row.revetement_bas_source_id,
                        row.dimension_horizontale,
                        row.dimension_verticale,
                        row.numero_secteur,
                        row.geometry_wkt,
                        row.valid,
                    )
                    for row in rows
                ]
            else:
                values = [
                    (
                        row.id,
                        row.type_id,
                        row.designation,
                        row.commentaire,
                        row.date_debut,
                        row.geometry_wkt,
                        row.troncon_id,
                        row.valid,
                    )
                    for row in rows
                ]
            cursor.executemany(
                statements[table],
                values,
            )
    if prepared.cheminement_troncon_links:
        cursor.executemany(
            statements["link_cheminements_troncons"],
            [
                (row.cheminement_id, row.troncon_id)
                for row in prepared.cheminement_troncon_links
            ],
        )
    if prepared.cheminement_desordre_links:
        cursor.executemany(
            statements["link_cheminements_desordres"],
            [
                (row.cheminement_id, row.desordre_id)
                for row in prepared.cheminement_desordre_links
            ],
        )
