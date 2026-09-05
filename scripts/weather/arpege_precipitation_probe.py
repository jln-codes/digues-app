#!/usr/bin/env python3
"""Compare ARPEGE precipitation coverages on one small common space-time subset."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import re
import struct
import sys
from tempfile import TemporaryDirectory
from typing import Iterable
from xml.etree import ElementTree

import requests
from dotenv import load_dotenv
from osgeo import gdal, osr


API_KEY_ENV = "METEOFRANCE_API_KEY"
WCS_ENDPOINT = (
    "https://public-api.meteofrance.fr/public/arpege/1.0/wcs/"
    "MF-NWP-GLOBAL-ARPEGE-01-EUROPE-WCS"
)
PRODUCT = "TOTAL_WATER_PRECIPITATION__GROUND_OR_WATER_SURFACE"
PERIODS = ("P1D", "PT1H", "PT3H", "PT6H")
DEFAULT_BBOX = (2.45, 50.40, 2.75, 50.60)
HTTP_TIMEOUT = (15, 120)
MAX_XML_BYTES = 25 * 1024 * 1024
MAX_TIFF_BYTES = 50 * 1024 * 1024
ROOT_DIRECTORY = Path(__file__).resolve().parents[2]
CONFIG_ENV_PATH = ROOT_DIRECTORY / "config.env"

gdal.UseExceptions()


class ProbeError(RuntimeError):
    """Expected failure reported without exposing credentials."""


@dataclass(frozen=True)
class Coverage:
    coverage_id: str
    run: datetime
    period: str


@dataclass(frozen=True)
class CoverageDescription:
    coverage_id: str
    times: tuple[datetime, ...]
    unit: str | None
    begin: datetime | None
    end: datetime | None


@dataclass(frozen=True)
class RasterSummary:
    product: str
    coverage_id: str
    width: int
    height: int
    crs: str
    bounds: tuple[float, float, float, float]
    resolution: tuple[float, float]
    data_type: str
    nodata: float | None
    minimum: float
    maximum: float
    mean: float
    center: float
    describe_unit: str | None
    dataset_tags: dict[str, dict[str, str]]
    band_tags: dict[str, dict[str, str]]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_utc(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_coverage_id(coverage_id: str) -> Coverage | None:
    prefix = f"{PRODUCT}___"
    if not coverage_id.startswith(prefix):
        return None
    remainder = coverage_id[len(prefix) :]
    try:
        run_text, period = remainder.rsplit("_", 1)
    except ValueError:
        return None
    if not re.fullmatch(r"P(?:\d+D|T\d+H)", period):
        return None
    run_match = re.fullmatch(
        r"(\d{4}-\d{2}-\d{2})T(\d{2})[.:](\d{2})[.:](\d{2})Z",
        run_text,
    )
    if not run_match:
        return None
    run = datetime.strptime(
        "".join(run_match.groups()), "%Y-%m-%d%H%M%S"
    ).replace(tzinfo=timezone.utc)
    return Coverage(coverage_id=coverage_id, run=run, period=period)


def parse_capabilities(payload: bytes) -> list[Coverage]:
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise ProbeError(f"GetCapabilities XML invalide : {exc}") from exc
    coverages: list[Coverage] = []
    for element in root.iter():
        if _local_name(element.tag) != "CoverageId" or not element.text:
            continue
        parsed = parse_coverage_id(element.text.strip())
        if parsed:
            coverages.append(parsed)
    if not coverages:
        raise ProbeError(f"Aucun coverage trouvé pour {PRODUCT}.")
    return coverages


def select_latest_complete_run(
    coverages: Iterable[Coverage], periods: Iterable[str] = PERIODS
) -> dict[str, Coverage]:
    required = tuple(periods)
    by_run: dict[datetime, dict[str, Coverage]] = {}
    for coverage in coverages:
        by_run.setdefault(coverage.run, {})[coverage.period] = coverage
    complete_runs = [
        run for run, values in by_run.items() if all(period in values for period in required)
    ]
    if not complete_runs:
        raise ProbeError(
            "Aucun run ARPEGE ne contient tous les produits requis : "
            + ", ".join(required)
        )
    selected = by_run[max(complete_runs)]
    return {period: selected[period] for period in required}


def _first_text(root: ElementTree.Element, name: str) -> str | None:
    for element in root.iter():
        if _local_name(element.tag) == name and element.text and element.text.strip():
            return element.text.strip()
    return None


def parse_description(payload: bytes, run: datetime) -> CoverageDescription:
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise ProbeError(f"DescribeCoverage XML invalide : {exc}") from exc
    coverage_id = _first_text(root, "CoverageId")
    if not coverage_id:
        raise ProbeError("DescribeCoverage ne contient aucun CoverageId.")

    coefficients: list[int] = []
    for axis in root.iter():
        if _local_name(axis.tag) != "GeneralGridAxis":
            continue
        axis_name = _first_text(axis, "gridAxesSpanned")
        if axis_name != "time":
            continue
        values = _first_text(axis, "coefficients") or ""
        try:
            coefficients = [int(float(value)) for value in values.split()]
        except ValueError as exc:
            raise ProbeError("Coefficients temporels ARPEGE invalides.") from exc
        break
    if not coefficients:
        raise ProbeError(
            f"Aucune échéance discrète trouvée dans DescribeCoverage pour {coverage_id}."
        )

    begin_text = _first_text(root, "beginPosition")
    end_text = _first_text(root, "endPosition")
    unit = None
    for element in root.iter():
        if _local_name(element.tag) == "uom":
            unit = element.attrib.get("code")
            if unit:
                break
    return CoverageDescription(
        coverage_id=coverage_id,
        times=tuple(run + timedelta(seconds=value) for value in coefficients),
        unit=unit,
        begin=_parse_utc(begin_text) if begin_text else None,
        end=_parse_utc(end_text) if end_text else None,
    )


def select_common_time(descriptions: Iterable[CoverageDescription]) -> datetime:
    values = list(descriptions)
    if not values:
        raise ProbeError("Aucune description de coverage disponible.")
    common = set(values[0].times)
    for description in values[1:]:
        common.intersection_update(description.times)
    if not common:
        raise ProbeError("Aucune échéance valide commune aux produits demandés.")
    return min(common)


class WcsClient:
    def __init__(self, api_key: str, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()
        self._headers = {"apikey": api_key}

    def _get(self, operation: str, params: list[tuple[str, str]], *, stream: bool):
        try:
            response = self._session.get(
                f"{WCS_ENDPOINT}/{operation}",
                params=params,
                headers=self._headers,
                timeout=HTTP_TIMEOUT,
                stream=stream,
            )
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            status = getattr(exc.response, "status_code", None)
            suffix = f" (HTTP {status})" if status else ""
            raise ProbeError(f"Échec de {operation}{suffix}.") from exc

    def _xml(self, operation: str, params: list[tuple[str, str]]) -> bytes:
        response = self._get(operation, params, stream=False)
        payload = response.content
        if len(payload) > MAX_XML_BYTES:
            raise ProbeError(f"Réponse {operation} trop volumineuse.")
        return payload

    def get_capabilities(self) -> bytes:
        return self._xml(
            "GetCapabilities",
            [("service", "WCS"), ("version", "2.0.1"), ("language", "fre")],
        )

    def describe_coverage(self, coverage_id: str) -> bytes:
        return self._xml(
            "DescribeCoverage",
            [
                ("service", "WCS"),
                ("version", "2.0.1"),
                ("coverageID", coverage_id),
            ],
        )

    def download_coverage(
        self,
        coverage_id: str,
        valid_time: datetime,
        bbox: tuple[float, float, float, float],
        destination: Path,
    ) -> None:
        west, south, east, north = bbox
        params = [
            ("service", "WCS"),
            ("version", "2.0.1"),
            ("coverageid", coverage_id),
            ("subset", f"long({west},{east})"),
            ("subset", f"lat({south},{north})"),
            ("subset", f"time({_format_utc(valid_time)})"),
            ("format", "image/tiff"),
        ]
        response = self._get("GetCoverage", params, stream=True)
        size = 0
        with destination.open("wb") as output:
            for chunk in response.iter_content(64 * 1024):
                if not chunk:
                    continue
                size += len(chunk)
                if size > MAX_TIFF_BYTES:
                    raise ProbeError("GeoTIFF ARPEGE trop volumineux pour cette sonde.")
                output.write(chunk)
        if size == 0:
            raise ProbeError("GetCoverage a retourné un fichier vide.")


def _metadata_by_domain(item) -> dict[str, dict[str, str]]:
    domains = item.GetMetadataDomainList() or [""]
    result: dict[str, dict[str, str]] = {}
    for domain in domains:
        metadata = item.GetMetadata(domain) or {}
        if metadata:
            result[domain or "default"] = dict(sorted(metadata.items()))
    return result


def _read_pixel(band, x: int, y: int) -> float:
    formats = {
        gdal.GDT_Byte: "B",
        gdal.GDT_UInt16: "H",
        gdal.GDT_Int16: "h",
        gdal.GDT_UInt32: "I",
        gdal.GDT_Int32: "i",
        gdal.GDT_Float32: "f",
        gdal.GDT_Float64: "d",
    }
    if hasattr(gdal, "GDT_UInt64"):
        formats[gdal.GDT_UInt64] = "Q"
        formats[gdal.GDT_Int64] = "q"
    value_format = formats.get(band.DataType)
    if not value_format:
        raise ProbeError(f"Type raster non pris en charge : {band.DataType}.")
    payload = band.ReadRaster(x, y, 1, 1, buf_type=band.DataType)
    if not payload:
        raise ProbeError("Lecture du pixel central impossible.")
    return float(struct.unpack(f"={value_format}", payload)[0])


def analyze_raster(
    path: Path,
    product: str,
    coverage_id: str,
    describe_unit: str | None,
) -> RasterSummary:
    dataset = gdal.Open(str(path), gdal.GA_ReadOnly)
    if dataset is None or dataset.RasterCount != 1:
        raise ProbeError(f"GeoTIFF invalide ou multibande pour {product}.")
    band = dataset.GetRasterBand(1)
    statistics = band.ComputeStatistics(False)
    if not statistics or any(not math.isfinite(value) for value in statistics[:3]):
        raise ProbeError(f"Statistiques raster invalides pour {product}.")
    transform = dataset.GetGeoTransform()
    corners = [
        gdal.ApplyGeoTransform(transform, x, y)
        for x, y in (
            (0, 0),
            (dataset.RasterXSize, 0),
            (0, dataset.RasterYSize),
            (dataset.RasterXSize, dataset.RasterYSize),
        )
    ]
    xs = [point[0] for point in corners]
    ys = [point[1] for point in corners]
    spatial_reference = osr.SpatialReference(wkt=dataset.GetProjectionRef())
    authority = spatial_reference.GetAuthorityName(None)
    authority_code = spatial_reference.GetAuthorityCode(None)
    crs = (
        f"{authority}:{authority_code}"
        if authority and authority_code
        else spatial_reference.GetName() or dataset.GetProjectionRef() or "inconnu"
    )
    return RasterSummary(
        product=product,
        coverage_id=coverage_id,
        width=dataset.RasterXSize,
        height=dataset.RasterYSize,
        crs=crs,
        bounds=(min(xs), min(ys), max(xs), max(ys)),
        resolution=(abs(transform[1]), abs(transform[5])),
        data_type=gdal.GetDataTypeName(band.DataType),
        nodata=band.GetNoDataValue(),
        minimum=float(statistics[0]),
        maximum=float(statistics[1]),
        mean=float(statistics[2]),
        center=_read_pixel(
            band, dataset.RasterXSize // 2, dataset.RasterYSize // 2
        ),
        describe_unit=describe_unit,
        dataset_tags=_metadata_by_domain(dataset),
        band_tags=_metadata_by_domain(band),
    )


def _parse_bbox(value: str) -> tuple[float, float, float, float]:
    try:
        west, south, east, north = (float(part) for part in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "La bbox doit être west,south,east,north."
        ) from exc
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise argparse.ArgumentTypeError("BBox géographique invalide.")
    return west, south, east, north


def _grib_tag(summary: RasterSummary, name: str) -> str:
    for metadata in summary.band_tags.values():
        if name in metadata:
            return metadata[name]
    return ""


def _print_table(summaries: list[RasterSummary]) -> None:
    headers = ("produit", "centre", "min", "max", "unité", "ref time", "valid time")
    rows = [headers]
    for summary in summaries:
        rows.append(
            (
                summary.product,
                f"{summary.center:.10g}",
                f"{summary.minimum:.10g}",
                f"{summary.maximum:.10g}",
                _grib_tag(summary, "GRIB_UNIT") or summary.describe_unit or "",
                _grib_tag(summary, "GRIB_REF_TIME"),
                _grib_tag(summary, "GRIB_VALID_TIME"),
            )
        )
    widths = [max(len(row[index]) for row in rows) for index in range(len(headers))]
    for row_index, row in enumerate(rows):
        print(" | ".join(value.ljust(widths[index]) for index, value in enumerate(row)))
        if row_index == 0:
            print("-+-".join("-" * width for width in widths))


def _print_relationships(summaries: list[RasterSummary]) -> None:
    by_product = {summary.product: summary for summary in summaries}
    ordered = [by_product[period].center for period in ("PT1H", "PT3H", "PT6H", "P1D")]
    monotonic = all(left <= right for left, right in zip(ordered, ordered[1:]))
    print("\nRelations au pixel central :")
    print(f"- PT1H <= PT3H <= PT6H <= P1D : {'oui' if monotonic else 'non'}")
    baseline = by_product["PT1H"].center
    for period in ("PT3H", "PT6H", "P1D"):
        value = by_product[period].center
        ratio = value / baseline if baseline else math.nan
        print(f"- {period} / PT1H : {ratio:.6g}")
    print(
        "Ces rapports sont des observations, pas une preuve d'unité : "
        "les métadonnées DescribeCoverage et GRIB doivent être comparées."
    )


def run_probe(
    client: WcsClient,
    bbox: tuple[float, float, float, float],
    *,
    json_output: Path | None = None,
    temporal_samples: int = 0,
) -> list[RasterSummary]:
    selected = select_latest_complete_run(parse_capabilities(client.get_capabilities()))
    run = next(iter(selected.values())).run
    print(f"Run choisi : {_format_utc(run)}")
    for period in PERIODS:
        print(f"- {period}: {selected[period].coverage_id}")

    descriptions = {
        period: parse_description(
            client.describe_coverage(coverage.coverage_id), coverage.run
        )
        for period, coverage in selected.items()
    }
    valid_time = select_common_time(descriptions.values())
    lead_hours = (valid_time - run).total_seconds() / 3600
    print(f"Heure valide commune : {_format_utc(valid_time)} (H+{lead_hours:g})")
    print(f"BBox : {bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}")

    summaries: list[RasterSummary] = []
    with TemporaryDirectory(prefix="sirs-arpege-probe-") as directory:
        temporary_directory = Path(directory)
        for period in PERIODS:
            coverage = selected[period]
            destination = temporary_directory / f"{period}.tif"
            client.download_coverage(coverage.coverage_id, valid_time, bbox, destination)
            summaries.append(
                analyze_raster(
                    destination,
                    period,
                    coverage.coverage_id,
                    descriptions[period].unit,
                )
            )

        if temporal_samples:
            candidates = [
                value
                for value in descriptions["P1D"].times
                if value > valid_time
            ][:temporal_samples]
            print("\nÉchantillons temporels P1D supplémentaires :")
            for index, sample_time in enumerate(candidates, start=1):
                destination = temporary_directory / f"P1D-temporal-{index}.tif"
                coverage = selected["P1D"]
                client.download_coverage(
                    coverage.coverage_id, sample_time, bbox, destination
                )
                sample = analyze_raster(
                    destination,
                    "P1D",
                    coverage.coverage_id,
                    descriptions["P1D"].unit,
                )
                print(f"- {_format_utc(sample_time)} : centre={sample.center:.10g}")

    print()
    _print_table(summaries)
    _print_relationships(summaries)
    print("\nMétadonnées complètes :")
    print(json.dumps([asdict(summary) for summary in summaries], indent=2, ensure_ascii=False))
    if json_output:
        json_output.write_text(
            json.dumps([asdict(summary) for summary in summaries], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Rapport JSON écrit dans {json_output}")
    return summaries


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare P1D, PT1H, PT3H et PT6H sur une petite bbox ARPEGE."
    )
    parser.add_argument(
        "--bbox",
        type=_parse_bbox,
        default=DEFAULT_BBOX,
        metavar="WEST,SOUTH,EAST,NORTH",
        help="Petite bbox WGS84 (défaut : centre approximatif CABBALR).",
    )
    parser.add_argument("--json-output", type=Path, help="Écrire aussi le détail en JSON.")
    parser.add_argument(
        "--temporal-samples",
        type=int,
        default=0,
        choices=range(0, 4),
        metavar="0..3",
        help="Télécharger jusqu'à trois échéances P1D suivantes (défaut : 0).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    load_dotenv(CONFIG_ENV_PATH, override=False)
    api_key = os.getenv(API_KEY_ENV, "").strip()
    if not api_key:
        print(
            f"Erreur : définissez {API_KEY_ENV} dans l'environnement ou config.env.",
            file=sys.stderr,
        )
        return 2
    try:
        run_probe(
            WcsClient(api_key),
            arguments.bbox,
            json_output=arguments.json_output,
            temporal_samples=arguments.temporal_samples,
        )
    except ProbeError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
