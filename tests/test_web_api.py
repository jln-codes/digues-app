import json
from pathlib import Path
import unittest
import uuid

from dotenv import load_dotenv
from pydantic import ValidationError

from sirs_postgre.target import PostgreSQLConfig
from sirs_postgre.web.models import (
    LineStringGeometryUpdate,
    PointDesordreUpdate,
    PointReperageUpdate,
)
from sirs_postgre.web.queries import (
    DESORDRE_OBSERVATIONS_SQL,
    DESORDRES_GEOJSON_SQL,
    OBSERVATION_DETAIL_SQL,
    POINT_DESORDRE_SQL,
    LINE_DESORDRE_SQL,
    SYSTEMES_ENDIGUEMENT_SQL,
    TRONCONS_GEOJSON_SQL,
    fetch_desordres,
    fetch_desordre_observations,
    fetch_desordre,
    fetch_line_desordre,
    fetch_observation,
    fetch_point_desordre,
    fetch_systemes_endiguement,
    fetch_troncons,
    update_point_desordre,
    update_point_reperage,
    update_line_desordre_geometry,
    LineDesordreUpdateError,
    PointReperageUpdateError,
    PointReperageUnavailableError,
)

try:
    from sirs_postgre.web.app import FRONTEND_DIRECTORY, app
except ModuleNotFoundError as exc:
    if exc.name != "fastapi":
        raise
    FRONTEND_DIRECTORY = Path(__file__).resolve().parents[1] / "web"
    app = None


EMPTY_COLLECTION = {"type": "FeatureCollection", "features": []}


class FakeCursor:
    def __init__(self, result):
        self.result = result
        self.query = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        self.query = query
        self.params = params

    def fetchone(self):
        return (self.result,)


class FakeConnection:
    def __init__(self, result):
        self.cursor_instance = FakeCursor(result)

    def cursor(self):
        return self.cursor_instance


@unittest.skipIf(app is None, "FastAPI indisponible dans l’environnement de test")
class WebApplicationTest(unittest.TestCase):
    def test_application_exposes_expected_routes(self):
        paths = {route.path for route in app.routes}
        self.assertTrue(
            {
                "/",
                "/api/troncons",
                "/api/systemes-endiguement",
                "/api/desordres",
                "/api/desordres/{desordre_id}",
                "/api/desordres/{desordre_id}/observations",
                "/api/desordres/{desordre_id}/reperage",
                "/api/desordres/{desordre_id}/geometry",
                "/api/observations/{observation_id}",
            }
            <= paths
        )
        point_methods = {
            method
            for route in app.routes
            if route.path == "/api/desordres/{desordre_id}"
            for method in route.methods
        }
        self.assertTrue({"GET", "PUT"} <= point_methods)

    def test_business_routes_return_feature_collections(self):
        routes = {route.path: route for route in app.routes}
        for path in ("/api/troncons", "/api/desordres"):
            response = routes[path].endpoint(FakeConnection(EMPTY_COLLECTION))
            self.assertEqual(response, EMPTY_COLLECTION)
            self.assertEqual(
                routes[path].response_class.media_type,
                "application/geo+json",
            )


class WebAssetsAndQueriesTest(unittest.TestCase):
    def test_frontend_files_exist(self):
        self.assertTrue((FRONTEND_DIRECTORY / "index.html").is_file())
        self.assertTrue((FRONTEND_DIRECTORY / "css" / "app.css").is_file())
        self.assertTrue((FRONTEND_DIRECTORY / "js" / "map.js").is_file())

    def test_queries_transform_to_4326_without_updating_geometry(self):
        for query in (TRONCONS_GEOJSON_SQL, DESORDRES_GEOJSON_SQL):
            normalized = " ".join(query.lower().split())
            self.assertIn("st_transform(", normalized)
            self.assertIn("4326", normalized)
            self.assertNotIn(" update ", f" {normalized} ")

    def test_query_result_is_a_feature_collection(self):
        connection = FakeConnection(EMPTY_COLLECTION)
        self.assertEqual(fetch_troncons(connection), EMPTY_COLLECTION)
        self.assertIn("public.troncons", connection.cursor_instance.query)

        serialized = json.dumps(EMPTY_COLLECTION)
        connection = FakeConnection(serialized)
        self.assertEqual(fetch_desordres(connection), EMPTY_COLLECTION)
        self.assertIn("public.desordres", connection.cursor_instance.query)

    def test_frontend_uses_native_single_marker_dragging(self):
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        self.assertIn("L.marker(latlng", script)
        self.assertIn("activePointLayer.dragging.enable()", script)
        self.assertIn('layer.on("dragend"', script)
        self.assertIn("longitude_4326: provisionalLatLng.lng", script)
        self.assertIn("latitude_4326: provisionalLatLng.lat", script)
        self.assertNotIn("Leaflet.Draw", script)
        self.assertNotIn("L.circleMarker", script)

    def test_frontend_has_heritage_navigation_and_explicit_troncon_zoom(self):
        page = (FRONTEND_DIRECTORY / "index.html").read_text(encoding="utf-8")
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        self.assertIn('id="toggle-heritage"', page)
        self.assertIn('id="heritage-panel"', page)
        self.assertIn('id="heritage-tree"', page)
        self.assertIn('id="zoom-troncon"', page)
        self.assertIn("zoomControl: false", script)
        self.assertIn('fetchJson("/api/systemes-endiguement")', script)
        self.assertIn("tronconLayersById", script)
        self.assertIn("map.fitBounds(layer.getBounds(), { padding: [40, 40] })", script)

    def test_hierarchy_query_uses_real_relations_without_artificial_geometry(self):
        normalized = " ".join(SYSTEMES_ENDIGUEMENT_SQL.lower().split())
        self.assertIn("public.systemes", normalized)
        self.assertIn("d.systeme_endiguement_id = s.id", normalized)
        self.assertIn("public.digues", normalized)
        self.assertIn("t.digue_id = d.id", normalized)
        self.assertIn("public.troncons", normalized)
        self.assertNotIn("geometry", normalized)

    def test_hierarchy_result_keeps_identifiers_labels_and_relations(self):
        hierarchy = {
            "systemes": [
                {
                    "id": "systeme-1",
                    "libelle": "SE A",
                    "valid": True,
                    "digues": [
                        {
                            "id": "digue-1",
                            "systeme_endiguement_id": "systeme-1",
                            "libelle": "Digue 1",
                            "valid": True,
                            "troncons": [
                                {
                                    "id": "troncon-1",
                                    "digue_id": "digue-1",
                                    "systeme_reperage_defaut_id": None,
                                    "libelle": "Tronçon 1",
                                    "valid": True,
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        connection = FakeConnection(hierarchy)
        self.assertEqual(fetch_systemes_endiguement(connection), hierarchy)
        self.assertIn("public.systemes", connection.cursor_instance.query)

    def test_observation_queries_preserve_both_parent_child_relations(self):
        observations_query = " ".join(DESORDRE_OBSERVATIONS_SQL.lower().split())
        detail_query = " ".join(OBSERVATION_DETAIL_SQL.lower().split())
        self.assertIn("o.desordre_id = d.id", observations_query)
        self.assertIn("p.observation_id = o.id", observations_query)
        self.assertIn("p.observation_id = o.id", detail_query)
        self.assertNotIn("p.desordre_id", observations_query)
        self.assertNotIn("p.desordre_id", detail_query)

    def test_point_read_query_exposes_real_reperage_and_filtered_bornes(self):
        normalized = " ".join(POINT_DESORDRE_SQL.lower().split())
        self.assertIn("public.link_desordres_troncons", normalized)
        self.assertIn("public.desordre_localisations_reperage", normalized)
        self.assertIn("public.view_systemes_reperage_bornes", normalized)
        self.assertIn("disponible.systeme_reperage_id = sr.id", normalized)
        self.assertIn("liens.nombre_troncons = 1", normalized)

    def test_line_read_query_preserves_all_vertices_and_reads_reperage(self):
        normalized = " ".join(LINE_DESORDRE_SQL.lower().split())
        self.assertIn("public.desordres", normalized)
        self.assertIn("st_npoints(d.geometry)", normalized)
        self.assertIn("public.view_desordre_localisations_reperage", normalized)
        self.assertNotIn("st_startpoint", normalized)
        self.assertNotIn("st_endpoint", normalized)

    def test_observation_results_keep_identifiers_and_nested_photos(self):
        desordre_id = uuid.uuid4()
        observation_id = uuid.uuid4()
        summary = {
            "desordre_id": str(desordre_id),
            "observations": [{"id": str(observation_id), "photo_count": 1}],
        }
        connection = FakeConnection(summary)
        self.assertEqual(fetch_desordre_observations(connection, desordre_id), summary)
        self.assertEqual(connection.cursor_instance.params, (desordre_id,))

        detail = {
            "id": str(observation_id),
            "desordre_id": str(desordre_id),
            "photos": [
                {
                    "id": str(uuid.uuid4()),
                    "observation_id": str(observation_id),
                    "content_available": False,
                }
            ],
        }
        connection = FakeConnection(detail)
        self.assertEqual(fetch_observation(connection, observation_id), detail)
        self.assertEqual(
            detail["photos"][0]["observation_id"],
            detail["id"],
        )

    def test_frontend_has_observation_navigation_and_photo_lightbox(self):
        page = (FRONTEND_DIRECTORY / "index.html").read_text(encoding="utf-8")
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        for identifier in (
            'id="general-tab-button"',
            'id="observations-tab-button"',
            'id="observations-list"',
            'id="observation-detail-view"',
            'id="observation-photos"',
            'id="photo-lightbox"',
        ):
            self.assertIn(identifier, page)
        self.assertIn("/observations`", script)
        self.assertIn("/api/observations/${encodeURIComponent", script)
        self.assertIn("showPhotoInLightbox", script)
        self.assertIn("backToObservationsButton", script)

    def test_frontend_has_exclusive_bornage_mode_and_server_reload(self):
        page = (FRONTEND_DIRECTORY / "index.html").read_text(encoding="utf-8")
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        for identifier in (
            'id="bornage-mode"',
            'name="coordinate-family" value="bornage"',
            'id="reperage-troncon"',
            'id="reperage-borne"',
            'id="reperage-distance"',
            'id="reperage-sens"',
            'id="reperage-pr"',
        ):
            self.assertIn(identifier, page)
        self.assertIn("buildReperagePayload", script)
        self.assertIn("borne_debut_id: reperageFields.borne.value", script)
        self.assertIn("distance_debut_m: distance", script)
        self.assertIn("position_debut_relative: reperageFields.sens.value", script)
        self.assertIn("/reperage`", script)
        self.assertIn("renderServerFeature(feature)", script)
        self.assertIn("updatePointLayer(feature)", script)

    def test_frontend_has_explicit_linestring_editing_without_drag_writes(self):
        page = (FRONTEND_DIRECTORY / "index.html").read_text(encoding="utf-8")
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        self.assertIn("leaflet-editable@1.2.0", page)
        for identifier in (
            'id="line-editor"',
            'id="start-line-edit"',
            'id="validate-line-edit"',
            'id="cancel-line-edit"',
            'id="line-vertex-count"',
        ):
            self.assertIn(identifier, page)
        self.assertIn("activeLineLayer.enableEdit(map)", script)
        self.assertIn("activeLineLayer.disableEdit()", script)
        self.assertIn('map.on("editable:editing"', script)
        self.assertIn("const payload = { geometry };", script)
        self.assertIn("/geometry`", script)
        editing_handler = script.split('map.on("editable:editing"', 1)[1].split(
            "startLineEditButton.addEventListener", 1
        )[0]
        self.assertNotIn("fetchJson", editing_handler)
        self.assertNotIn('method: "PUT"', editing_handler)


class PointUpdateValidationTest(unittest.TestCase):
    def test_accepts_xy_pair(self):
        update = PointDesordreUpdate(coord_x_3950=12.5, coord_y_3950=9.25)
        self.assertEqual(update.coord_x_3950, 12.5)

    def test_accepts_lonlat_pair(self):
        update = PointDesordreUpdate(longitude_4326=2.25, latitude_4326=48.75)
        self.assertEqual(update.latitude_4326, 48.75)
        self.assertEqual(
            set(update.model_dump(exclude_unset=True)),
            {"longitude_4326", "latitude_4326"},
        )

    def test_rejects_incomplete_xy_pair(self):
        with self.assertRaisesRegex(ValidationError, "X et Y"):
            PointDesordreUpdate(coord_x_3950=12.5)

    def test_rejects_incomplete_lonlat_pair(self):
        with self.assertRaisesRegex(ValidationError, "Longitude et latitude"):
            PointDesordreUpdate(longitude_4326=2.25)

    def test_rejects_two_coordinate_families(self):
        with self.assertRaisesRegex(ValidationError, "Une seule famille"):
            PointDesordreUpdate(
                coord_x_3950=12.5,
                coord_y_3950=9.25,
                longitude_4326=2.25,
                latitude_4326=48.75,
            )

    def test_accepts_complete_reperage_family(self):
        borne_id = uuid.uuid4()
        update = PointReperageUpdate(
            borne_debut_id=borne_id,
            distance_debut_m=12.5,
            position_debut_relative="APRES_BORNE",
        )
        self.assertEqual(update.borne_debut_id, borne_id)

    def test_rejects_invalid_reperage_distance_and_sense(self):
        with self.assertRaisesRegex(ValidationError, "positive ou nulle"):
            PointReperageUpdate(
                borne_debut_id=uuid.uuid4(),
                distance_debut_m=-1,
                position_debut_relative="APRES_BORNE",
            )
        with self.assertRaisesRegex(ValidationError, "nulle"):
            PointReperageUpdate(
                borne_debut_id=uuid.uuid4(),
                distance_debut_m=1,
                position_debut_relative="SUR_BORNE",
            )
        with self.assertRaises(ValidationError):
            PointReperageUpdate(
                borne_debut_id=uuid.uuid4(),
                distance_debut_m=1,
                position_debut_relative="SENS_INCONNU",
            )

    def test_reperage_payload_rejects_coordinate_families(self):
        with self.assertRaises(ValidationError):
            PointReperageUpdate(
                borne_debut_id=uuid.uuid4(),
                distance_debut_m=10,
                position_debut_relative="APRES_BORNE",
                coord_x_3950=10,
                coord_y_3950=0,
            )

    def test_accepts_multivertex_linestring_geometry(self):
        update = LineStringGeometryUpdate(
            geometry={
                "type": "LineString",
                "coordinates": [[2.1, 50.5], [2.11, 50.51], [2.12, 50.52]],
            }
        )
        self.assertEqual(len(update.geometry.coordinates), 3)

    def test_rejects_non_line_short_or_invalid_coordinates(self):
        for geometry in (
            {"type": "Point", "coordinates": [2.1, 50.5]},
            {"type": "Polygon", "coordinates": []},
            {"type": "LineString", "coordinates": [[2.1, 50.5]]},
            {
                "type": "LineString",
                "coordinates": [[2.1, 50.5], [float("nan"), 50.6]],
            },
            {
                "type": "LineString",
                "coordinates": [[2.1, 50.5], [181, 50.6]],
            },
        ):
            with self.subTest(geometry=geometry):
                with self.assertRaises(ValidationError):
                    LineStringGeometryUpdate(geometry=geometry)


class WebPostGISIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import psycopg

            load_dotenv(
                Path(__file__).resolve().parents[1] / "config.env",
                override=False,
            )
            cls.connection = psycopg.connect(
                **PostgreSQLConfig.from_env().connect_kwargs(autocommit=False),
            )
            with cls.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT to_regclass('public.troncons'), "
                    "to_regclass('public.desordres')"
                )
                if cursor.fetchone() != ("troncons", "desordres"):
                    raise unittest.SkipTest("Schéma cible absent")
                cls.desordre_id = uuid.uuid4()
                cls.observation_new_id = uuid.uuid4()
                cls.observation_old_id = uuid.uuid4()
                cls.photo_new_id = uuid.uuid4()
                cls.photo_old_id = uuid.uuid4()
                cls.systeme_endiguement_id = uuid.uuid4()
                cls.digue_id = uuid.uuid4()
                cls.reperage_troncon_id = uuid.uuid4()
                cls.second_troncon_id = uuid.uuid4()
                cls.systeme_reperage_id = uuid.uuid4()
                cls.second_systeme_reperage_id = uuid.uuid4()
                cls.borne_debut_id = uuid.uuid4()
                cls.borne_fin_id = uuid.uuid4()
                cls.incompatible_borne_id = uuid.uuid4()
                cls.second_borne_fin_id = uuid.uuid4()
                cls.reperage_desordre_id = uuid.uuid4()
                cls.many_troncons_desordre_id = uuid.uuid4()
                cls.line_desordre_id = uuid.uuid4()
                cursor.execute(
                    "INSERT INTO public.desordres "
                    "(id, designation, commentaire, geometry, valid) "
                    "VALUES (%s, 'Web test', 'Initial', "
                    "ST_SetSRID(ST_Point(10, 7), 3950), true)",
                    (cls.desordre_id,),
                )
                cursor.execute(
                    "INSERT INTO public.observations "
                    "(id, desordre_id, designation, date, evolution, valid) VALUES "
                    "(%s, %s, 'Observation récente', DATE '2025-05-02', "
                    "'Évolution récente', true), "
                    "(%s, %s, 'Observation ancienne', DATE '2024-01-03', "
                    "'Évolution ancienne', true)",
                    (
                        cls.observation_new_id,
                        cls.desordre_id,
                        cls.observation_old_id,
                        cls.desordre_id,
                    ),
                )
                cursor.execute(
                    "INSERT INTO public.photos "
                    "(id, observation_id, chemin_source, date, designation, valid) "
                    "VALUES (%s, %s, %s, DATE '2025-05-03', 'Vue aval', true), "
                    "(%s, %s, %s, DATE '2025-05-01', 'Vue amont', true)",
                    (
                        cls.photo_new_id,
                        cls.observation_new_id,
                        r"C:\\archives\\vue-aval.jpg",
                        cls.photo_old_id,
                        cls.observation_new_id,
                        "/archives/vue-amont.jpg",
                    ),
                )
                cursor.execute(
                    "INSERT INTO public.systemes (id, libelle, valid) "
                    "VALUES (%s, 'SE web bornage', true)",
                    (cls.systeme_endiguement_id,),
                )
                cursor.execute(
                    "INSERT INTO public.digues "
                    "(id, systeme_endiguement_id, libelle, valid) "
                    "VALUES (%s, %s, 'Digue web bornage', true)",
                    (cls.digue_id, cls.systeme_endiguement_id),
                )
                cursor.execute(
                    "INSERT INTO public.troncons "
                    "(id, digue_id, libelle, geometry, valid) VALUES "
                    "(%s, %s, 'Tronçon web bornage', "
                    "ST_GeomFromText('LINESTRING(0 0,100 0)', 3950), true), "
                    "(%s, %s, 'Second tronçon web', "
                    "ST_GeomFromText('LINESTRING(0 10,100 10)', 3950), true)",
                    (
                        cls.reperage_troncon_id,
                        cls.digue_id,
                        cls.second_troncon_id,
                        cls.digue_id,
                    ),
                )
                cursor.execute(
                    "INSERT INTO public.systemes_reperage "
                    "(id, troncon_id, libelle, valid) VALUES "
                    "(%s, %s, 'Repérage web', true), "
                    "(%s, %s, 'Second repérage web', true)",
                    (
                        cls.systeme_reperage_id,
                        cls.reperage_troncon_id,
                        cls.second_systeme_reperage_id,
                        cls.second_troncon_id,
                    ),
                )
                cursor.execute(
                    "INSERT INTO public.bornes_reperage "
                    "(id, libelle, geometry, valid) VALUES "
                    "(%s, 'Borne A', ST_SetSRID(ST_Point(0, 0), 3950), true), "
                    "(%s, 'Borne B', ST_SetSRID(ST_Point(100, 0), 3950), true), "
                    "(%s, 'Borne C', ST_SetSRID(ST_Point(0, 10), 3950), true), "
                    "(%s, 'Borne D', ST_SetSRID(ST_Point(100, 10), 3950), true)",
                    (
                        cls.borne_debut_id,
                        cls.borne_fin_id,
                        cls.incompatible_borne_id,
                        cls.second_borne_fin_id,
                    ),
                )
                for troncon_id, systeme_id, debut_id, fin_id in (
                    (
                        cls.reperage_troncon_id,
                        cls.systeme_reperage_id,
                        cls.borne_debut_id,
                        cls.borne_fin_id,
                    ),
                    (
                        cls.second_troncon_id,
                        cls.second_systeme_reperage_id,
                        cls.incompatible_borne_id,
                        cls.second_borne_fin_id,
                    ),
                ):
                    cursor.execute(
                        "INSERT INTO public.link_troncons_bornes "
                        "(troncon_id, borne_id) VALUES (%s, %s), (%s, %s)",
                        (troncon_id, debut_id, troncon_id, fin_id),
                    )
                    cursor.execute(
                        "INSERT INTO public.link_systemes_reperage_bornes "
                        "(id, systeme_reperage_id, borne_id, valeur_pr, valid) "
                        "VALUES (%s, %s, %s, 0, true), "
                        "(%s, %s, %s, 100, true)",
                        (
                            uuid.uuid4(),
                            systeme_id,
                            debut_id,
                            uuid.uuid4(),
                            systeme_id,
                            fin_id,
                        ),
                    )
                    cursor.execute(
                        "UPDATE public.troncons "
                        "SET systeme_reperage_defaut_id = %s WHERE id = %s",
                        (systeme_id, troncon_id),
                    )
                cursor.execute(
                    "INSERT INTO public.desordres "
                    "(id, designation, geometry, valid) VALUES "
                    "(%s, 'Point web bornage', "
                    "ST_SetSRID(ST_Point(10, 7), 3950), true), "
                    "(%s, 'Point web multilien', "
                    "ST_SetSRID(ST_Point(10, 7), 3950), true), "
                    "(%s, 'Ligne web', "
                    "ST_GeomFromText('LINESTRING(5 2,30 8,80 3)', 3950), true)",
                    (
                        cls.reperage_desordre_id,
                        cls.many_troncons_desordre_id,
                        cls.line_desordre_id,
                    ),
                )
                cursor.execute(
                    "INSERT INTO public.link_desordres_troncons "
                    "(desordre_id, troncon_id) VALUES "
                    "(%s, %s), (%s, %s), (%s, %s), (%s, %s)",
                    (
                        cls.reperage_desordre_id,
                        cls.reperage_troncon_id,
                        cls.many_troncons_desordre_id,
                        cls.reperage_troncon_id,
                        cls.many_troncons_desordre_id,
                        cls.second_troncon_id,
                        cls.line_desordre_id,
                        cls.reperage_troncon_id,
                    ),
                )
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
        self.connection.execute("SAVEPOINT web_api_test")

    def tearDown(self):
        self.connection.execute("ROLLBACK TO SAVEPOINT web_api_test")
        self.connection.execute("RELEASE SAVEPOINT web_api_test")

    def test_real_endpoints_queries_return_feature_collections(self):
        for collection in (
            fetch_troncons(self.connection),
            fetch_desordres(self.connection),
        ):
            self.assertEqual(collection["type"], "FeatureCollection")
            self.assertIsInstance(collection["features"], list)
            for feature in collection["features"]:
                self.assertEqual(feature["type"], "Feature")
                self.assertIn(feature["geometry"]["type"], {"Point", "LineString"})
                self.assertIsInstance(feature["properties"], dict)

    def test_real_hierarchy_has_coherent_parent_relations(self):
        hierarchy = fetch_systemes_endiguement(self.connection)
        self.assertIsInstance(hierarchy["systemes"], list)
        for systeme in hierarchy["systemes"]:
            self.assertTrue({"id", "libelle", "valid", "digues"} <= set(systeme))
            self.assertNotIn("geometry", systeme)
            for digue in systeme["digues"]:
                self.assertEqual(digue["systeme_endiguement_id"], systeme["id"])
                self.assertTrue({"id", "libelle", "valid", "troncons"} <= set(digue))
                self.assertNotIn("geometry", digue)
                for troncon in digue["troncons"]:
                    self.assertEqual(troncon["digue_id"], digue["id"])
                    self.assertTrue({"id", "libelle", "valid"} <= set(troncon))

    def test_get_real_point_desordre(self):
        feature = fetch_point_desordre(self.connection, self.desordre_id)
        self.assertEqual(feature["type"], "Feature")
        self.assertEqual(feature["geometry"]["type"], "Point")
        self.assertEqual(feature["properties"]["id"], str(self.desordre_id))
        self.assertEqual(feature["properties"]["coord_x_3950"], 10)
        self.assertEqual(feature["properties"]["coord_y_3950"], 7)

    def test_real_observations_are_related_and_ordered_by_descending_date(self):
        result = fetch_desordre_observations(self.connection, self.desordre_id)
        self.assertEqual(result["desordre_id"], str(self.desordre_id))
        self.assertEqual(
            [item["id"] for item in result["observations"][:2]],
            [str(self.observation_new_id), str(self.observation_old_id)],
        )
        self.assertEqual(result["observations"][0]["photo_count"], 2)

    def test_real_observation_returns_only_its_photo_children(self):
        result = fetch_observation(self.connection, self.observation_new_id)
        self.assertEqual(result["desordre_id"], str(self.desordre_id))
        self.assertEqual(
            [photo["observation_id"] for photo in result["photos"]],
            [str(self.observation_new_id), str(self.observation_new_id)],
        )
        self.assertEqual(
            [photo["id"] for photo in result["photos"]],
            [str(self.photo_new_id), str(self.photo_old_id)],
        )
        self.assertEqual(
            [photo["nom_fichier"] for photo in result["photos"]],
            ["vue-aval.jpg", "vue-amont.jpg"],
        )
        self.assertTrue(all(not photo["content_available"] for photo in result["photos"]))
        self.assertTrue(all("chemin_source" not in photo for photo in result["photos"]))

    def test_reperage_availability_follows_zero_one_many_rule(self):
        zero = fetch_point_desordre(self.connection, self.desordre_id)
        one = fetch_point_desordre(self.connection, self.reperage_desordre_id)
        many = fetch_point_desordre(
            self.connection,
            self.many_troncons_desordre_id,
        )
        self.assertEqual(zero["properties"]["reperage"]["nombre_troncons"], 0)
        self.assertFalse(zero["properties"]["reperage"]["disponible"])
        self.assertEqual(one["properties"]["reperage"]["nombre_troncons"], 1)
        self.assertTrue(one["properties"]["reperage"]["disponible"])
        self.assertEqual(
            {borne["id"] for borne in one["properties"]["reperage"]["bornes"]},
            {str(self.borne_debut_id), str(self.borne_fin_id)},
        )
        self.assertEqual(many["properties"]["reperage"]["nombre_troncons"], 2)
        self.assertFalse(many["properties"]["reperage"]["disponible"])

    def test_put_reperage_rebuilds_geometry_coordinates_and_reloads_state(self):
        feature = update_point_reperage(
            self.connection,
            self.reperage_desordre_id,
            PointReperageUpdate(
                borne_debut_id=self.borne_debut_id,
                distance_debut_m=25,
                position_debut_relative="APRES_BORNE",
            ),
        )
        properties = feature["properties"]
        reperage = properties["reperage"]
        self.assertEqual(reperage["borne_debut_id"], str(self.borne_debut_id))
        self.assertAlmostEqual(reperage["distance_debut_m"], 25)
        self.assertEqual(reperage["position_debut_relative"], "APRES_BORNE")
        self.assertAlmostEqual(properties["coord_x_3950"], 25)
        self.assertAlmostEqual(properties["coord_y_3950"], 0)
        self.assertIsNotNone(properties["longitude_4326"])
        self.assertIsNotNone(properties["latitude_4326"])
        self.assertEqual(feature["geometry"]["type"], "Point")

        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT ST_X(d.geometry), ST_Y(d.geometry), "
                "ST_X(ST_Transform(d.geometry, 4326)), "
                "ST_Y(ST_Transform(d.geometry, 4326)), "
                "l.borne_debut_id, l.distance_debut_m, "
                "l.position_debut_relative, l.pr_debut "
                "FROM public.desordres AS d "
                "JOIN public.desordre_localisations_reperage AS l "
                "ON l.desordre_id = d.id WHERE d.id = %s",
                (self.reperage_desordre_id,),
            )
            stored = cursor.fetchone()
        self.assertEqual(stored[0:2], (25, 0))
        self.assertAlmostEqual(stored[2], properties["longitude_4326"], places=8)
        self.assertAlmostEqual(stored[3], properties["latitude_4326"], places=8)
        self.assertEqual(
            stored[4:7],
            (self.borne_debut_id, 25, "APRES_BORNE"),
        )
        self.assertEqual(stored[7], reperage["pr_debut"])

    def test_put_reperage_rejects_zero_or_many_associated_troncons(self):
        update = PointReperageUpdate(
            borne_debut_id=self.borne_debut_id,
            distance_debut_m=10,
            position_debut_relative="APRES_BORNE",
        )
        for desordre_id in (
            self.desordre_id,
            self.many_troncons_desordre_id,
        ):
            with self.assertRaises(PointReperageUnavailableError):
                update_point_reperage(self.connection, desordre_id, update)

    def test_put_reperage_rejects_borne_from_another_system(self):
        with self.assertRaises(PointReperageUpdateError):
            update_point_reperage(
                self.connection,
                self.reperage_desordre_id,
                PointReperageUpdate(
                    borne_debut_id=self.incompatible_borne_id,
                    distance_debut_m=10,
                    position_debut_relative="APRES_BORNE",
                ),
            )

    def test_get_real_linestring_desordre_keeps_multivertex_geometry(self):
        feature = fetch_desordre(self.connection, self.line_desordre_id)
        self.assertEqual(feature["geometry"]["type"], "LineString")
        self.assertEqual(len(feature["geometry"]["coordinates"]), 3)
        self.assertEqual(feature["properties"]["nombre_sommets"], 3)
        self.assertTrue(feature["properties"]["reperage"]["disponible"])
        self.assertEqual(
            fetch_line_desordre(self.connection, self.line_desordre_id),
            feature,
        )

    def test_put_linestring_transforms_preserves_vertices_and_reloads_db(self):
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT ST_AsGeoJSON(ST_Transform(ST_GeomFromText("
                "'LINESTRING(7 1,25 9,55 12,90 2)', 3950), 4326))::jsonb"
            )
            geometry = cursor.fetchone()[0]
        feature = update_line_desordre_geometry(
            self.connection,
            self.line_desordre_id,
            LineStringGeometryUpdate(geometry=geometry),
        )
        self.assertEqual(feature["geometry"]["type"], "LineString")
        self.assertEqual(len(feature["geometry"]["coordinates"]), 4)
        self.assertEqual(feature["properties"]["nombre_sommets"], 4)
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT ST_AsGeoJSON(ST_Transform(geometry, 4326))::jsonb, "
                "ST_NPoints(geometry), ST_SRID(geometry) "
                "FROM public.desordres WHERE id = %s",
                (self.line_desordre_id,),
            )
            stored_geometry, stored_vertices, stored_srid = cursor.fetchone()
        self.assertEqual(stored_geometry, feature["geometry"])
        self.assertEqual(stored_vertices, 4)
        self.assertEqual(stored_srid, 3950)

    def test_put_linestring_rejects_postgis_invalid_geometry(self):
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT ST_AsGeoJSON(ST_Transform("
                "ST_SetSRID(ST_Point(10, 5), 3950), 4326))::jsonb"
            )
            point = cursor.fetchone()[0]["coordinates"]
        with self.assertRaises(LineDesordreUpdateError):
            update_line_desordre_geometry(
                self.connection,
                self.line_desordre_id,
                LineStringGeometryUpdate(
                    geometry={"type": "LineString", "coordinates": [point, point]}
                ),
            )

    def test_put_xy_returns_postgresql_recalculated_state(self):
        feature = update_point_desordre(
            self.connection,
            self.desordre_id,
            PointDesordreUpdate(coord_x_3950=12.5, coord_y_3950=9.25),
        )
        properties = feature["properties"]
        self.assertAlmostEqual(properties["coord_x_3950"], 12.5)
        self.assertAlmostEqual(properties["coord_y_3950"], 9.25)
        self.assertIsNotNone(properties["longitude_4326"])
        self.assertIsNotNone(properties["latitude_4326"])
        self.assertEqual(feature["geometry"]["type"], "Point")

        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT coord_x_3950, coord_y_3950, longitude_4326, latitude_4326 "
                "FROM public.view_desordres_points_saisie WHERE id = %s",
                (self.desordre_id,),
            )
            stored = cursor.fetchone()
        self.assertEqual(
            stored,
            (
                properties["coord_x_3950"],
                properties["coord_y_3950"],
                properties["longitude_4326"],
                properties["latitude_4326"],
            ),
        )

    def test_put_lonlat_returns_xy_recalculated_by_postgresql(self):
        feature = update_point_desordre(
            self.connection,
            self.desordre_id,
            PointDesordreUpdate(
                longitude_4326=2.25,
                latitude_4326=48.75,
            ),
        )
        properties = feature["properties"]
        self.assertAlmostEqual(properties["longitude_4326"], 2.25, places=8)
        self.assertAlmostEqual(properties["latitude_4326"], 48.75, places=8)
        self.assertNotAlmostEqual(properties["coord_x_3950"], 10)
        self.assertNotAlmostEqual(properties["coord_y_3950"], 7)


if __name__ == "__main__":
    unittest.main()
