"""Overrides explicitement propres à un jeu de données CouchDB.

Ce module est la seule couche autorisée à connaître des UUID de la base auditée.
Les transformations génériques ne dépendent ni de ces UUID, ni des désignations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class SourceMigrationOverrides:
    """Décisions métier validées pour une base source nommée."""

    amenagement_type_by_id: Mapping[str, str] = field(default_factory=dict)
    vegetation_geometry_source_by_id: Mapping[str, str] = field(default_factory=dict)


_CABBALR_AMENAGEMENT_TYPES = MappingProxyType(
    {
        "496d26f14278405a4172bf66ec000321": "ZEC",
        "496d26f14278405a4172bf66ec0110bd": "ZEC",
        "599f219cafdeeac6ddead74f3008e5a1": "ZEC",
        "bb404c686144992ff4ecd939ea005d75": "ZEC",
        "d6d8083f9cac3e3037fc935f0900568c": "ZEC",
        "f5e5abcf38c36e27afd735570e039ade": "ZEC",
    }
)

_CABBALR_VEGETATION_GEOMETRY_SOURCES = MappingProxyType(
    {
        # Audit géométrique du 30 août 2026 : le Polygon principal est
        # effondré et les positions valent (0, 0), tandis que la géométrie
        # explicite est un Polygon valide. Cette décision n'est pas générique.
        "16f47274e17fbb21a37b9213fe0030a9": "explicitGeometry",
    }
)


SOURCE_OVERRIDES: Mapping[str, SourceMigrationOverrides] = MappingProxyType(
    {
        # Audit du 30 août 2026 : classement ZEC provisoire pour cette base seule.
        "cabbalr": SourceMigrationOverrides(
            amenagement_type_by_id=_CABBALR_AMENAGEMENT_TYPES,
            vegetation_geometry_source_by_id=(
                _CABBALR_VEGETATION_GEOMETRY_SOURCES
            ),
        ),
    }
)


def get_source_overrides(database: str | None) -> SourceMigrationOverrides:
    """Retourne une configuration vide pour toute base non explicitement connue."""

    if not database:
        return SourceMigrationOverrides()
    return SOURCE_OVERRIDES.get(database.casefold(), SourceMigrationOverrides())
