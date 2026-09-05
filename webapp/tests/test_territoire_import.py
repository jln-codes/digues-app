import asyncio
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
import zipfile

from dotenv import load_dotenv

from digues_webapp.app import app, read_limited_body
from digues_webapp.database import PostgreSQLConfig
from digues_webapp.territoire import (
    TERRITOIRE_INSERT_SQL,
    TERRITOIRE_UPSERT_SQL,
    TERRITOIRE_VALIDATE_WKB_SQL,
    TerritoireConflictError,
    fetch_territoire_administratif,
    replace_territoire_administratif,
)
from digues_webapp.territoire_import import (
    MAX_TERRITORY_UPLOAD_BYTES,
    MAX_TERRITORY_ZIP_ENTRIES,
    MAX_TERRITORY_ZIP_UNCOMPRESSED_BYTES,
    TARGET_TERRITORY_SRID,
    TerritoireImportError,
    _validate_zip_members,
    import_territoire_geometry,
    validate_upload_metadata,
)

try:
    sys.path.append("/usr/lib/python3/dist-packages")
    from osgeo import gdal, ogr, osr

    gdal.UseExceptions()
    GDAL_AVAILABLE = True
except Exception:
    GDAL_AVAILABLE = False


POLYGON_WKT = "POLYGON ((2 48, 2.01 48, 2.01 48.01, 2 48, 2 48))"
POLYGON_WKT_2 = "POLYGON ((2.1 48.1, 2.11 48.1, 2.11 48.11, 2.1 48.1, 2.1 48.1))"


class FakeRequest:
    def __init__(self, chunks):
        self._chunks = chunks

    async def stream(self):
        for chunk in self._chunks:
            yield chunk


def epsg_srs(code=4326):
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(code)
    srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return srs


def create_gpkg(path, layers):
    driver = ogr.GetDriverByName("GPKG")
    datasource = driver.CreateDataSource(str(path))
    if datasource is None:
        raise RuntimeError("Création GPKG impossible")
    for spec in layers:
        layer = datasource.CreateLayer(
            spec["name"],
            srs=spec.get("srs", epsg_srs()),
            geom_type=spec.get("geom_type", ogr.wkbPolygon),
        )
        layer.CreateField(ogr.FieldDefn("name", ogr.OFTString))
        for index, wkt in enumerate(spec.get("features", [])):
            feature = ogr.Feature(layer.GetLayerDefn())
            feature.SetField("name", f"feature-{index}")
            if wkt is not None:
                feature.SetGeometry(ogr.CreateGeometryFromWkt(wkt))
            layer.CreateFeature(feature)
            feature = None
    datasource = None


def create_shapefile(path, *, srs=None, geom_type=None, features=None):
    driver = ogr.GetDriverByName("ESRI Shapefile")
    datasource = driver.CreateDataSource(str(path))
    if datasource is None:
        raise RuntimeError("Création Shapefile impossible")
    layer = datasource.CreateLayer(
        path.stem,
        srs=epsg_srs() if srs is None else srs,
        geom_type=ogr.wkbPolygon if geom_type is None else geom_type,
    )
    layer.CreateField(ogr.FieldDefn("name", ogr.OFTString))
    for index, wkt in enumerate(features or [POLYGON_WKT]):
        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetField("name", f"feature-{index}")
        if wkt is not None:
            feature.SetGeometry(ogr.CreateGeometryFromWkt(wkt))
        layer.CreateFeature(feature)
        feature = None
    datasource = None


def zip_directory_files(directory, names=None, *, arc_prefix=""):
    zip_path = directory / "upload.zip"
    selected = names or [
        path.name for path in directory.iterdir() if path.name != zip_path.name
    ]
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in selected:
            archive.write(directory / name, arcname=f"{arc_prefix}{name}")
    return zip_path.read_bytes()


@unittest.skipUnless(GDAL_AVAILABLE, "GDAL/OGR indisponible")
class TerritoireImportGdalTest(unittest.TestCase):
    def import_gpkg(self, path, *, layer=None):
        return import_territoire_geometry(
            path.read_bytes(),
            filename="territoire.gpkg",
            content_type="application/geopackage+sqlite3",
            layer_name=layer,
        )

    def assert_reprojected_polygon(self, imported):
        self.assertEqual(imported.target_srid, TARGET_TERRITORY_SRID)
        geometry = ogr.CreateGeometryFromWkb(imported.wkb)
        self.assertEqual(geometry.GetGeometryType(), ogr.wkbPolygon)
        ring = geometry.GetGeometryRef(0)
        self.assertGreater(abs(ring.GetX(0)), 1000)

    def test_imports_valid_gpkg_polygon_and_reprojects_to_3950(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "territoire.gpkg"
            create_gpkg(path, [{"name": "territoire", "features": [POLYGON_WKT]}])
            imported = self.import_gpkg(path)
        self.assertEqual(imported.source_layer, "territoire")
        self.assertEqual(imported.source_crs, "EPSG:4326")
        self.assert_reprojected_polygon(imported)

    def test_imports_valid_zip_shapefile(self):
        with TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            shp_path = directory / "territoire.shp"
            create_shapefile(shp_path)
            payload = zip_directory_files(directory)
        imported = import_territoire_geometry(
            payload,
            filename="territoire.zip",
            content_type="application/zip",
        )
        self.assertEqual(imported.source_layer, "territoire")
        self.assert_reprojected_polygon(imported)

    def test_rejects_zip_without_required_sidecars(self):
        with TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            create_shapefile(directory / "territoire.shp")
            payload = zip_directory_files(
                directory,
                names=["territoire.shp", "territoire.shx", "territoire.prj"],
            )
        with self.assertRaisesRegex(TerritoireImportError, "incomplète"):
            import_territoire_geometry(
                payload,
                filename="territoire.zip",
                content_type="application/zip",
            )

    def test_rejects_zip_with_multiple_shapefiles(self):
        with TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            create_shapefile(directory / "territoire.shp")
            create_shapefile(directory / "autre.shp")
            payload = zip_directory_files(directory)
        with self.assertRaisesRegex(TerritoireImportError, "exactement un .shp"):
            import_territoire_geometry(
                payload,
                filename="territoire.zip",
                content_type="application/zip",
            )

    def test_rejects_gpkg_without_layer(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "empty.gpkg"
            create_gpkg(path, [{"name": "table", "geom_type": ogr.wkbNone}])
            with self.assertRaisesRegex(TerritoireImportError, "aucune couche"):
                self.import_gpkg(path)

    def test_rejects_multilayer_gpkg_without_explicit_layer(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "multi.gpkg"
            create_gpkg(path, [
                {"name": "a", "features": [POLYGON_WKT]},
                {"name": "b", "features": [POLYGON_WKT_2]},
            ])
            with self.assertRaises(TerritoireImportError) as raised:
                self.import_gpkg(path)
            self.assertEqual(raised.exception.available_layers, ["a", "b"])

    def test_accepts_explicit_gpkg_layer_and_rejects_unknown_layer(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "multi.gpkg"
            create_gpkg(path, [
                {"name": "a", "features": [POLYGON_WKT]},
                {"name": "b", "features": [POLYGON_WKT_2]},
            ])
            self.assertEqual(self.import_gpkg(path, layer="b").source_layer, "b")
            with self.assertRaises(TerritoireImportError) as raised:
                self.import_gpkg(path, layer="absente")
            self.assertEqual(raised.exception.available_layers, ["a", "b"])

    def test_rejects_invalid_feature_counts_and_missing_geometry(self):
        cases = (
            ("zero", [], "aucune entité"),
            ("deux", [POLYGON_WKT, POLYGON_WKT_2], "plusieurs entités"),
            ("sans_geom", [None], "aucune géométrie"),
        )
        for name, features, message in cases:
            with self.subTest(name=name), TemporaryDirectory() as directory:
                path = Path(directory) / f"{name}.gpkg"
                create_gpkg(path, [{"name": name, "features": features}])
                with self.assertRaisesRegex(TerritoireImportError, message):
                    self.import_gpkg(path)

    def test_rejects_missing_crs_empty_and_invalid_geometries(self):
        invalid_polygon = "POLYGON ((0 0, 1 1, 1 0, 0 1, 0 0))"
        cases = (
            ("sans_crs", None, [POLYGON_WKT], "CRS"),
            ("vide", epsg_srs(), ["POLYGON EMPTY"], "vide"),
            ("invalide", epsg_srs(), [invalid_polygon], "invalide"),
        )
        for name, srs, features, message in cases:
            with self.subTest(name=name), TemporaryDirectory() as directory:
                path = Path(directory) / f"{name}.gpkg"
                create_gpkg(path, [{"name": name, "srs": srs, "features": features}])
                with self.assertRaisesRegex(TerritoireImportError, message):
                    self.import_gpkg(path)

    def test_rejects_non_polygon_geometry_types(self):
        cases = (
            ("point", ogr.wkbPoint, "POINT (2 48)"),
            ("line", ogr.wkbLineString, "LINESTRING (2 48, 2.01 48.01)"),
            ("multipolygon", ogr.wkbMultiPolygon, f"MULTIPOLYGON ({POLYGON_WKT[8:]})"),
            ("collection", ogr.wkbGeometryCollection, "GEOMETRYCOLLECTION (POINT (2 48))"),
        )
        for name, geom_type, wkt in cases:
            with self.subTest(name=name), TemporaryDirectory() as directory:
                path = Path(directory) / f"{name}.gpkg"
                create_gpkg(path, [
                    {"name": name, "geom_type": geom_type, "features": [wkt]}
                ])
                with self.assertRaisesRegex(TerritoireImportError, "Polygon"):
                    self.import_gpkg(path)


class TerritoireUploadSecurityTest(unittest.TestCase):
    def test_rejects_unknown_extension_and_content_type(self):
        with self.assertRaisesRegex(TerritoireImportError, "Extension"):
            validate_upload_metadata("territoire.geojson", "application/octet-stream")
        with self.assertRaisesRegex(TerritoireImportError, "contenu"):
            validate_upload_metadata("territoire.gpkg", "text/plain")

    def test_rejects_zip_traversal_absolute_and_too_many_entries(self):
        cases = (
            [SimpleNamespace(filename="../evil.shp", flag_bits=0, is_dir=lambda: False, file_size=1, compress_size=1)],
            [SimpleNamespace(filename="/evil.shp", flag_bits=0, is_dir=lambda: False, file_size=1, compress_size=1)],
            [SimpleNamespace(filename=r"dir\\evil.shp", flag_bits=0, is_dir=lambda: False, file_size=1, compress_size=1)],
        )
        for infos in cases:
            with self.subTest(filename=infos[0].filename):
                with self.assertRaises(TerritoireImportError):
                    _validate_zip_members(infos)

        too_many = [
            SimpleNamespace(
                filename=f"{index}.txt",
                flag_bits=0,
                is_dir=lambda: False,
                file_size=0,
                compress_size=0,
            )
            for index in range(MAX_TERRITORY_ZIP_ENTRIES + 1)
        ]
        with self.assertRaisesRegex(TerritoireImportError, "trop"):
            _validate_zip_members(too_many)

    def test_rejects_encrypted_zip_size_and_compression_ratio(self):
        encrypted = SimpleNamespace(
            filename="territoire.shp",
            flag_bits=0x1,
            is_dir=lambda: False,
            file_size=1,
            compress_size=1,
        )
        with self.assertRaisesRegex(TerritoireImportError, "chiffrée"):
            _validate_zip_members([encrypted])

        oversized = SimpleNamespace(
            filename="territoire.shp",
            flag_bits=0,
            is_dir=lambda: False,
            file_size=MAX_TERRITORY_ZIP_UNCOMPRESSED_BYTES + 1,
            compress_size=MAX_TERRITORY_ZIP_UNCOMPRESSED_BYTES + 1,
        )
        with self.assertRaisesRegex(TerritoireImportError, "décompressée"):
            _validate_zip_members([oversized])

        bomb = SimpleNamespace(
            filename="territoire.shp",
            flag_bits=0,
            is_dir=lambda: False,
            file_size=10_001,
            compress_size=100,
        )
        with self.assertRaisesRegex(TerritoireImportError, "ratio"):
            _validate_zip_members([bomb])

    def test_rejects_body_larger_than_upload_limit(self):
        request = FakeRequest([b"a" * (MAX_TERRITORY_UPLOAD_BYTES + 1)])
        with self.assertRaisesRegex(TerritoireImportError, "taille maximale"):
            asyncio.run(read_limited_body(request, limit=MAX_TERRITORY_UPLOAD_BYTES))


class TerritoireApplicationTest(unittest.TestCase):
    def test_application_exposes_territoire_routes(self):
        paths = {route.path for route in app.routes}
        self.assertIn("/api/territoire-administratif", paths)
        self.assertIn("/api/territoire-administratif/import", paths)
        methods = {
            route.path: route.methods
            for route in app.routes
            if route.path.startswith("/api/territoire-administratif")
        }
        self.assertEqual(methods["/api/territoire-administratif"], {"GET"})
        self.assertEqual(methods["/api/territoire-administratif/import"], {"POST"})

    def test_import_error_handler_exposes_available_layers(self):
        handler = app.exception_handlers[TerritoireImportError]
        response = asyncio.run(
            handler(None, TerritoireImportError("Couche requise.", available_layers=["a"]))
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'"layers":["a"]', response.body)


class TerritoirePersistenceSqlTest(unittest.TestCase):
    def test_singleton_write_sql_uses_wkb_srid_validation_and_upsert(self):
        combined = " ".join(
            (
                TERRITOIRE_VALIDATE_WKB_SQL,
                TERRITOIRE_INSERT_SQL,
                TERRITOIRE_UPSERT_SQL,
            )
        ).lower()
        self.assertIn("st_geomfromwkb", combined)
        self.assertIn(f"st_setsrid(st_geomfromwkb(%s), {TARGET_TERRITORY_SRID})", combined)
        self.assertIn("geometrytype(candidate.geometry)", combined)
        self.assertIn("st_isvalid(candidate.geometry)", combined)
        self.assertIn("not st_isempty(candidate.geometry)", combined)
        self.assertIn("on conflict (id) do nothing", TERRITOIRE_INSERT_SQL.lower())
        self.assertIn("on conflict (id) do update", TERRITOIRE_UPSERT_SQL.lower())
        self.assertIn("::geometry(polygon, 3950)", combined)
        self.assertNotIn("delete from public.territoires_administratifs", combined)


class TerritoirePostGISIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import psycopg

            load_dotenv(
                Path(__file__).resolve().parents[2] / "config.env",
                override=False,
            )
            cls.connection = psycopg.connect(
                **PostgreSQLConfig.from_env().connect_kwargs(autocommit=False),
            )
            with cls.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT to_regclass('public.territoires_administratifs'), "
                    "PostGIS_Version()"
                )
                if cursor.fetchone()[0] != "territoires_administratifs":
                    raise unittest.SkipTest("Table territoires_administratifs absente")
        except unittest.SkipTest:
            raise
        except Exception as exc:
            raise unittest.SkipTest(f"PostGIS local indisponible : {exc}")

    @classmethod
    def tearDownClass(cls):
        connection = getattr(cls, "connection", None)
        if connection is not None:
            connection.rollback()
            connection.close()

    def setUp(self):
        self.connection.execute("SAVEPOINT territoire_test")
        self.connection.execute("DELETE FROM public.territoires_administratifs")

    def tearDown(self):
        self.connection.execute("ROLLBACK TO SAVEPOINT territoire_test")
        self.connection.execute("RELEASE SAVEPOINT territoire_test")

    def wkb_3950(self, wkt):
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT ST_AsBinary(ST_GeomFromText(%s, %s))", (wkt, TARGET_TERRITORY_SRID))
            return bytes(cursor.fetchone()[0])

    def test_get_returns_empty_or_single_feature_collection(self):
        empty = fetch_territoire_administratif(self.connection)
        self.assertEqual(empty, {"type": "FeatureCollection", "features": []})

        result = replace_territoire_administratif(
            self.connection,
            libelle="Territoire A",
            wkb=self.wkb_3950("POLYGON ((0 0, 10 0, 10 10, 0 0))"),
            replace=False,
        )
        self.assertEqual(result["type"], "FeatureCollection")
        self.assertEqual(len(result["features"]), 1)
        self.assertEqual(result["features"][0]["geometry"]["type"], "Polygon")
        self.assertEqual(result["features"][0]["properties"]["srid"], TARGET_TERRITORY_SRID)

    def test_insert_conflict_and_replace_preserve_singleton(self):
        first = self.wkb_3950("POLYGON ((0 0, 10 0, 10 10, 0 0))")
        second = self.wkb_3950("POLYGON ((0 0, 20 0, 20 20, 0 0))")
        replace_territoire_administratif(
            self.connection,
            libelle="Territoire initial",
            wkb=first,
            replace=False,
        )
        with self.assertRaises(TerritoireConflictError):
            replace_territoire_administratif(
                self.connection,
                libelle="Territoire refusé",
                wkb=second,
                replace=False,
            )
        result = replace_territoire_administratif(
            self.connection,
            libelle="Territoire remplacé",
            wkb=second,
            replace=True,
        )
        self.assertEqual(result["features"][0]["id"], 1)
        self.assertEqual(result["features"][0]["properties"]["libelle"], "Territoire remplacé")
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*), min(id), max(id), min(ST_SRID(geometry)) "
                "FROM public.territoires_administratifs"
            )
            self.assertEqual(cursor.fetchone(), (1, 1, 1, TARGET_TERRITORY_SRID))
