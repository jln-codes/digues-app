"""Migration générique du domaine Végétation SIRS.

Les transformations de ce module dépendent des propriétés des documents. Les
exceptions propres à un corpus sont injectées depuis ``source_overrides``.
"""

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

from .source_overrides import SourceMigrationOverrides, get_source_overrides


VEGETATION_SOURCE_CLASSES = {
    "PlanVegetation": "fr.sirs.core.model.PlanVegetation",
    "ParcelleVegetation": "fr.sirs.core.model.ParcelleVegetation",
    "ArbreVegetation": "fr.sirs.core.model.ArbreVegetation",
    "PeuplementVegetation": "fr.sirs.core.model.PeuplementVegetation",
    "InvasiveVegetation": "fr.sirs.core.model.InvasiveVegetation",
}

REFERENCE_TABLES = (
    "ref_natures_vegetation",
    "ref_etats_sanitaires_vegetation",
    "ref_classes_hauteur_vegetation",
    "ref_classes_diametre_vegetation",
)
TARGET_PLAN_TABLE = "plans_gestion_vegetation"
TARGET_PARCELLE_TABLE = "parcelles_gestion_vegetation"
TARGET_LINK_TABLE = "link_parcelles_gestion_troncons"
TARGET_VEGETATION_TABLE = "vegetation"

KEEP_GEOMETRY = "KEEP_GEOMETRY"
DEGENERATE_LINE_TO_POINT = "DEGENERATE_LINE_TO_POINT"
POSITION_DEBUT_TO_POINT = "POSITION_DEBUT_TO_POINT"
RECONSTRUCT_FROM_EXPLICIT_GEOMETRY = "RECONSTRUCT_FROM_EXPLICIT_GEOMETRY"
KEEP_NULL = "KEEP_NULL"
MANUAL_REVIEW = "MANUAL_REVIEW"

ALLOWED_GEOMETRY_KINDS = frozenset({"POINT", "LINESTRING", "POLYGON"})


class VegetationMigrationError(RuntimeError):
    """Une donnée végétation ne peut pas être migrée sans perte silencieuse."""


@dataclass(frozen=True)
class VegetationReferenceRow:
    id: str
    code: str
    abrege: str
    libelle: str
    valid: bool = True


@dataclass(frozen=True)
class PlanGestionVegetationRow:
    id: UUID
    libelle: str | None
    annee_debut: int | None
    annee_fin: int | None
    valid: bool


@dataclass(frozen=True)
class ParcelleGestionVegetationRow:
    id: UUID
    plan_id: UUID | None
    designation: str | None
    date_debut: date | None
    geometry_wkt: str
    valid: bool


@dataclass(frozen=True)
class LinkParcelleGestionTronconRow:
    parcelle_gestion_id: UUID
    troncon_id: UUID


@dataclass(frozen=True)
class VegetationRow:
    id: UUID
    nature_id: str
    designation: str | None
    commentaire: str | None
    date_debut: date | None
    etat_sanitaire_id: str | None
    classe_hauteur_id: str | None
    classe_diametre_id: str | None
    geometry_wkt: str | None
    geometry_kind: str
    geometry_method: str
    parcelle_gestion_id: UUID
    valid: bool
    source_class: str


@dataclass(frozen=True)
class PreparedVegetationMigration:
    references: Mapping[str, tuple[VegetationReferenceRow, ...]]
    plans: tuple[PlanGestionVegetationRow, ...]
    parcelles: tuple[ParcelleGestionVegetationRow, ...]
    links: tuple[LinkParcelleGestionTronconRow, ...]
    vegetation: tuple[VegetationRow, ...]
    deferred_treatments: int
    deferred_planifications: int
    active_planification_flags: int
    warnings: tuple[str, ...]
    enabled: bool = True

    @classmethod
    def empty(cls) -> "PreparedVegetationMigration":
        return cls({}, (), (), (), (), 0, 0, 0, (), enabled=False)

    @property
    def expected_counts(self) -> dict[str, int]:
        counts = {table: len(self.references.get(table, ())) for table in REFERENCE_TABLES}
        counts.update(
            {
                TARGET_PLAN_TABLE: len(self.plans),
                TARGET_PARCELLE_TABLE: len(self.parcelles),
                TARGET_LINK_TABLE: len(self.links),
                TARGET_VEGETATION_TABLE: len(self.vegetation),
            }
        )
        return counts

    @property
    def geometry_counts(self) -> dict[str, int]:
        counts = Counter(row.geometry_kind for row in self.vegetation)
        return {
            "point": counts["point"],
            "linestring": counts["linestring"],
            "polygon": counts["polygon"],
            "null": counts["null"],
        }

    @property
    def method_counts(self) -> dict[str, int]:
        return dict(Counter(row.geometry_method for row in self.vegetation))

    @property
    def manual_review_ids(self) -> tuple[UUID, ...]:
        return tuple(
            row.id for row in self.vegetation if row.geometry_method == MANUAL_REVIEW
        )

    @property
    def manual_review_warnings(self) -> tuple[str, ...]:
        return tuple(
            warning for warning in self.warnings if warning.startswith("MANUAL_REVIEW ")
        )

    @property
    def invalid_count(self) -> int:
        return sum(not row.valid for row in self.vegetation)


TARGET_REFERENCES: Mapping[str, tuple[VegetationReferenceRow, ...]] = {
    "ref_natures_vegetation": (
        VegetationReferenceRow("ARB", "arbre", "ARB", "Arbre"),
        VegetationReferenceRow("PEU", "peuplement", "PEU", "Peuplement"),
        VegetationReferenceRow(
            "INV", "vegetation_invasive", "INV", "Végétation invasive"
        ),
        VegetationReferenceRow("IND", "indefini", "IND", "Indéfini"),
    ),
    "ref_etats_sanitaires_vegetation": (
        VegetationReferenceRow("SAI", "sain", "SAI", "Sain"),
        VegetationReferenceRow("DEP", "deperissant", "DEP", "Dépérissant"),
        VegetationReferenceRow("MOR", "mort", "MOR", "Mort"),
    ),
    "ref_classes_hauteur_vegetation": (
        VegetationReferenceRow("H1", "moins_7m", "H1", "< 7 m"),
        VegetationReferenceRow("H2", "7_15m", "H2", "7 à 15 m"),
        VegetationReferenceRow("H3", "15_20m", "H3", "15 à 20 m"),
        VegetationReferenceRow("H4", "20_30m", "H4", "20 à 30 m"),
        VegetationReferenceRow("H5", "plus_30m", "H5", "> 30 m"),
        VegetationReferenceRow("IND", "indefini", "IND", "Indéfini"),
    ),
    "ref_classes_diametre_vegetation": (
        VegetationReferenceRow("D1", "moins_10cm", "D1", "< 10 cm"),
        VegetationReferenceRow("D2", "10_20cm", "D2", "10 à 20 cm"),
        VegetationReferenceRow("D3", "20_40cm", "D3", "20 à 40 cm"),
        VegetationReferenceRow("D4", "40_60cm", "D4", "40 à 60 cm"),
        VegetationReferenceRow("D5", "plus_60cm", "D5", "> 60 cm"),
        VegetationReferenceRow("IND", "indefini", "IND", "Indéfini"),
    ),
}

NATURE_BY_SOURCE_CLASS = {
    "ArbreVegetation": "ARB",
    "PeuplementVegetation": "PEU",
    "InvasiveVegetation": "INV",
}

ETAT_SANITAIRE_MAPPING = {
    "RefEtatSanitaireVegetation:1": "SAI",
    "RefEtatSanitaireVegetation:2": "DEP",
    "RefEtatSanitaireVegetation:3": "MOR",
}
HAUTEUR_MAPPING = {
    "RefHauteurVegetation:1": "H1",
    "RefHauteurVegetation:2": "H2",
    "RefHauteurVegetation:3": "H3",
    "RefHauteurVegetation:4": "H4",
    "RefHauteurVegetation:5": "H5",
    "RefHauteurVegetation:99": "IND",
}
DIAMETRE_MAPPING = {
    "RefDiametreVegetation:1": "D1",
    "RefDiametreVegetation:2": "D2",
    "RefDiametreVegetation:3": "D3",
    "RefDiametreVegetation:4": "D4",
    "RefDiametreVegetation:5": "D5",
    "RefDiametreVegetation:99": "IND",
}

NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
COORDINATE = re.compile(rf"^\s*({NUMBER})\s+({NUMBER})\s*$")
WKT_HEADER = re.compile(r"^\s*([A-Za-z]+)\s*(.*)\s*$", re.DOTALL)


@dataclass(frozen=True)
class GeometryInfo:
    kind: str
    coordinates: tuple[tuple[Decimal, Decimal], ...]
    rings: tuple[tuple[tuple[Decimal, Decimal], ...], ...]
    valid: bool
    reason: str

    @property
    def bbox(self) -> tuple[Decimal, Decimal, Decimal, Decimal] | None:
        if not self.coordinates:
            return None
        xs = [point[0] for point in self.coordinates]
        ys = [point[1] for point in self.coordinates]
        return min(xs), min(ys), max(xs), max(ys)


def _uuid(value: Any, *, context: str) -> UUID:
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise VegetationMigrationError(f"{context} invalide : {value!r}") from exc


def _optional_text(document: Mapping[str, Any], field: str, context: str) -> str | None:
    value = document.get(field)
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise VegetationMigrationError(f"{context}.{field} doit être du texte")
    return value


def _optional_date(document: Mapping[str, Any], field: str, context: str) -> date | None:
    value = document.get(field)
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise VegetationMigrationError(f"{context}.{field} doit être une date ISO")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise VegetationMigrationError(
            f"{context}.{field} date ISO invalide : {value!r}"
        ) from exc


def _optional_int(document: Mapping[str, Any], field: str, context: str) -> int | None:
    value = document.get(field)
    if value in (None, ""):
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise VegetationMigrationError(f"{context}.{field} doit être un entier")
    return value


def _required_bool(document: Mapping[str, Any], field: str, context: str) -> bool:
    value = document.get(field)
    if not isinstance(value, bool):
        raise VegetationMigrationError(f"{context}.{field} doit être un booléen")
    return value


def _strip_parentheses(value: str) -> str:
    value = value.strip()
    if len(value) < 2 or value[0] != "(" or value[-1] != ")":
        raise ValueError("parenthèses WKT absentes")
    return value[1:-1].strip()


def _split_top_level(value: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(value):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                raise ValueError("parenthèses WKT déséquilibrées")
        elif char == "," and depth == 0:
            parts.append(value[start:index].strip())
            start = index + 1
    if depth:
        raise ValueError("parenthèses WKT déséquilibrées")
    parts.append(value[start:].strip())
    return parts


def _parse_coordinate(value: str) -> tuple[Decimal, Decimal]:
    match = COORDINATE.fullmatch(value)
    if not match:
        raise ValueError(f"coordonnée 2D invalide : {value!r}")
    try:
        return Decimal(match.group(1)), Decimal(match.group(2))
    except InvalidOperation as exc:
        raise ValueError(f"coordonnée invalide : {value!r}") from exc


def _parse_coordinate_list(value: str) -> tuple[tuple[Decimal, Decimal], ...]:
    return tuple(_parse_coordinate(item) for item in _split_top_level(value))


def _orientation(
    a: tuple[Decimal, Decimal],
    b: tuple[Decimal, Decimal],
    c: tuple[Decimal, Decimal],
) -> Decimal:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(
    a: tuple[Decimal, Decimal],
    b: tuple[Decimal, Decimal],
    p: tuple[Decimal, Decimal],
) -> bool:
    return (
        _orientation(a, b, p) == 0
        and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
        and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])
    )


def _segments_intersect(
    a: tuple[Decimal, Decimal],
    b: tuple[Decimal, Decimal],
    c: tuple[Decimal, Decimal],
    d: tuple[Decimal, Decimal],
) -> bool:
    o1, o2 = _orientation(a, b, c), _orientation(a, b, d)
    o3, o4 = _orientation(c, d, a), _orientation(c, d, b)
    if ((o1 > 0 > o2) or (o1 < 0 < o2)) and (
        (o3 > 0 > o4) or (o3 < 0 < o4)
    ):
        return True
    return any(
        (
            o1 == 0 and _on_segment(a, b, c),
            o2 == 0 and _on_segment(a, b, d),
            o3 == 0 and _on_segment(c, d, a),
            o4 == 0 and _on_segment(c, d, b),
        )
    )


def _ring_area(ring: tuple[tuple[Decimal, Decimal], ...]) -> Decimal:
    return sum(
        ring[index][0] * ring[index + 1][1]
        - ring[index + 1][0] * ring[index][1]
        for index in range(len(ring) - 1)
    ) / Decimal(2)


def _ring_self_intersects(ring: tuple[tuple[Decimal, Decimal], ...]) -> bool:
    segment_count = len(ring) - 1
    for first in range(segment_count):
        for second in range(first + 1, segment_count):
            if second == first + 1:
                continue
            if first == 0 and second == segment_count - 1:
                continue
            if _segments_intersect(
                ring[first],
                ring[first + 1],
                ring[second],
                ring[second + 1],
            ):
                return True
    return False


def _rings_intersect(
    first: tuple[tuple[Decimal, Decimal], ...],
    second: tuple[tuple[Decimal, Decimal], ...],
) -> bool:
    return any(
        _segments_intersect(a, b, c, d)
        for a, b in zip(first, first[1:])
        for c, d in zip(second, second[1:])
    )


def _point_in_ring(
    point: tuple[Decimal, Decimal], ring: tuple[tuple[Decimal, Decimal], ...]
) -> bool:
    x, y = point
    inside = False
    for a, b in zip(ring, ring[1:]):
        if _on_segment(a, b, point):
            return True
        if (a[1] > y) != (b[1] > y):
            crossing_x = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if crossing_x > x:
                inside = not inside
    return inside


def inspect_wkt(value: Any) -> GeometryInfo | None:
    """Analyse les WKT 2D simples sans réparer ni reprojeter."""

    if value in (None, ""):
        return None
    if not isinstance(value, str):
        return GeometryInfo("UNKNOWN", (), (), False, "WKT non textuel")
    header = WKT_HEADER.fullmatch(value)
    if not header:
        return GeometryInfo("UNKNOWN", (), (), False, "WKT illisible")
    kind = header.group(1).upper()
    body = header.group(2)
    if kind not in ALLOWED_GEOMETRY_KINDS:
        return GeometryInfo(kind, (), (), False, f"type {kind} non autorisé")
    try:
        if kind == "POINT":
            coordinates = (_parse_coordinate(_strip_parentheses(body)),)
            return GeometryInfo(kind, coordinates, (), True, "valide")
        if kind == "LINESTRING":
            coordinates = _parse_coordinate_list(_strip_parentheses(body))
            valid = len(coordinates) >= 2 and len(set(coordinates)) >= 2
            reason = "valide" if valid else "LineString dégénérée"
            return GeometryInfo(kind, coordinates, (), valid, reason)

        polygon_body = _strip_parentheses(body)
        rings = tuple(
            _parse_coordinate_list(_strip_parentheses(item))
            for item in _split_top_level(polygon_body)
        )
        coordinates = tuple(point for ring in rings for point in ring)
        if not rings:
            return GeometryInfo(kind, coordinates, rings, False, "Polygon sans anneau")
        for ring in rings:
            if len(ring) < 4 or ring[0] != ring[-1] or len(set(ring[:-1])) < 3:
                return GeometryInfo(
                    kind, coordinates, rings, False, "anneau Polygon dégénéré"
                )
            if _ring_area(ring) == 0:
                return GeometryInfo(kind, coordinates, rings, False, "aire nulle")
            if _ring_self_intersects(ring):
                return GeometryInfo(kind, coordinates, rings, False, "auto-intersection")
        outer = rings[0]
        for index, hole in enumerate(rings[1:], start=1):
            if not _point_in_ring(hole[0], outer) or _rings_intersect(outer, hole):
                return GeometryInfo(
                    kind, coordinates, rings, False, f"trou {index} invalide"
                )
        for first in range(1, len(rings)):
            for second in range(first + 1, len(rings)):
                if _rings_intersect(rings[first], rings[second]):
                    return GeometryInfo(
                        kind, coordinates, rings, False, "trous en intersection"
                    )
        return GeometryInfo(kind, coordinates, rings, True, "valide")
    except (ValueError, InvalidOperation) as exc:
        return GeometryInfo(kind, (), (), False, str(exc))


def _bbox_disjoint(first: GeometryInfo, second: GeometryInfo) -> bool:
    a, b = first.bbox, second.bbox
    if a is None or b is None:
        return True
    return a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1]


def _substantially_divergent(first: GeometryInfo, second: GeometryInfo) -> bool:
    if first.kind != second.kind:
        return True
    if first.coordinates == second.coordinates and first.rings == second.rings:
        return False
    # Une disjonction des enveloppes suffit à établir un conflit. Une analyse
    # plus fine des versions qui se recouvrent reste volontairement prudente.
    return _bbox_disjoint(first, second)


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _point_wkt(point: tuple[Decimal, Decimal]) -> str:
    return f"POINT ({_decimal_text(point[0])} {_decimal_text(point[1])})"


def _manual_review(
    object_id: UUID, source_class: str, reason: str, warnings: list[str]
) -> tuple[None, str, str]:
    warnings.append(f"MANUAL_REVIEW {source_class} {object_id}: {reason}")
    return None, "null", MANUAL_REVIEW


def resolve_vegetation_geometry(
    document: Mapping[str, Any],
    *,
    source_class: str,
    object_id: UUID,
    overrides: SourceMigrationOverrides,
    warnings: list[str],
) -> tuple[str | None, str, str]:
    """Choisit une géométrie cible par propriétés et override explicite."""

    geometry_wkt = document.get("geometry")
    explicit_wkt = document.get("explicitGeometry")
    geometry = inspect_wkt(geometry_wkt)
    explicit = inspect_wkt(explicit_wkt)

    override_source = overrides.vegetation_geometry_source_by_id.get(object_id.hex)
    if override_source is not None:
        if override_source != "explicitGeometry":
            raise VegetationMigrationError(
                f"Override géométrique inconnu pour {object_id}: {override_source!r}"
            )
        if not isinstance(explicit_wkt, str) or explicit is None or not explicit.valid:
            raise VegetationMigrationError(
                f"Override {object_id}: explicitGeometry absente ou invalide"
            )
        warnings.append(
            f"{source_class} {object_id}: explicitGeometry sélectionnée par "
            "override spécifique à la base source"
        )
        return explicit_wkt, explicit.kind.lower(), RECONSTRUCT_FROM_EXPLICIT_GEOMETRY

    if (
        source_class == "ArbreVegetation"
        and geometry is not None
        and geometry.kind == "LINESTRING"
        and not geometry.valid
        and geometry.coordinates
        and len(set(geometry.coordinates)) == 1
    ):
        return (
            _point_wkt(geometry.coordinates[0]),
            "point",
            DEGENERATE_LINE_TO_POINT,
        )

    if geometry is None and source_class == "ArbreVegetation":
        position_debut = inspect_wkt(document.get("positionDebut"))
        position_fin = inspect_wkt(document.get("positionFin"))
        if (
            position_debut is not None
            and position_fin is not None
            and position_debut.valid
            and position_fin.valid
            and position_debut.kind == position_fin.kind == "POINT"
            and position_debut.coordinates == position_fin.coordinates
        ):
            return (
                _point_wkt(position_debut.coordinates[0]),
                "point",
                POSITION_DEBUT_TO_POINT,
            )

    if geometry is not None and geometry.valid:
        if explicit is not None and explicit.valid and _substantially_divergent(
            geometry, explicit
        ):
            return _manual_review(
                object_id,
                source_class,
                "geometry et explicitGeometry valides mais divergentes",
                warnings,
            )
        return str(geometry_wkt), geometry.kind.lower(), KEEP_GEOMETRY

    if explicit is not None and explicit.valid:
        compatible = geometry is None or (
            geometry.kind == explicit.kind and not _bbox_disjoint(geometry, explicit)
        )
        if compatible:
            return (
                str(explicit_wkt),
                explicit.kind.lower(),
                RECONSTRUCT_FROM_EXPLICIT_GEOMETRY,
            )

    if geometry is None:
        return None, "null", KEEP_NULL

    return _manual_review(
        object_id,
        source_class,
        f"geometry source non exploitable ({geometry.reason})",
        warnings,
    )


def _mapped_reference(
    value: Any,
    mapping: Mapping[str, str],
    *,
    context: str,
    warnings: list[str],
) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise VegetationMigrationError(f"{context}: référence source non textuelle")
    target = mapping.get(value)
    if target is None:
        warnings.append(f"{context}: référence source inconnue {value!r} ; cible NULL")
    return target


def prepare_vegetation_migration(
    source_documents: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    troncon_ids: set[UUID],
    source_database: str | None = None,
    overrides: SourceMigrationOverrides | None = None,
) -> PreparedVegetationMigration:
    """Prépare plans, parcelles, liens et objets sans relation spatiale induite."""

    selected_overrides = overrides or get_source_overrides(source_database)
    warnings: list[str] = []

    plans: list[PlanGestionVegetationRow] = []
    plan_ids: set[UUID] = set()
    for document in sorted(
        source_documents.get("PlanVegetation", ()), key=lambda item: str(item.get("_id"))
    ):
        object_id = _uuid(document.get("_id"), context="PlanVegetation._id")
        context = f"PlanVegetation {object_id}"
        if object_id in plan_ids:
            raise VegetationMigrationError(f"UUID plan dupliqué : {object_id}")
        plan_ids.add(object_id)
        plans.append(
            PlanGestionVegetationRow(
                id=object_id,
                libelle=_optional_text(document, "libelle", context),
                annee_debut=_optional_int(document, "anneeDebut", context),
                annee_fin=_optional_int(document, "anneeFin", context),
                valid=_required_bool(document, "valid", context),
            )
        )

    parcelles: list[ParcelleGestionVegetationRow] = []
    links: list[LinkParcelleGestionTronconRow] = []
    parcelle_ids: set[UUID] = set()
    deferred_planifications = 0
    active_planification_flags = 0
    for document in sorted(
        source_documents.get("ParcelleVegetation", ()),
        key=lambda item: str(item.get("_id")),
    ):
        object_id = _uuid(document.get("_id"), context="ParcelleVegetation._id")
        context = f"ParcelleVegetation {object_id}"
        if object_id in parcelle_ids:
            raise VegetationMigrationError(f"UUID parcelle dupliqué : {object_id}")
        parcelle_ids.add(object_id)
        raw_plan_id = document.get("planId")
        plan_id = (
            _uuid(raw_plan_id, context=f"{context}.planId") if raw_plan_id else None
        )
        if plan_id is not None and plan_id not in plan_ids:
            raise VegetationMigrationError(f"{context}: planId référence un plan absent")
        geometry_wkt = document.get("geometry")
        geometry = inspect_wkt(geometry_wkt)
        if geometry is None or geometry.kind != "LINESTRING" or not geometry.valid:
            reason = geometry.reason if geometry is not None else "geometry absente"
            raise VegetationMigrationError(
                f"{context}: LineString de parcelle invalide ({reason})"
            )
        parcelles.append(
            ParcelleGestionVegetationRow(
                id=object_id,
                plan_id=plan_id,
                designation=_optional_text(document, "designation", context),
                date_debut=_optional_date(document, "date_debut", context),
                geometry_wkt=str(geometry_wkt),
                valid=_required_bool(document, "valid", context),
            )
        )
        raw_troncons: list[Any] = []
        if document.get("linearId") not in (None, ""):
            raw_troncons.append(document["linearId"])
        if document.get("linearIds") not in (None, ""):
            if not isinstance(document["linearIds"], list):
                raise VegetationMigrationError(f"{context}.linearIds doit être une liste")
            raw_troncons.extend(document["linearIds"])
        normalized_troncons = {
            _uuid(raw_id, context=f"{context}.linearId") for raw_id in raw_troncons
        }
        for troncon_id in normalized_troncons:
            if troncon_id not in troncon_ids:
                raise VegetationMigrationError(
                    f"{context}: relation explicite vers un tronçon absent"
                )
            links.append(LinkParcelleGestionTronconRow(object_id, troncon_id))

        planifications = document.get("planifications")
        if planifications not in (None, []):
            if not isinstance(planifications, list) or not all(
                isinstance(flag, bool) for flag in planifications
            ):
                raise VegetationMigrationError(
                    f"{context}.planifications doit être une liste de booléens"
                )
            deferred_planifications += 1
            active_planification_flags += sum(planifications)

    if len(links) != len(
        {(row.parcelle_gestion_id, row.troncon_id) for row in links}
    ):
        raise VegetationMigrationError("Relations parcelle/tronçon dupliquées")

    rows: list[VegetationRow] = []
    vegetation_ids: set[UUID] = set()
    deferred_treatments = 0
    for source_class in NATURE_BY_SOURCE_CLASS:
        for document in sorted(
            source_documents.get(source_class, ()),
            key=lambda item: str(item.get("_id")),
        ):
            object_id = _uuid(document.get("_id"), context=f"{source_class}._id")
            context = f"{source_class} {object_id}"
            if object_id in vegetation_ids:
                raise VegetationMigrationError(f"UUID végétation dupliqué : {object_id}")
            vegetation_ids.add(object_id)
            parcelle_id = _uuid(
                document.get("parcelleId"), context=f"{context}.parcelleId"
            )
            if parcelle_id not in parcelle_ids:
                raise VegetationMigrationError(
                    f"{context}: parcelleId référence une parcelle absente"
                )
            geometry_wkt, geometry_kind, geometry_method = resolve_vegetation_geometry(
                document,
                source_class=source_class,
                object_id=object_id,
                overrides=selected_overrides,
                warnings=warnings,
            )
            rows.append(
                VegetationRow(
                    id=object_id,
                    nature_id=NATURE_BY_SOURCE_CLASS[source_class],
                    designation=_optional_text(document, "designation", context),
                    commentaire=_optional_text(document, "commentaire", context),
                    date_debut=_optional_date(document, "date_debut", context),
                    etat_sanitaire_id=_mapped_reference(
                        document.get("etatSanitaireId"),
                        ETAT_SANITAIRE_MAPPING,
                        context=f"{context}.etatSanitaireId",
                        warnings=warnings,
                    ),
                    classe_hauteur_id=_mapped_reference(
                        document.get("hauteurId"),
                        HAUTEUR_MAPPING,
                        context=f"{context}.hauteurId",
                        warnings=warnings,
                    ),
                    classe_diametre_id=_mapped_reference(
                        document.get("diametreId"),
                        DIAMETRE_MAPPING,
                        context=f"{context}.diametreId",
                        warnings=warnings,
                    ),
                    geometry_wkt=geometry_wkt,
                    geometry_kind=geometry_kind,
                    geometry_method=geometry_method,
                    parcelle_gestion_id=parcelle_id,
                    valid=_required_bool(document, "valid", context),
                    source_class=source_class,
                )
            )
            if document.get("traitement") not in (None, {}):
                deferred_treatments += 1

    manual_count = sum(row.geometry_method == MANUAL_REVIEW for row in rows)
    manual_warning_count = sum(
        warning.startswith("MANUAL_REVIEW ") for warning in warnings
    )
    if manual_count != manual_warning_count:
        raise VegetationMigrationError(
            "Chaque MANUAL_REVIEW doit produire exactement un warning dédié"
        )
    if deferred_treatments:
        warnings.append(
            f"{deferred_treatments} TraitementZoneVegetation embarqué(s) différé(s)"
        )
    if deferred_planifications:
        warnings.append(
            f"{deferred_planifications} planification(s) de végétation différée(s) "
            f"({active_planification_flags} indicateur(s) actif(s))"
        )

    return PreparedVegetationMigration(
        references=TARGET_REFERENCES,
        plans=tuple(sorted(plans, key=lambda row: row.id.int)),
        parcelles=tuple(sorted(parcelles, key=lambda row: row.id.int)),
        links=tuple(
            sorted(
                links,
                key=lambda row: (row.parcelle_gestion_id.int, row.troncon_id.int),
            )
        ),
        vegetation=tuple(sorted(rows, key=lambda row: row.id.int)),
        deferred_treatments=deferred_treatments,
        deferred_planifications=deferred_planifications,
        active_planification_flags=active_planification_flags,
        warnings=tuple(warnings),
    )


INSERT_STATEMENTS = {
    table: f"""
        INSERT INTO public.{table} (id, code, abrege, libelle, valid)
        VALUES (%s, %s, %s, %s, %s)
    """
    for table in REFERENCE_TABLES
}
INSERT_STATEMENTS.update(
    {
        TARGET_PLAN_TABLE: f"""
            INSERT INTO public.{TARGET_PLAN_TABLE}
                (id, libelle, annee_debut, annee_fin, valid)
            VALUES (%s, %s, %s, %s, %s)
        """,
        TARGET_PARCELLE_TABLE: f"""
            INSERT INTO public.{TARGET_PARCELLE_TABLE}
                (id, plan_id, designation, date_debut, geometry, valid)
            VALUES (%s, %s, %s, %s, {geometry_sql()}, %s)
        """,
        TARGET_LINK_TABLE: f"""
            INSERT INTO public.{TARGET_LINK_TABLE}
                (parcelle_gestion_id, troncon_id)
            VALUES (%s, %s)
        """,
        TARGET_VEGETATION_TABLE: f"""
            INSERT INTO public.{TARGET_VEGETATION_TABLE}
                (id, nature_id, designation, commentaire,
                 date_debut, etat_sanitaire_id, classe_hauteur_id,
                 classe_diametre_id, geometry, parcelle_gestion_id, valid)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                    {geometry_sql()}, %s, %s)
        """,
    }
)


def insert_prepared_vegetation(
    cursor: Any,
    prepared: PreparedVegetationMigration,
    *,
    crs_info: CRSInfo | None = None,
) -> None:
    """Insère le bloc Végétation dans la transaction globale."""

    if not prepared.enabled:
        return
    statements = dict(INSERT_STATEMENTS)
    expression = geometry_sql(crs_info)
    for table in (TARGET_PARCELLE_TABLE, TARGET_VEGETATION_TABLE):
        statements[table] = statements[table].replace(geometry_sql(), expression)
    for table in REFERENCE_TABLES:
        cursor.executemany(
            INSERT_STATEMENTS[table],
            [
                (row.id, row.code, row.abrege, row.libelle, row.valid)
                for row in prepared.references[table]
            ],
        )
    if prepared.plans:
        cursor.executemany(
            INSERT_STATEMENTS[TARGET_PLAN_TABLE],
            [
                (row.id, row.libelle, row.annee_debut, row.annee_fin, row.valid)
                for row in prepared.plans
            ],
        )
    if prepared.parcelles:
        cursor.executemany(
            statements[TARGET_PARCELLE_TABLE],
            [
                (
                    row.id,
                    row.plan_id,
                    row.designation,
                    row.date_debut,
                    row.geometry_wkt,
                    row.valid,
                )
                for row in prepared.parcelles
            ],
        )
    if prepared.links:
        cursor.executemany(
            INSERT_STATEMENTS[TARGET_LINK_TABLE],
            [(row.parcelle_gestion_id, row.troncon_id) for row in prepared.links],
        )
    if prepared.vegetation:
        cursor.executemany(
            statements[TARGET_VEGETATION_TABLE],
            [
                (
                    row.id,
                    row.nature_id,
                    row.designation,
                    row.commentaire,
                    row.date_debut,
                    row.etat_sanitaire_id,
                    row.classe_hauteur_id,
                    row.classe_diametre_id,
                    row.geometry_wkt,
                    row.parcelle_gestion_id,
                    row.valid,
                )
                for row in prepared.vegetation
            ],
        )
