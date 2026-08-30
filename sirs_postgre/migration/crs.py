"""Résolution centralisée du CRS source et construction SQL PostGIS sûre."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Any

from sirs_postgre.source import CouchDBDatabaseInfo
from sirs_postgre.target import PostgreSQLConfig


TARGET_SRID = 3950
EPSG_AUTHORITY = re.compile(
    r"AUTHORITY\s*\[\s*[\"']EPSG[\"']\s*,\s*[\"'](\d+)[\"']\s*\]",
    re.IGNORECASE,
)
PROJ4_EPSG = re.compile(r"(?:\+init=)?epsg:(\d+)", re.IGNORECASE)


class CRSResolutionError(RuntimeError):
    """Le CRS source ne peut pas être déterminé sans risque."""

    def __init__(self, message: str, *, category: str) -> None:
        super().__init__(message)
        self.category = category


@dataclass(frozen=True)
class CRSInfo:
    source_srid: int
    target_srid: int = TARGET_SRID
    source: str = "$sirs"
    epsg_code: str | int | None = None
    crs_wkt: str | None = None
    proj4: str | None = None
    warnings: tuple[str, ...] = ()

    @property
    def transformation_required(self) -> bool:
        return self.source_srid != self.target_srid

    @property
    def source_label(self) -> str:
        suffix = " (fallback SIRS_SOURCE_SRID)" if self.source == "SIRS_SOURCE_SRID" else ""
        return f"EPSG:{self.source_srid}{suffix}"


def parse_srid(value: Any) -> int:
    """Accepte ``3950`` ou ``EPSG:3950`` et renvoie un entier positif."""

    if isinstance(value, bool):
        raise ValueError("un booléen n'est pas un SRID")
    if isinstance(value, int):
        srid = value
    elif isinstance(value, str):
        match = re.fullmatch(r"\s*(?:EPSG\s*:\s*)?(\d+)\s*", value, re.IGNORECASE)
        if not match:
            raise ValueError(f"format SRID illisible : {value!r}")
        srid = int(match.group(1))
    else:
        raise ValueError(f"format SRID illisible : {value!r}")
    if srid <= 0:
        raise ValueError(f"SRID invalide : {srid}")
    return srid


def _optional_fallback(value: Any = None) -> int | None:
    raw = os.getenv("SIRS_SOURCE_SRID") if value is None else value
    if raw in (None, ""):
        return None
    try:
        return parse_srid(raw)
    except ValueError as exc:
        raise CRSResolutionError(
            f"SIRS_SOURCE_SRID invalide : {exc}", category="INVALID_SOURCE_CRS"
        ) from exc


def _validate_metadata_consistency(info: CouchDBDatabaseInfo, srid: int) -> None:
    if info.crs_wkt:
        authorities = EPSG_AUTHORITY.findall(info.crs_wkt)
        if authorities and int(authorities[-1]) != srid:
            raise CRSResolutionError(
                "$sirs.crsWkt contredit $sirs.epsgCode : "
                f"EPSG:{authorities[-1]} au lieu de EPSG:{srid}",
                category="CONFLICTING_SOURCE_CRS",
            )
    if info.proj4:
        explicit = PROJ4_EPSG.search(info.proj4)
        if explicit and int(explicit.group(1)) != srid:
            raise CRSResolutionError(
                "$sirs.proj4 contredit $sirs.epsgCode : "
                f"EPSG:{explicit.group(1)} au lieu de EPSG:{srid}",
                category="CONFLICTING_SOURCE_CRS",
            )


def resolve_source_crs(
    database_info: CouchDBDatabaseInfo,
    *,
    fallback: Any = None,
) -> CRSInfo:
    """Résout le CRS global avec priorité à ``$sirs.epsgCode``.

    Une métadonnée absente ou syntaxiquement invalide autorise le fallback
    explicite. Une métadonnée valide contradictoire avec ce fallback bloque.
    """

    fallback_srid = _optional_fallback(fallback)
    metadata_srid: int | None = None
    metadata_error: ValueError | None = None
    if database_info.epsg_code not in (None, ""):
        try:
            metadata_srid = parse_srid(database_info.epsg_code)
        except ValueError as exc:
            metadata_error = exc

    if metadata_srid is not None:
        if fallback_srid is not None and fallback_srid != metadata_srid:
            raise CRSResolutionError(
                "$sirs.epsgCode et SIRS_SOURCE_SRID sont contradictoires : "
                f"EPSG:{metadata_srid} contre EPSG:{fallback_srid}",
                category="CONFLICTING_SOURCE_CRS",
            )
        _validate_metadata_consistency(database_info, metadata_srid)
        return CRSInfo(
            source_srid=metadata_srid,
            source="$sirs",
            epsg_code=database_info.epsg_code,
            crs_wkt=database_info.crs_wkt,
            proj4=database_info.proj4,
        )

    if fallback_srid is not None:
        _validate_metadata_consistency(database_info, fallback_srid)
        warning = (
            f"$sirs.epsgCode invalide ({metadata_error}); fallback explicite utilisé"
            if metadata_error
            else "$sirs.epsgCode absent ; fallback explicite utilisé"
        )
        return CRSInfo(
            source_srid=fallback_srid,
            source="SIRS_SOURCE_SRID",
            epsg_code=database_info.epsg_code,
            crs_wkt=database_info.crs_wkt,
            proj4=database_info.proj4,
            warnings=(warning,),
        )

    if metadata_error:
        raise CRSResolutionError(
            f"$sirs.epsgCode invalide et SIRS_SOURCE_SRID absent : {metadata_error}",
            category="INVALID_SOURCE_CRS",
        )
    raise CRSResolutionError(
        "$sirs.epsgCode absent et SIRS_SOURCE_SRID non configuré",
        category="MISSING_SOURCE_CRS",
    )


def validate_crs(cursor: Any, crs_info: CRSInfo) -> None:
    """Vérifie dans PostGIS que les CRS source et cible sont résolvables."""

    for role, srid in (("source", crs_info.source_srid), ("cible", crs_info.target_srid)):
        cursor.execute("SELECT srid FROM spatial_ref_sys WHERE srid = %s", (srid,))
        if cursor.fetchone() is None:
            raise CRSResolutionError(
                f"CRS {role} EPSG:{srid} absent de spatial_ref_sys",
                category="INVALID_SOURCE_CRS" if role == "source" else "CONFLICTING_SOURCE_CRS",
            )


def validate_crs_with_postgis(
    crs_info: CRSInfo,
    config: PostgreSQLConfig | None = None,
) -> None:
    """Ouvre une connexion de lecture dédiée pour les commandes de diagnostic."""

    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("Le pilote psycopg n'est pas installé") from exc
    selected = config or PostgreSQLConfig.from_env()
    with psycopg.connect(**selected.connect_kwargs(autocommit=True)) as connection:
        with connection.cursor() as cursor:
            validate_crs(cursor, crs_info)


def geometry_sql(crs_info: CRSInfo | None = None, *, placeholder: str = "%s") -> str:
    """Produit l'expression SQL unique d'assignation ou de reprojection."""

    info = crs_info or CRSInfo(source_srid=TARGET_SRID)
    source = f"ST_GeomFromText({placeholder}, {info.source_srid})"
    if info.transformation_required:
        return f"ST_Transform({source}, {info.target_srid})"
    return source


def crs_hint_is_consistent(hint: Any, crs_info: CRSInfo) -> bool:
    """Contrôle un ``crsName`` sans jamais en faire une source d'autorité."""

    if not isinstance(hint, str) or not hint.strip():
        return True
    numeric = re.search(r"EPSG\s*:\s*(\d+)", hint, re.IGNORECASE)
    if numeric:
        return int(numeric.group(1)) == crs_info.source_srid
    label = re.sub(r"^\s*EPSG\s*:\s*", "", hint, flags=re.IGNORECASE).strip()
    if label and crs_info.crs_wkt:
        compact_label = re.sub(r"\s+", " ", label).casefold()
        compact_wkt = re.sub(r"[_\s]+", " ", crs_info.crs_wkt).casefold()
        return compact_label in compact_wkt
    # Un indice non résolvable ne peut ni définir ni contredire le CRS global.
    return True
