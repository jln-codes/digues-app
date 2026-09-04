"""Chargement optionnel d'overrides propres à une base CouchDB.

Le mécanisme est public, mais les décisions et identifiants liés à un corpus
réel restent dans un fichier de configuration privé. En l'absence de ce fichier,
le migrateur conserve son comportement générique.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from types import MappingProxyType
from typing import Mapping


SOURCE_OVERRIDES_PATH_ENV = "SIRS_SOURCE_OVERRIDES_PATH"
DEFAULT_SOURCE_OVERRIDES_PATH = (
    Path(__file__).resolve().parents[2] / "private" / "source_overrides.json"
)


class SourceOverridesConfigurationError(ValueError):
    """Le fichier optionnel d'overrides est présent mais invalide."""


@dataclass(frozen=True)
class SourceMigrationOverrides:
    """Décisions métier validées pour une base source nommée."""

    amenagement_type_by_id: Mapping[str, str] = field(default_factory=dict)
    vegetation_geometry_source_by_id: Mapping[str, str] = field(default_factory=dict)


def _string_mapping(value: object, *, field_name: str) -> Mapping[str, str]:
    if not isinstance(value, dict):
        raise SourceOverridesConfigurationError(
            f"Le champ {field_name!r} doit être un objet JSON"
        )
    if not all(
        isinstance(key, str) and isinstance(item, str)
        for key, item in value.items()
    ):
        raise SourceOverridesConfigurationError(
            f"Le champ {field_name!r} doit uniquement associer des chaînes"
        )
    return MappingProxyType(dict(value))


def source_overrides_path(path: str | Path | None = None) -> Path:
    """Résout le fichier explicite, configuré ou privé local à charger."""

    if path is not None:
        return Path(path)
    configured = os.getenv(SOURCE_OVERRIDES_PATH_ENV)
    if configured:
        return Path(configured)
    return DEFAULT_SOURCE_OVERRIDES_PATH


def load_source_overrides(
    path: str | Path | None = None,
) -> Mapping[str, SourceMigrationOverrides]:
    """Charge les overrides locaux ; retourne un registre vide s'ils sont absents."""

    resolved_path = source_overrides_path(path)
    if not resolved_path.is_file():
        return MappingProxyType({})

    try:
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceOverridesConfigurationError(
            f"Impossible de charger les overrides depuis {resolved_path}"
        ) from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("sources"), dict):
        raise SourceOverridesConfigurationError(
            "Le fichier d'overrides doit contenir un objet JSON 'sources'"
        )

    overrides: dict[str, SourceMigrationOverrides] = {}
    for database, values in payload["sources"].items():
        if not isinstance(database, str) or not isinstance(values, dict):
            raise SourceOverridesConfigurationError(
                "Chaque entrée de 'sources' doit associer un nom à un objet JSON"
            )
        overrides[database.casefold()] = SourceMigrationOverrides(
            amenagement_type_by_id=_string_mapping(
                values.get("amenagement_type_by_id", {}),
                field_name=f"sources.{database}.amenagement_type_by_id",
            ),
            vegetation_geometry_source_by_id=_string_mapping(
                values.get("vegetation_geometry_source_by_id", {}),
                field_name=f"sources.{database}.vegetation_geometry_source_by_id",
            ),
        )
    return MappingProxyType(overrides)


def get_source_overrides(
    database: str | None,
    *,
    path: str | Path | None = None,
) -> SourceMigrationOverrides:
    """Retourne une configuration vide pour toute base non configurée."""

    if not database:
        return SourceMigrationOverrides()
    return load_source_overrides(path).get(
        database.casefold(), SourceMigrationOverrides()
    )
