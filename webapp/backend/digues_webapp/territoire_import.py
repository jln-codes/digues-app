"""Lecture SIG sécurisée du territoire administratif importé."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
import re
from tempfile import TemporaryDirectory
import zipfile


TARGET_TERRITORY_SRID = 3950

ACCEPTED_TERRITORY_CONTENT_TYPES = {
    "application/geopackage+sqlite3",
    "application/octet-stream",
    "application/zip",
}
MAX_TERRITORY_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_TERRITORY_ZIP_ENTRIES = 32
MAX_TERRITORY_ZIP_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_TERRITORY_ZIP_COMPRESSION_RATIO = 100

_SHAPEFILE_REQUIRED_EXTENSIONS = {".shp", ".shx", ".dbf", ".prj"}
_SHAPEFILE_EXTRACTED_EXTENSIONS = {
    ".shp",
    ".shx",
    ".dbf",
    ".prj",
    ".cpg",
    ".qix",
    ".sbn",
    ".sbx",
}
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")


class TerritoireImportError(ValueError):
    """L'upload SIG ne respecte pas le contrat d'import."""

    def __init__(
        self,
        message: str,
        *,
        available_layers: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.available_layers = available_layers or []


class TerritoireImportConfigurationError(RuntimeError):
    """Le runtime webapp ne fournit pas le moteur SIG requis."""


@dataclass(frozen=True)
class ImportedTerritoireGeometry:
    """Résultat validé côté OGR, prêt à être transmis à PostGIS."""

    wkb: bytes
    source_layer: str
    source_crs: str
    target_srid: int = TARGET_TERRITORY_SRID


def validate_upload_metadata(filename: str | None, content_type: str | None) -> str:
    """Valide l'enveloppe HTTP sans faire confiance au type MIME seul."""

    if not filename or not filename.strip():
        raise TerritoireImportError("L'en-tête X-Filename est obligatoire.")
    normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized_type not in ACCEPTED_TERRITORY_CONTENT_TYPES:
        raise TerritoireImportError("Type de contenu d'import non pris en charge.")
    suffix = Path(filename.strip()).suffix.lower()
    if suffix not in {".gpkg", ".zip"}:
        raise TerritoireImportError(
            "Extension de fichier non prise en charge. Utiliser .gpkg ou .zip."
        )
    return suffix


def import_territoire_geometry(
    payload: bytes,
    *,
    filename: str,
    content_type: str,
    layer_name: str | None = None,
) -> ImportedTerritoireGeometry:
    """Lit, valide et reprojette un GPKG ou ZIP Shapefile vers EPSG:3950."""

    if not payload:
        raise TerritoireImportError("Le fichier importé est vide.")
    if len(payload) > MAX_TERRITORY_UPLOAD_BYTES:
        raise TerritoireImportError("Le fichier importé dépasse la taille maximale.")
    suffix = validate_upload_metadata(filename, content_type)
    selected_layer = layer_name.strip() if layer_name is not None else None
    if selected_layer == "":
        raise TerritoireImportError("Le nom de couche fourni est vide.")

    with TemporaryDirectory(prefix="digues-territoire-") as directory:
        root = Path(directory)
        if suffix == ".gpkg":
            source_path = root / "upload.gpkg"
            source_path.write_bytes(payload)
            return _read_ogr_dataset(
                source_path,
                allowed_drivers=["GPKG"],
                layer_name=selected_layer,
            )

        source_path = _extract_single_shapefile_zip(payload, root)
        return _read_ogr_dataset(
            source_path,
            allowed_drivers=["ESRI Shapefile"],
            layer_name=selected_layer,
        )


def _safe_zip_path(name: str) -> PurePosixPath:
    if not name or "\x00" in name or "\\" in name:
        raise TerritoireImportError("Archive ZIP contenant un chemin invalide.")
    if name.startswith("/") or name.startswith("\\") or _WINDOWS_DRIVE_RE.match(name):
        raise TerritoireImportError("Archive ZIP contenant un chemin absolu.")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise TerritoireImportError("Archive ZIP contenant une traversée de chemin.")
    return path


def _validate_zip_members(infos: list[zipfile.ZipInfo]) -> None:
    if len(infos) > MAX_TERRITORY_ZIP_ENTRIES:
        raise TerritoireImportError("Archive ZIP contenant trop d'entrées.")
    total_uncompressed = 0
    for info in infos:
        _safe_zip_path(info.filename)
        if info.flag_bits & 0x1:
            raise TerritoireImportError("Archive ZIP chiffrée refusée.")
        if info.is_dir():
            continue
        total_uncompressed += info.file_size
        if total_uncompressed > MAX_TERRITORY_ZIP_UNCOMPRESSED_BYTES:
            raise TerritoireImportError(
                "Archive ZIP dépassant la taille décompressée maximale."
            )
        if info.file_size and info.compress_size == 0:
            raise TerritoireImportError("Archive ZIP au ratio de compression invalide.")
        if info.compress_size:
            ratio = info.file_size / info.compress_size
            if ratio > MAX_TERRITORY_ZIP_COMPRESSION_RATIO:
                raise TerritoireImportError(
                    "Archive ZIP refusée par limite de ratio de compression."
                )


def _extract_single_shapefile_zip(payload: bytes, root: Path) -> Path:
    try:
        archive = zipfile.ZipFile(BytesIO(payload))
    except zipfile.BadZipFile as exc:
        raise TerritoireImportError("Archive ZIP illisible.") from exc
    with archive:
        infos = archive.infolist()
        _validate_zip_members(infos)
        files = [info for info in infos if not info.is_dir()]
        shapefiles = [
            info
            for info in files
            if PurePosixPath(info.filename).suffix.lower() == ".shp"
        ]
        if len(shapefiles) != 1:
            raise TerritoireImportError(
                "Archive ZIP ambiguë : elle doit contenir exactement un .shp."
            )

        shp_path = _safe_zip_path(shapefiles[0].filename)
        shp_directory = shp_path.parent
        shp_stem = shp_path.stem.lower()
        sibling_extensions = {
            PurePosixPath(info.filename).suffix.lower()
            for info in files
            if _safe_zip_path(info.filename).parent == shp_directory
            and PurePosixPath(info.filename).stem.lower() == shp_stem
        }
        missing = sorted(_SHAPEFILE_REQUIRED_EXTENSIONS - sibling_extensions)
        if missing:
            raise TerritoireImportError(
                "Archive ZIP Shapefile incomplète : fichiers manquants "
                + ", ".join(missing)
                + "."
            )

        for info in files:
            path = _safe_zip_path(info.filename)
            if path.parent != shp_directory or path.stem.lower() != shp_stem:
                continue
            if path.suffix.lower() not in _SHAPEFILE_EXTRACTED_EXTENSIONS:
                continue
            destination = root.joinpath(*path.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source:
                destination.write_bytes(source.read())

    return root.joinpath(*shp_path.parts)


def _require_gdal():
    try:
        from osgeo import gdal, ogr, osr
    except ModuleNotFoundError as exc:
        raise TerritoireImportConfigurationError(
            "GDAL/OGR est requis pour importer un territoire administratif."
        ) from exc
    gdal.UseExceptions()
    return gdal, ogr, osr


def _read_ogr_dataset(
    source_path: Path,
    *,
    allowed_drivers: list[str],
    layer_name: str | None,
) -> ImportedTerritoireGeometry:
    gdal, ogr, osr = _require_gdal()
    try:
        dataset = gdal.OpenEx(
            str(source_path),
            gdal.OF_VECTOR | gdal.OF_READONLY,
            allowed_drivers=allowed_drivers,
        )
    except RuntimeError as exc:
        raise TerritoireImportError("Fichier SIG illisible par GDAL/OGR.") from exc
    if dataset is None:
        raise TerritoireImportError("Fichier SIG illisible par GDAL/OGR.")
    try:
        layer = _select_layer(dataset, ogr, layer_name)
        return _read_polygon_feature(layer, ogr, osr)
    finally:
        dataset = None


def _layer_has_geometry(layer: object, ogr: object) -> bool:
    definition = layer.GetLayerDefn()
    if definition.GetGeomFieldCount() <= 0:
        return False
    return layer.GetGeomType() != ogr.wkbNone


def _select_layer(dataset: object, ogr: object, layer_name: str | None) -> object:
    layers = [dataset.GetLayerByIndex(index) for index in range(dataset.GetLayerCount())]
    geometric_layers = [layer for layer in layers if layer and _layer_has_geometry(layer, ogr)]
    available = [layer.GetName() for layer in geometric_layers]
    if layer_name is not None:
        for layer in geometric_layers:
            if layer.GetName() == layer_name:
                return layer
        raise TerritoireImportError(
            f"Couche GeoPackage/Shapefile inexistante : {layer_name}.",
            available_layers=available,
        )
    if not geometric_layers:
        raise TerritoireImportError("Le fichier SIG ne contient aucune couche géométrique.")
    if len(geometric_layers) > 1:
        raise TerritoireImportError(
            "Le fichier SIG contient plusieurs couches géométriques ; "
            "le paramètre layer est obligatoire.",
            available_layers=available,
        )
    return geometric_layers[0]


def _read_polygon_feature(layer: object, ogr: object, osr: object) -> ImportedTerritoireGeometry:
    source_srs = layer.GetSpatialRef()
    srs_name = (source_srs.GetName() if source_srs is not None else "") or ""
    srs_datum = (
        source_srs.GetAttrValue("DATUM") if source_srs is not None else ""
    ) or ""
    if (
        source_srs is None
        or not source_srs.ExportToWkt()
        or not (source_srs.IsProjected() or source_srs.IsGeographic())
        or srs_name.lower().startswith("undefined")
        or srs_datum.lower().startswith("unknown")
    ):
        raise TerritoireImportError("CRS source absent ou inexploitable.")
    try:
        source_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        if source_srs.Validate() != 0:
            raise TerritoireImportError("CRS source absent ou inexploitable.")
        target_srs = osr.SpatialReference()
        if target_srs.ImportFromEPSG(TARGET_TERRITORY_SRID) != 0:
            raise TerritoireImportConfigurationError(
                f"CRS cible EPSG:{TARGET_TERRITORY_SRID} indisponible."
            )
        target_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        transform = osr.CoordinateTransformation(source_srs, target_srs)
    except TerritoireImportError:
        raise
    except Exception as exc:
        raise TerritoireImportError("Transformation CRS impossible.") from exc

    layer.ResetReading()
    feature_count = 0
    geometry = None
    for feature in layer:
        feature_count += 1
        if feature_count > 1:
            raise TerritoireImportError(
                "Le jeu de données contient plusieurs entités géographiques."
            )
        geometry_ref = feature.GetGeometryRef()
        if geometry_ref is None:
            raise TerritoireImportError("L'entité ne contient aucune géométrie.")
        geometry = geometry_ref.Clone()

    if feature_count == 0:
        raise TerritoireImportError("Le jeu de données ne contient aucune entité.")
    if geometry is None:
        raise TerritoireImportError("L'entité ne contient aucune géométrie.")
    if geometry.GetGeometryType() != ogr.wkbPolygon:
        raise TerritoireImportError("La géométrie importée doit être un Polygon 2D.")
    if geometry.IsEmpty():
        raise TerritoireImportError("La géométrie importée est vide.")
    if not geometry.IsValid():
        raise TerritoireImportError("La géométrie importée est invalide.")

    try:
        if geometry.Transform(transform) != 0:
            raise TerritoireImportError("Reprojection vers le CRS cible impossible.")
    except TerritoireImportError:
        raise
    except Exception as exc:
        raise TerritoireImportError("Reprojection vers le CRS cible impossible.") from exc
    if geometry.GetGeometryType() != ogr.wkbPolygon:
        raise TerritoireImportError("La reprojection a produit un type non Polygon.")
    if geometry.IsEmpty() or not geometry.IsValid():
        raise TerritoireImportError("La géométrie reprojetée est invalide ou vide.")

    authority = source_srs.GetAuthorityName(None)
    code = source_srs.GetAuthorityCode(None)
    source_crs = f"{authority}:{code}" if authority and code else source_srs.ExportToWkt()
    return ImportedTerritoireGeometry(
        wkb=bytes(geometry.ExportToWkb()),
        source_layer=layer.GetName(),
        source_crs=source_crs,
    )
