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

from .validation import CoreValidationResult, validate_core_migration


CORE_SOURCE_CLASSES = {
    "SystemeEndiguement": "fr.sirs.core.model.SystemeEndiguement",
    "Digue": "fr.sirs.core.model.Digue",
    "TronconDigue": "fr.sirs.core.model.TronconDigue",
    "Desordre": "fr.sirs.core.model.Desordre",
}

CORE_FIELD_MAPPINGS = {
    "systeme_endiguement": (
        "_id → UUID → id",
        "libelle → texte inchangé → libelle",
        "valid → booléen inchangé → valid",
    ),
    "digue": (
        "_id → UUID → id",
        "systemeEndiguementId absent ou UUID → systeme_endiguement_id nullable",
        "libelle → texte inchangé → libelle",
        "valid → booléen inchangé → valid",
    ),
    "troncon": (
        "_id → UUID → id",
        "digueId → UUID vérifié → digue_id",
        "libelle → texte inchangé → libelle",
        "geometry WKT LINESTRING → ST_GeomFromText(..., 3950) → geometry",
        "valid → booléen inchangé → valid",
    ),
    "desordre": (
        "_id → UUID → id",
        "designation/commentaire → textes inchangés → colonnes homonymes",
        "date_debut/date_fin ISO → DATE → colonnes homonymes",
        "positionDebut/positionFin → POINT ou LINESTRING SRID 3950 → geometry",
        "valid → booléen inchangé → valid",
        "geometry source → comptée dans le rapport, non utilisée pour la cible",
    ),
    "link_desordre_troncon": (
        "aucune source → gen_random_uuid() PostgreSQL → id technique",
        "Desordre._id → UUID → desordre_id",
        "Desordre.linearId → UUID de TronconDigue vérifié → troncon_id",
    ),
    "observation": (
        "Desordre.observations[].id → UUID → id",
        "Desordre._id → UUID injecté → desordre_id",
        "designation → texte inchangé ou absent → designation nullable",
        "date ISO → DATE → date",
        "evolution → texte inchangé → evolution",
        "valid → booléen inchangé → valid",
    ),
    "photo": (
        "Observation.photos[].id → UUID → id",
        "Observation.id → UUID injecté → observation_id",
        "chemin → texte inchangé sans déduplication → chemin_source",
        "date ISO → DATE → date",
        "designation → texte inchangé → designation",
        "valid → booléen inchangé → valid",
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
class ObservationRow:
    id: UUID
    desordre_id: UUID
    designation: str | None
    date: date | None
    evolution: str | None
    valid: bool


@dataclass(frozen=True)
class PhotoRow:
    id: UUID
    observation_id: UUID
    chemin_source: str
    date: date | None
    designation: str | None
    valid: bool


@dataclass(frozen=True)
class PreparedCoreMigration:
    systemes: tuple[SystemeEndiguementRow, ...]
    digues: tuple[DigueRow, ...]
    troncons: tuple[TronconRow, ...]
    desordres: tuple[DesordreRow, ...]
    links: tuple[LinkDesordreTronconRow, ...]
    observations: tuple[ObservationRow, ...]
    photos: tuple[PhotoRow, ...]
    digues_without_system: int
    desordre_source_geometry_present: int
    desordre_source_geometry_absent: int
    ignored_direct_troncon_photos: int
    warnings: tuple[str, ...]

    @property
    def expected_counts(self) -> dict[str, int]:
        return {
            "systeme_endiguement": len(self.systemes),
            "digue": len(self.digues),
            "troncon": len(self.troncons),
            "desordre": len(self.desordres),
            "link_desordre_troncon": len(self.links),
            "observation": len(self.observations),
            "photo": len(self.photos),
        }

    @property
    def desordre_geometry_counts(self) -> dict[str, int]:
        return {
            "point": sum(row.geometry_kind == "point" for row in self.desordres),
            "linestring": sum(
                row.geometry_kind == "linestring" for row in self.desordres
            ),
            "null": sum(row.geometry_kind == "null" for row in self.desordres),
        }


@dataclass(frozen=True)
class CoreMigrationReport:
    prepared: PreparedCoreMigration
    validation: CoreValidationResult


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


def prepare_core_migration(
    source_documents: Mapping[str, Sequence[Mapping[str, Any]]],
) -> PreparedCoreMigration:
    """Transforme les documents live en lignes typées, sans accès PostgreSQL."""

    warnings: list[str] = []

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
    _ensure_unique_ids(systemes, "systeme_endiguement")
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
    _ensure_unique_ids(digues, "digue")
    digue_ids = {row.id for row in digues}

    troncons_list: list[TronconRow] = []
    direct_troncon_photos = 0
    for doc in _sorted_documents(
        source_documents.get("TronconDigue", ()),
        id_field="_id",
        context="TronconDigue",
    ):
        context = f"TronconDigue {doc.get('_id')}"
        digue_id = couchdb_id_to_uuid(doc.get("digueId"), context=f"{context}.digueId")
        if digue_id not in digue_ids:
            raise CoreMigrationError(f"{context}: digueId référence une digue absente")
        direct_photos = doc.get("photos") or []
        if not isinstance(direct_photos, list):
            raise CoreMigrationError(f"{context}: photos directes invalides")
        direct_troncon_photos += len(direct_photos)
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
    _ensure_unique_ids(troncons, "troncon")
    troncon_ids = {row.id for row in troncons}

    desordres_list: list[DesordreRow] = []
    links_list: list[LinkDesordreTronconRow] = []
    observations_list: list[ObservationRow] = []
    photos_list: list[PhotoRow] = []
    source_geometry_present = 0
    source_geometry_absent = 0
    direct_desordre_photos = 0
    for doc in _sorted_documents(
        source_documents.get("Desordre", ()), id_field="_id", context="Desordre"
    ):
        raw_id = doc.get("_id")
        context = f"Desordre {raw_id}"
        desordre_id = couchdb_id_to_uuid(raw_id, context=f"{context}._id")
        geometry_wkt, geometry_kind, warning = desordre_geometry_from_positions(
            doc.get("positionDebut"), doc.get("positionFin"), desordre_id=raw_id
        )
        if warning:
            warnings.append(warning)
        if doc.get("geometry"):
            source_geometry_present += 1
        else:
            source_geometry_absent += 1
        direct_desordre = doc.get("photos") or []
        if not isinstance(direct_desordre, list):
            raise CoreMigrationError(f"{context}: photos directes invalides")
        direct_desordre_photos += len(direct_desordre)
        desordres_list.append(
            DesordreRow(
                id=desordre_id,
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

        raw_observations = _embedded_items(doc, "observations", context)
        for observation in _sorted_documents(
            raw_observations, id_field="id", context=f"{context}.Observation"
        ):
            raw_observation_id = observation.get("id")
            observation_context = f"Observation {raw_observation_id}"
            observation_id = couchdb_id_to_uuid(
                raw_observation_id, context=f"{observation_context}.id"
            )
            observations_list.append(
                ObservationRow(
                    id=observation_id,
                    desordre_id=desordre_id,
                    designation=_optional_text(
                        observation, "designation", observation_context
                    ),
                    date=_optional_date(observation, "date", observation_context),
                    evolution=_optional_text(
                        observation, "evolution", observation_context
                    ),
                    valid=_required_bool(observation, "valid", observation_context),
                )
            )
            raw_photos = _embedded_items(
                observation, "photos", observation_context
            )
            for photo in _sorted_documents(
                raw_photos, id_field="id", context=f"{observation_context}.Photo"
            ):
                raw_photo_id = photo.get("id")
                photo_context = f"Photo {raw_photo_id}"
                photos_list.append(
                    PhotoRow(
                        id=couchdb_id_to_uuid(
                            raw_photo_id, context=f"{photo_context}.id"
                        ),
                        observation_id=observation_id,
                        chemin_source=_required_text(photo, "chemin", photo_context),
                        date=_optional_date(photo, "date", photo_context),
                        designation=_optional_text(
                            photo, "designation", photo_context
                        ),
                        valid=_required_bool(photo, "valid", photo_context),
                    )
                )

    desordres = tuple(desordres_list)
    links = tuple(links_list)
    observations = tuple(sorted(observations_list, key=lambda row: row.id.int))
    photos = tuple(sorted(photos_list, key=lambda row: row.id.int))
    _ensure_unique_ids(desordres, "desordre")
    _ensure_unique_ids(observations, "observation")
    _ensure_unique_ids(photos, "photo")
    if len(links) != len({(row.desordre_id, row.troncon_id) for row in links}):
        raise CoreMigrationError("Liaisons source desordre/troncon dupliquées")

    if direct_troncon_photos:
        warnings.append(
            f"{direct_troncon_photos} photo(s) directement rattachée(s) aux "
            "tronçons ignorée(s) conformément au périmètre"
        )
    if direct_desordre_photos:
        warnings.append(
            f"{direct_desordre_photos} photo(s) directement rattachée(s) aux "
            "désordres ignorée(s) conformément au périmètre"
        )

    return PreparedCoreMigration(
        systemes=systemes,
        digues=digues,
        troncons=troncons,
        desordres=desordres,
        links=links,
        observations=observations,
        photos=photos,
        digues_without_system=digues_without_system,
        desordre_source_geometry_present=source_geometry_present,
        desordre_source_geometry_absent=source_geometry_absent,
        ignored_direct_troncon_photos=direct_troncon_photos,
        warnings=tuple(warnings),
    )


INSERT_STATEMENTS = {
    "systeme_endiguement": """
        INSERT INTO public.systeme_endiguement (id, libelle, valid)
        VALUES (%s, %s, %s)
    """,
    "digue": """
        INSERT INTO public.digue (id, systeme_endiguement_id, libelle, valid)
        VALUES (%s, %s, %s, %s)
    """,
    "troncon": """
        INSERT INTO public.troncon (id, digue_id, libelle, geometry, valid)
        VALUES (%s, %s, %s, ST_GeomFromText(%s, 3950), %s)
    """,
    "desordre": """
        INSERT INTO public.desordre
            (id, designation, commentaire, date_debut, date_fin, geometry, valid)
        VALUES (%s, %s, %s, %s, %s, ST_GeomFromText(%s, 3950), %s)
    """,
    "link_desordre_troncon": """
        INSERT INTO public.link_desordre_troncon (desordre_id, troncon_id)
        VALUES (%s, %s)
    """,
    "observation": """
        INSERT INTO public.observation
            (id, desordre_id, designation, date, evolution, valid)
        VALUES (%s, %s, %s, %s, %s, %s)
    """,
    "photo": """
        INSERT INTO public.photo
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


def _insert_prepared_core(cursor: Any, prepared: PreparedCoreMigration) -> None:
    batches = (
        (
            "systeme_endiguement",
            [(row.id, row.libelle, row.valid) for row in prepared.systemes],
        ),
        (
            "digue",
            [
                (row.id, row.systeme_endiguement_id, row.libelle, row.valid)
                for row in prepared.digues
            ],
        ),
        (
            "troncon",
            [
                (row.id, row.digue_id, row.libelle, row.geometry_wkt, row.valid)
                for row in prepared.troncons
            ],
        ),
        (
            "desordre",
            [
                (
                    row.id,
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
            "link_desordre_troncon",
            [(row.desordre_id, row.troncon_id) for row in prepared.links],
        ),
        (
            "observation",
            [
                (
                    row.id,
                    row.desordre_id,
                    row.designation,
                    row.date,
                    row.evolution,
                    row.valid,
                )
                for row in prepared.observations
            ],
        ),
        (
            "photo",
            [
                (
                    row.id,
                    row.observation_id,
                    row.chemin_source,
                    row.date,
                    row.designation,
                    row.valid,
                )
                for row in prepared.photos
            ],
        ),
    )
    for table, rows in batches:
        if rows:
            cursor.executemany(INSERT_STATEMENTS[table], rows)


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
) -> CoreValidationResult:
    """Insère et valide tout le noyau dans une transaction PostgreSQL unique."""

    selected = config or PostgreSQLConfig.from_env()
    connect = connector or _default_connector()
    try:
        with connect(**selected.connect_kwargs(autocommit=False)) as connection:
            with connection.cursor() as cursor:
                ensure_target_empty(cursor)
                _insert_prepared_core(cursor, prepared)
                return validate_core_migration(
                    cursor,
                    expected_counts=prepared.expected_counts,
                    expected_desordre_geometries=prepared.desordre_geometry_counts,
                )
    except (CoreMigrationError, TargetNotEmptyError):
        raise
    except Exception as exc:
        error = selected.redact_secrets(str(exc))
        raise CoreMigrationError(f"Migration PostgreSQL annulée : {error}") from exc


def fetch_core_documents(client: CouchDBClient) -> dict[str, list[dict[str, Any]]]:
    """Lit uniquement les quatre classes top-level du noyau."""

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
    documents = fetch_core_documents(client)
    prepared = prepare_core_migration(documents)
    validation = execute_core_migration(
        prepared,
        target_config,
        connector=connector,
    )
    return CoreMigrationReport(prepared=prepared, validation=validation)
