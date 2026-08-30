"""Normalisation générique des observations et photos SIRS.

Les anciennes photos directement embarquées dans un objet métier sont
regroupées par objet et date sous une observation synthétique déterministe.
La cible ne conserve ainsi qu'un seul chemin relationnel : objet → observation
→ photo.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID, uuid5


OWNER_FIELDS = (
    "desordre_id",
    "troncon_id",
    "ouvrage_hydraulique_id",
    "equipement_mesure_id",
    "cheminement_id",
    "mobilier_id",
    "reseau_technique_id",
    "amenagement_hydraulique_id",
    "vegetation_id",
)

# Namespace stable propre à sirs-postgre. Il rend les observations synthétiques
# reproductibles sans dépendre d'un UUID ou d'un nom propre à cabbalr.
SYNTHETIC_OBSERVATION_NAMESPACE = UUID("8708bb95-4705-5372-8382-11a4455aef50")


class MediaMigrationError(RuntimeError):
    """Une observation ou photo source ne peut pas être normalisée."""


@dataclass(frozen=True)
class OwnerBinding:
    owner_field: str
    owner_id: UUID

    def __post_init__(self) -> None:
        if self.owner_field not in OWNER_FIELDS:
            raise ValueError(f"Parent d'observation inconnu : {self.owner_field}")


@dataclass(frozen=True)
class ObservationRow:
    id: UUID
    desordre_id: UUID | None = None
    troncon_id: UUID | None = None
    ouvrage_hydraulique_id: UUID | None = None
    equipement_mesure_id: UUID | None = None
    cheminement_id: UUID | None = None
    mobilier_id: UUID | None = None
    reseau_technique_id: UUID | None = None
    amenagement_hydraulique_id: UUID | None = None
    vegetation_id: UUID | None = None
    urgence_id: str | None = None
    designation: str | None = None
    date: date | None = None
    evolution: str | None = None
    valid: bool = True
    synthetic: bool = False

    @classmethod
    def for_owner(cls, *, id: UUID, owner: OwnerBinding, **values: Any) -> "ObservationRow":
        return cls(id=id, **{owner.owner_field: owner.owner_id}, **values)

    @property
    def parent_count(self) -> int:
        return sum(getattr(self, field) is not None for field in OWNER_FIELDS)

    @property
    def parent_values(self) -> tuple[UUID | None, ...]:
        return tuple(getattr(self, field) for field in OWNER_FIELDS)


@dataclass(frozen=True)
class PhotoRow:
    id: UUID
    observation_id: UUID
    chemin_source: str
    date: date | None
    designation: str | None
    valid: bool


@dataclass(frozen=True)
class PreparedMediaMigration:
    observations: tuple[ObservationRow, ...]
    photos: tuple[PhotoRow, ...]
    direct_photo_counts: Mapping[str, int]
    warnings: tuple[str, ...]

    @property
    def synthetic_observation_count(self) -> int:
        return sum(row.synthetic for row in self.observations)

    @property
    def direct_troncon_photos(self) -> int:
        return self.direct_photo_counts.get("troncon_id", 0)

    @property
    def direct_other_photos(self) -> int:
        return sum(self.direct_photo_counts.values()) - self.direct_troncon_photos


def _uuid(value: Any, *, context: str) -> UUID:
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise MediaMigrationError(f"{context}: UUID absent ou invalide : {value!r}") from exc


def _text(value: Any, *, context: str, required: bool = False) -> str | None:
    if value in (None, ""):
        if required:
            raise MediaMigrationError(f"{context}: texte obligatoire absent")
        return None
    if not isinstance(value, str):
        raise MediaMigrationError(f"{context}: texte invalide : {value!r}")
    return value


def _valid(value: Any, *, context: str) -> bool:
    if not isinstance(value, bool):
        raise MediaMigrationError(f"{context}: booléen valid absent ou invalide")
    return value


def _date(value: Any, *, context: str, warnings: list[str], permissive: bool) -> date | None:
    if value in (None, ""):
        if permissive:
            warnings.append(f"{context}: date absente ; date cible NULL")
        return None
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    if permissive:
        warnings.append(f"{context}: date inexploitable {value!r} ; date cible NULL")
        return None
    raise MediaMigrationError(f"{context}: date ISO invalide : {value!r}")


def _items(document: Mapping[str, Any], field: str, *, context: str) -> Sequence[Mapping[str, Any]]:
    value = document.get(field)
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise MediaMigrationError(f"{context}: liste {field} invalide")
    return value


def _photo_row(
    photo: Mapping[str, Any],
    *,
    observation_id: UUID,
    context: str,
    warnings: list[str],
    permissive_date: bool,
) -> PhotoRow:
    photo_id = _uuid(photo.get("id") or photo.get("_id"), context=f"{context}.id")
    return PhotoRow(
        id=photo_id,
        observation_id=observation_id,
        chemin_source=_text(photo.get("chemin"), context=f"{context}.chemin", required=True) or "",
        date=_date(photo.get("date"), context=context, warnings=warnings, permissive=permissive_date),
        designation=_text(photo.get("designation"), context=f"{context}.designation"),
        valid=_valid(photo.get("valid"), context=context),
    )


def prepare_media_migration(
    source_documents: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    owner_bindings: Mapping[tuple[str, UUID], OwnerBinding],
    urgence_ids: frozenset[str] | set[str],
) -> PreparedMediaMigration:
    """Aplatit les observations et normalise toutes les photos des objets migrés."""

    observations: list[ObservationRow] = []
    photos: list[PhotoRow] = []
    warnings: list[str] = []
    direct_counts: Counter[str] = Counter()

    for source_class, documents in source_documents.items():
        for document in documents:
            try:
                source_id = UUID(str(document.get("_id")))
            except (ValueError, TypeError, AttributeError):
                continue
            owner = owner_bindings.get((source_class, source_id))
            if owner is None:
                continue
            object_context = f"{source_class} {source_id}"

            for raw_observation in _items(document, "observations", context=object_context):
                observation_id = _uuid(
                    raw_observation.get("id") or raw_observation.get("_id"),
                    context=f"{object_context}.observation",
                )
                observation_context = f"Observation {observation_id}"
                urgence_id = None
                if owner.owner_field == "desordre_id":
                    raw_urgence = raw_observation.get("urgenceId")
                    if raw_urgence not in (None, ""):
                        urgence_id = str(raw_urgence)
                        if urgence_id not in urgence_ids:
                            raise MediaMigrationError(
                                f"{observation_context}: urgenceId référence une urgence absente"
                            )
                observations.append(
                    ObservationRow.for_owner(
                        id=observation_id,
                        owner=owner,
                        urgence_id=urgence_id,
                        designation=_text(raw_observation.get("designation"), context=f"{observation_context}.designation"),
                        date=_date(raw_observation.get("date"), context=observation_context, warnings=warnings, permissive=False),
                        evolution=_text(raw_observation.get("evolution"), context=f"{observation_context}.evolution"),
                        valid=_valid(raw_observation.get("valid"), context=observation_context),
                    )
                )
                for raw_photo in _items(raw_observation, "photos", context=observation_context):
                    photos.append(
                        _photo_row(
                            raw_photo,
                            observation_id=observation_id,
                            context=f"{observation_context}.photo",
                            warnings=warnings,
                            permissive_date=False,
                        )
                    )

            grouped: defaultdict[date | None, list[tuple[Mapping[str, Any], date | None]]] = defaultdict(list)
            for raw_photo in _items(document, "photos", context=object_context):
                photo_id = raw_photo.get("id") or raw_photo.get("_id")
                parsed_date = _date(
                    raw_photo.get("date"),
                    context=f"Photo directe {photo_id}",
                    warnings=warnings,
                    permissive=True,
                )
                grouped[parsed_date].append((raw_photo, parsed_date))

            for photo_date, grouped_photos in grouped.items():
                date_key = photo_date.isoformat() if photo_date else "NULL"
                observation_id = uuid5(
                    SYNTHETIC_OBSERVATION_NAMESPACE,
                    f"{owner.owner_field}:{owner.owner_id}:{date_key}",
                )
                observations.append(
                    ObservationRow.for_owner(
                        id=observation_id,
                        owner=owner,
                        designation="Photos migrées",
                        date=photo_date,
                        valid=True,
                        synthetic=True,
                    )
                )
                direct_counts[owner.owner_field] += len(grouped_photos)
                for raw_photo, _ in grouped_photos:
                    normalized_photo = dict(raw_photo)
                    normalized_photo["date"] = (
                        photo_date.isoformat() if photo_date is not None else None
                    )
                    photos.append(
                        _photo_row(
                            normalized_photo,
                            observation_id=observation_id,
                            context=f"Photo directe {raw_photo.get('id') or raw_photo.get('_id')}",
                            warnings=warnings,
                            permissive_date=False,
                        )
                    )

    observation_ids = [row.id for row in observations]
    if len(observation_ids) != len(set(observation_ids)):
        raise MediaMigrationError("Identifiants d'observation dupliqués")
    if any(row.parent_count != 1 for row in observations):
        raise MediaMigrationError("Une observation préparée ne possède pas exactement un parent")
    photo_ids = [row.id for row in photos]
    if len(photo_ids) != len(set(photo_ids)):
        raise MediaMigrationError("Identifiants de photo dupliqués")
    known_observations = set(observation_ids)
    if any(row.observation_id not in known_observations for row in photos):
        raise MediaMigrationError("Une photo préparée référence une observation absente")

    return PreparedMediaMigration(
        observations=tuple(sorted(observations, key=lambda row: row.id.int)),
        photos=tuple(sorted(photos, key=lambda row: row.id.int)),
        direct_photo_counts=dict(direct_counts),
        warnings=tuple(warnings),
    )
