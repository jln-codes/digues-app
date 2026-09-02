import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
import uuid

from dotenv import load_dotenv
from pydantic import ValidationError

from sirs_postgre.target import PostgreSQLConfig
from sirs_postgre.target.desordre_reperage import FUNCTION_DEFINITIONS
from sirs_postgre.web.models import (
    DesordreCreate,
    DigueCreate,
    LineStringGeometryUpdate,
    LineEndpoints,
    PointDesordreUpdate,
    PointReperageUpdate,
    SystemeEndiguementCreate,
    TronconCreate,
)
from sirs_postgre.web.queries import (
    DIGUE_DETAIL_SQL,
    DESORDRE_OBSERVATIONS_SQL,
    DESORDRES_GEOJSON_SQL,
    OBSERVATION_DETAIL_SQL,
    POINT_DESORDRE_SQL,
    LINE_DESORDRE_SQL,
    SYSTEMES_ENDIGUEMENT_SQL,
    SYSTEME_ENDIGUEMENT_DETAIL_SQL,
    TRONCON_DETAIL_SQL,
    TRONCONS_GEOJSON_SQL,
    create_digue,
    create_desordre,
    create_systeme_endiguement,
    create_troncon,
    DesordreCreationError,
    fetch_desordres,
    fetch_desordre_observations,
    fetch_desordre,
    fetch_line_desordre,
    fetch_observation,
    fetch_point_desordre,
    fetch_systemes_endiguement,
    fetch_troncons,
    HeritageCreationError,
    update_point_desordre,
    update_point_reperage,
    update_line_desordre_geometry,
    update_line_desordre_endpoints,
    LineDesordreUpdateError,
    PointReperageUpdateError,
    PointReperageUnavailableError,
    PointDesordreUpdateError,
)

try:
    from sirs_postgre.web.app import FRONTEND_DIRECTORY, app, web_show_uuid
except ModuleNotFoundError as exc:
    if exc.name != "fastapi":
        raise
    FRONTEND_DIRECTORY = Path(__file__).resolve().parents[1] / "web"
    app = None
    web_show_uuid = None


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
                "/api/troncons/options",
                "/api/troncons/{troncon_id}/reperage-options",
                "/api/config",
                "/api/systemes-endiguement",
                "/api/digues",
                "/api/desordres",
                "/api/referentiels/types-desordre",
                "/api/desordres/{desordre_id}",
                "/api/desordres/{desordre_id}/observations",
                "/api/desordres/{desordre_id}/reperage",
                "/api/desordres/{desordre_id}/geometry",
                "/api/desordres/{desordre_id}/endpoints",
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
        methods_by_path = {
            path: {
                method
                for route in app.routes
                if route.path == path
                for method in route.methods
            }
            for path in (
                "/api/systemes-endiguement",
                "/api/digues",
                "/api/troncons",
            )
        }
        self.assertTrue({"GET", "POST"} <= methods_by_path["/api/systemes-endiguement"])
        self.assertEqual(methods_by_path["/api/digues"], {"POST"})
        self.assertTrue({"GET", "POST"} <= methods_by_path["/api/troncons"])
        desordre_methods = {
            method
            for route in app.routes
            if route.path == "/api/desordres"
            for method in route.methods
        }
        self.assertTrue({"GET", "POST"} <= desordre_methods)

    def test_business_routes_return_feature_collections(self):
        routes = {
            route.path: route
            for route in app.routes
            if "GET" in getattr(route, "methods", set())
        }
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

    def test_frontend_has_generic_creation_mode_and_context_prefill(self):
        page = (FRONTEND_DIRECTORY / "index.html").read_text(encoding="utf-8")
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        for expected in (
            '+ Nouvel objet ▾',
            'data-create-type="systeme"',
            'data-create-type="digue"',
            'data-create-type="troncon"',
            'data-create-type="desordre"',
            'id="heritage-object-editor"',
            'id="start-troncon-draw"',
        ):
            self.assertIn(expected, page)
        self.assertIn('editorState = { mode: "create", objectType }', script)
        self.assertIn('selectedHeritageObject?.kind === "Système d\'endiguement"', script)
        self.assertIn('selectedHeritageObject?.kind === "Digue"', script)
        self.assertIn("fillHeritageParentOptions", script)

    def test_frontend_desordre_drafts_are_local_and_support_three_geometries(self):
        page = (FRONTEND_DIRECTORY / "index.html").read_text(encoding="utf-8")
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        for expected in (
            'id="desordre-create-editor"',
            '<option value="Point">Point</option>',
            '<option value="LineString">Ligne</option>',
            '<option value="Polygon">Polygone</option>',
            'id="desordre-create-troncons"',
        ):
            self.assertIn(expected, page)
        drawing = script.split(
            'startDesordreDrawButton.addEventListener("click"', 1
        )[1].split('});\n\ncancelDesordreDrawButton', 1)[0]
        self.assertIn("startMarker", drawing)
        self.assertIn("startPolyline", drawing)
        self.assertIn("startPolygon", drawing)
        self.assertNotIn("fetchJson", drawing)
        self.assertIn('fetchJson("/api/desordres"', script)
        self.assertIn('fetchJson("/api/troncons/options")', script)
        self.assertIn("addCreatedDesordreToMap", script)
        self.assertIn("desordreLayersById", script)

    def test_frontend_keeps_creation_and_geometry_local_until_submit(self):
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        drawing = script.split(
            'startTronconDrawButton.addEventListener("click"', 1
        )[1].split(
            'heritageObjectForm.addEventListener("submit"', 1
        )[0]
        self.assertIn("map.editTools.startPolyline", drawing)
        self.assertIn("restoreTronconDraft", drawing)
        self.assertNotIn("fetchJson", drawing)
        cancellation = script.split("function closeHeritageDraft()", 1)[1].split(
            "function selectCreatedHeritageObject", 1
        )[0]
        self.assertIn("clearTronconDraft()", cancellation)
        self.assertNotIn("fetchJson", cancellation)
        submission = script.split(
            'heritageObjectForm.addEventListener("submit"', 1
        )[1].split("function selectedCoordinateFamily", 1)[0]
        self.assertIn('method: "POST"', submission)
        self.assertIn("addCreatedObjectToHeritage", submission)
        self.assertIn("addCreatedTronconToMap", submission)
        self.assertIn("showCreatedObject", submission)

    def test_creation_queries_use_transactions_reloads_and_postgis_transform(self):
        source = (Path(__file__).resolve().parents[1]
                  / "sirs_postgre" / "web" / "queries.py").read_text()
        self.assertIn("with connection.transaction()", source)
        self.assertIn("return fetch_systeme_endiguement", source)
        self.assertIn("return fetch_digue", source)
        self.assertIn("return fetch_troncon", source)
        normalized = " ".join(source.lower().split())
        self.assertIn("insert into public.troncons", normalized)
        self.assertIn("st_transform(st_setsrid(", normalized)
        self.assertIn("st_geomfromgeojson(%s), 4326), 3950)", normalized)
        self.assertIn("st_length(candidate.geometry) > 0", normalized)

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
        self.assertIn("st_startpoint", normalized)
        self.assertIn("st_endpoint", normalized)
        self.assertIn("debut_x_3950", normalized)
        self.assertIn("fin_longitude_4326", normalized)

    def test_line_authorities_use_distinct_postgis_operations(self):
        import inspect

        endpoint_source = inspect.getsource(update_line_desordre_endpoints).lower()
        reperage_source = FUNCTION_DEFINITIONS["appliquer_desordre_reperage"].lower()
        self.assertIn("st_setpoint", endpoint_source)
        self.assertNotIn("st_linesubstring", endpoint_source)
        self.assertIn("st_linesubstring", reperage_source)

    def test_frontend_modes_legend_and_uuid_configuration_are_centralized(self):
        page = (FRONTEND_DIRECTORY / "index.html").read_text(encoding="utf-8")
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        css = (FRONTEND_DIRECTORY / "css" / "app.css").read_text(encoding="utf-8")
        self.assertIn("Choisissez votre mode d’édition", page)
        for identifier in ("line-coordinate-editor", "line-bornage-editor",
                           "polygon-representative-point"):
            self.assertIn(f'id="{identifier}"', page)
        self.assertIn('id="polygon-representative-x" type="text" readonly', page)
        polygon_section = page.split('id="polygon-representative-point"', 1)[1]
        polygon_section = polygon_section.split("</section>", 1)[0]
        self.assertNotIn('name="line-edit-mode"', polygon_section)
        self.assertIn('data-layer-toggle="Polygon"', page)
        self.assertNotIn("L.control.layers", script)
        self.assertIn("map.removeLayer(layer)", script)
        self.assertIn('fetchJson("/api/config")', script)
        self.assertIn("body:not(.show-uuid) .technical-identifier", css)

    def test_frontend_centralizes_modes_and_never_queries_empty_reperage(self):
        page = (FRONTEND_DIRECTORY / "index.html").read_text(encoding="utf-8")
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        self.assertEqual(page.count('class="disorder-form"'), 3)
        self.assertIn("function availableDisorderModes", script)
        self.assertIn('return ["map"]', script)
        self.assertIn('["map", "coordinates"]', script)
        self.assertIn(".filter(Boolean)", script)
        availability = script.split(
            "async function refreshCreationReperageAvailability", 1
        )[1].split("async function openDesordreCreation", 1)[0]
        self.assertLess(availability.index("if (!eligible)"), availability.index(
            "loadTronconReperageOptions"
        ))
        self.assertIn("requestVersion !== creationReperageRequestVersion", availability)
        self.assertNotIn("Not Found", script)

    def test_create_linestring_bornage_follows_rendered_troncon_cardinality(self):
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        css = (FRONTEND_DIRECTORY / "css" / "app.css").read_text(encoding="utf-8")
        available_source = "function availableDisorderModes" + script.split(
            "function availableDisorderModes", 1
        )[1].split("function setModeChoiceAvailability", 1)[0]
        choice_source = "function setModeChoiceAvailability" + script.split(
            "function setModeChoiceAvailability", 1
        )[1].split("function renderCreationModeChoices", 1)[0]
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js indisponible pour le test DOM sans navigateur.")
        program = available_source + choice_source + """
const choice = {
  hidden: false,
  input: { disabled: false },
  querySelector() { return this.input; },
};
const states = [0, 1, 2, 3, 2, 1].map((count) => {
  const available = availableDisorderModes("LineString", count, true)
    .includes("bornage");
  setModeChoiceAvailability(choice, available);
  return { count, available, hidden: choice.hidden,
           disabled: choice.input.disabled };
});
process.stdout.write(JSON.stringify(states));
"""
        completed = subprocess.run(
            [node, "-e", program], check=True, capture_output=True, text=True
        )
        self.assertEqual(
            json.loads(completed.stdout),
            [
                {"count": 0, "available": False, "hidden": True, "disabled": True},
                {"count": 1, "available": True, "hidden": False, "disabled": False},
                {"count": 2, "available": False, "hidden": True, "disabled": True},
                {"count": 3, "available": False, "hidden": True, "disabled": True},
                {"count": 2, "available": False, "hidden": True, "disabled": True},
                {"count": 1, "available": True, "hidden": False, "disabled": False},
            ],
        )
        self.assertIn(".mode-selector .authority-choice[hidden]", css)
        hidden_rule = css.split(
            ".mode-selector .authority-choice[hidden]", 1
        )[1].split("}", 1)[0]
        self.assertIn("display: none !important", hidden_rule)
        renderer = script.split("function renderCreationModeChoices", 1)[1].split(
            "function updateLineCoordinateLabels", 1
        )[0]
        self.assertIn("desordreCreateLineBornageChoice", renderer)
        selection_handler = script.split(
            'desordreCreateTroncons.addEventListener("change"', 1
        )[1].split('startDesordreDrawButton.addEventListener', 1)[0]
        self.assertLess(
            selection_handler.index("renderCreationModeChoices(false)"),
            selection_handler.index("refreshCreationReperageAvailability()"),
        )
        payload_builder = script.split("function buildDesordreCreationPayload", 1)[1]
        payload_builder = payload_builder.split(
            'submitDesordreCreateButton.addEventListener', 1
        )[0]
        self.assertIn('if (!modes.includes("bornage"))', payload_builder)

    def test_create_linestring_replacement_never_flashes_bornage_visibility(self):
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        state_source = "function creationBornageChoiceState" + script.split(
            "function creationBornageChoiceState", 1
        )[1].split("function setModeChoiceState", 1)[0]
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js indisponible pour le test d'état frontend.")
        program = state_source + """
const states = [
  // A déjà chargé, puis remplacement par un B jamais chargé.
  creationBornageChoiceState("LineString", 1, true),
  creationBornageChoiceState("LineString", 1, false),
  creationBornageChoiceState("LineString", 1, true),
  // Retour vers un tronçon déjà présent dans le cache.
  creationBornageChoiceState("LineString", 1, true),
];
process.stdout.write(JSON.stringify({
  states,
  zero: creationBornageChoiceState("LineString", 0, false),
  many: creationBornageChoiceState("LineString", 2, true),
}));
"""
        completed = subprocess.run(
            [node, "-e", program], check=True, capture_output=True, text=True
        )
        result = json.loads(completed.stdout)
        self.assertTrue(all(state["visible"] for state in result["states"]))
        self.assertEqual(
            [state["enabled"] for state in result["states"]],
            [True, False, True, True],
        )
        self.assertEqual(result["zero"], {"visible": False, "enabled": False})
        self.assertEqual(result["many"], {"visible": False, "enabled": False})
        renderer = script.split("function renderCreationModeChoices", 1)[1].split(
            "function updateLineCoordinateLabels", 1
        )[0]
        self.assertIn("creationBornageChoiceState", renderer)
        self.assertIn('tronconCount === 1', state_source)
        self.assertIn('enabled: visible && reperageAvailable', state_source)

    def test_point_graphical_edit_supports_deliberate_map_tap(self):
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        tap_handler = script.split('map.on("click", (event)', 1)[1].split(
            'cancelMapPositionButton.addEventListener', 1
        )[0]
        self.assertIn("graphicEditActive", tap_handler)
        self.assertIn("activePointLayer.setLatLng(provisionalLatLng)", tap_handler)
        self.assertIn("validateMapPositionButton.disabled = false", tap_handler)
        self.assertNotIn("fetchJson", tap_handler)

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

    def test_reproject_buttons_and_warnings_match_editable_geometry_types(self):
        page = (FRONTEND_DIRECTORY / "index.html").read_text(encoding="utf-8")
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        point_actions = page.split('id="cancel-edit"', 1)[1].split("</div>", 1)[0]
        line_actions = page.split('id="line-bornage-editor"', 1)[1].split(
            "</section>", 1
        )[0]
        self.assertIn('id="reproject-point-bornage"', point_actions)
        self.assertLess(
            point_actions.index('id="reproject-point-bornage"'),
            point_actions.index('id="save-edit"'),
        )
        self.assertIn('id="reproject-line-bornage"', line_actions)
        self.assertLess(
            line_actions.index('id="reproject-line-bornage"'),
            line_actions.index('id="save-line-bornage"'),
        )
        self.assertEqual(page.count('>Reprojeter</button>'), 2)
        self.assertIn("modifier le bornage repositionne le point", page)
        self.assertIn("Les sommets de la géométrie actuelle sont perdus", page)
        self.assertIn(
            'reprojectPointBornageButton.hidden = family !== "bornage"',
            script,
        )
        self.assertIn("editorForm.requestSubmit()", script)
        self.assertIn("applyLineReperage", script)
        polygon_editor = script.split("function showReadonlyPolygon", 1)[1].split(
            "desordreCreateForm.addEventListener", 1
        )[0]
        self.assertIn("editorForm.hidden = true", polygon_editor)
        self.assertIn("lineEditorForm.hidden = true", polygon_editor)
        self.assertIn("desordreCreateBornage.hidden = true", polygon_editor)

    def test_reproject_actions_use_current_payload_without_dirty_check(self):
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        point_handler = script.split(
            'reprojectPointBornageButton.addEventListener("click"', 1
        )[1].split(");\n});", 1)[0]
        line_handler = script.split(
            'reprojectLineBornageButton.addEventListener("click"', 1
        )[1].split("saveLineBornageButton.addEventListener", 1)[0]
        self.assertIn("editorForm.requestSubmit(", point_handler)
        self.assertIn("applyLineReperage", line_handler)
        self.assertNotIn("initialFormValues", point_handler)
        self.assertNotIn("initialLineReperageValues", line_handler)

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

    def test_line_endpoints_require_two_distinct_complete_positions(self):
        endpoints = LineEndpoints(crs="EPSG:3950", debut=(1, 2), fin=(3, 4))
        self.assertEqual(endpoints.fin, (3, 4))
        with self.assertRaises(ValidationError):
            LineEndpoints(crs="EPSG:4326", debut=(2, 50), fin=(2, 50))

    def test_rejects_non_line_short_or_invalid_coordinates(self):
        for geometry in (
            {"type": "Point", "coordinates": [2.1, 50.5]},
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

    def test_geometry_update_accepts_valid_polygon(self):
        update = LineStringGeometryUpdate(geometry={
            "type": "Polygon",
            "coordinates": [[[2, 50], [2.1, 50], [2.1, 50.1], [2, 50]]],
        })
        self.assertEqual(update.geometry.type, "Polygon")


class HeritageCreationValidationTest(unittest.TestCase):
    def test_named_objects_trim_labels_and_default_to_valid(self):
        creation = SystemeEndiguementCreate(libelle="  SE neuf  ")
        self.assertEqual(creation.libelle, "SE neuf")
        self.assertTrue(creation.valid)
        with self.assertRaisesRegex(ValidationError, "libellé"):
            SystemeEndiguementCreate(libelle="   ")

    def test_digue_and_troncon_require_their_parent(self):
        with self.assertRaises(ValidationError):
            DigueCreate(libelle="Digue")
        with self.assertRaises(ValidationError):
            TronconCreate(
                libelle="Tronçon",
                geometry={
                    "type": "LineString",
                    "coordinates": [[2.1, 48.5], [2.2, 48.6]],
                },
            )

    def test_troncon_accepts_every_linestring_vertex(self):
        creation = TronconCreate(
            digue_id=uuid.uuid4(),
            libelle="Tronçon sinueux",
            geometry={
                "type": "LineString",
                "coordinates": [
                    [2.10, 48.50],
                    [2.11, 48.52],
                    [2.13, 48.51],
                    [2.15, 48.54],
                ],
            },
        )
        self.assertEqual(len(creation.geometry.coordinates), 4)


class DesordreCreationValidationTest(unittest.TestCase):
    def test_accepts_point_line_and_polygon(self):
        geometries = (
            {"type": "Point", "coordinates": [2.1, 50.5]},
            {
                "type": "LineString",
                "coordinates": [[2.1, 50.5], [2.2, 50.6], [2.3, 50.55]],
            },
            {
                "type": "Polygon",
                "coordinates": [[
                    [2.1, 50.5], [2.2, 50.5], [2.2, 50.6], [2.1, 50.5]
                ]],
            },
        )
        for geometry in geometries:
            with self.subTest(geometry=geometry["type"]):
                creation = DesordreCreate(geometry=geometry)
                self.assertEqual(creation.geometry.type, geometry["type"])

    def test_accepts_point_xy_or_lonlat_as_postgresql_authority(self):
        self.assertEqual(
            DesordreCreate(coord_x_3950=12, coord_y_3950=9).coord_x_3950,
            12,
        )
        self.assertEqual(
            DesordreCreate(
                longitude_4326=2.25, latitude_4326=50.5
            ).latitude_4326,
            50.5,
        )

    def test_rejects_missing_or_multiple_location_authorities(self):
        with self.assertRaisesRegex(ValidationError, "exactement une"):
            DesordreCreate(designation="Sans géométrie")
        with self.assertRaisesRegex(ValidationError, "exactement une"):
            DesordreCreate(
                geometry={"type": "Point", "coordinates": [2.1, 50.5]},
                coord_x_3950=1,
                coord_y_3950=2,
            )

    def test_rejects_invalid_polygon_and_unsupported_geometry(self):
        invalid = (
            {
                "type": "Polygon",
                "coordinates": [[[2.1, 50.5], [2.2, 50.5], [2.2, 50.6]]],
            },
            {
                "type": "Polygon",
                "coordinates": [[
                    [2.1, 50.5], [2.2, 50.5], [2.2, 50.6], [2.0, 50.4]
                ]],
            },
            {"type": "MultiLineString", "coordinates": []},
        )
        for geometry in invalid:
            with self.subTest(geometry=geometry):
                with self.assertRaises(ValidationError):
                    DesordreCreate(geometry=geometry)

    def test_rejects_non_finite_out_of_domain_and_duplicate_links(self):
        for coordinates in ([float("nan"), 50.5], [181, 50.5], [2.1, 91]):
            with self.subTest(coordinates=coordinates):
                with self.assertRaises(ValidationError):
                    DesordreCreate(
                        geometry={"type": "Point", "coordinates": coordinates}
                    )
        troncon_id = uuid.uuid4()
        with self.assertRaisesRegex(ValidationError, "qu'une fois"):
            DesordreCreate(
                geometry={"type": "Point", "coordinates": [2.1, 50.5]},
                troncon_ids=[troncon_id, troncon_id],
            )
        with self.assertRaises(ValidationError):
            DesordreCreate(
                longitude_4326=2.1,
                latitude_4326=50.5,
                troncon_ids=[""],
            )
        self.assertIsNone(DesordreCreate(
            longitude_4326=2.1,
            latitude_4326=50.5,
            type_desordre_id="",
        ).type_desordre_id)

    def test_point_accepts_zero_or_one_troncon_and_rejects_more(self):
        geometry = {"type": "Point", "coordinates": [2.1, 50.5]}
        DesordreCreate(geometry=geometry)
        DesordreCreate(geometry=geometry, troncon_ids=[uuid.uuid4()])
        for count in (2, 3):
            with self.subTest(count=count), self.assertRaisesRegex(
                ValidationError, "au plus un tronçon"
            ):
                DesordreCreate(
                    geometry=geometry,
                    troncon_ids=[uuid.uuid4() for _ in range(count)],
                )

    def test_line_and_polygon_accept_multiple_troncons(self):
        links = [uuid.uuid4(), uuid.uuid4()]
        DesordreCreate(geometry={
            "type": "LineString", "coordinates": [[2, 50], [2.1, 50.1]],
        }, troncon_ids=links)
        DesordreCreate(geometry={
            "type": "Polygon",
            "coordinates": [[[2, 50], [2.1, 50], [2.1, 50.1], [2, 50]]],
        }, troncon_ids=links)


@unittest.skipIf(web_show_uuid is None, "FastAPI indisponible")
class WebConfigurationTest(unittest.TestCase):
    def test_uuid_visibility_defaults_false_and_can_be_enabled(self):
        previous = os.environ.pop("SIRS_WEB_SHOW_UUID", None)
        try:
            self.assertFalse(web_show_uuid())
            os.environ["SIRS_WEB_SHOW_UUID"] = "true"
            self.assertTrue(web_show_uuid())
        finally:
            if previous is None:
                os.environ.pop("SIRS_WEB_SHOW_UUID", None)
            else:
                os.environ["SIRS_WEB_SHOW_UUID"] = previous


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
                cursor.execute(FUNCTION_DEFINITIONS["appliquer_desordre_reperage"])
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
                cls.categorie_desordre_id = f"categorie-web-{uuid.uuid4()}"
                cls.type_desordre_id = f"type-web-{uuid.uuid4()}"
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
                    "INSERT INTO public.ref_categories_desordre "
                    "(id, libelle, valid) VALUES (%s, 'Catégorie web', true)",
                    (cls.categorie_desordre_id,),
                )
                cursor.execute(
                    "INSERT INTO public.ref_types_desordre "
                    "(id, categorie_id, libelle, valid) "
                    "VALUES (%s, %s, 'Type web', true)",
                    (cls.type_desordre_id, cls.categorie_desordre_id),
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
                self.assertIn(
                    feature["geometry"]["type"],
                    {"Point", "LineString", "Polygon"},
                )
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

    def test_create_systeme_reloads_the_persisted_object(self):
        created = create_systeme_endiguement(
            self.connection,
            SystemeEndiguementCreate(libelle="  SE créé par le web  "),
        )
        self.assertEqual(created["libelle"], "SE créé par le web")
        self.assertTrue(created["valid"])
        self.assertEqual(created["digues"], [])
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT libelle, valid FROM public.systemes WHERE id = %s",
                (created["id"],),
            )
            self.assertEqual(cursor.fetchone(), ("SE créé par le web", True))

    def test_create_digue_validates_and_reloads_its_parent(self):
        created = create_digue(
            self.connection,
            DigueCreate(
                systeme_endiguement_id=self.systeme_endiguement_id,
                libelle="Digue créée par le web",
            ),
        )
        self.assertEqual(
            created["systeme_endiguement_id"],
            str(self.systeme_endiguement_id),
        )
        self.assertEqual(created["systeme_endiguement_libelle"], "SE web bornage")
        self.assertEqual(created["troncons"], [])

    def test_create_digue_rejects_unknown_parent_without_partial_insert(self):
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.digues")
            before = cursor.fetchone()[0]
        with self.assertRaisesRegex(HeritageCreationError, "parent"):
            create_digue(
                self.connection,
                DigueCreate(
                    systeme_endiguement_id=uuid.uuid4(),
                    libelle="Ne doit pas exister",
                ),
            )
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.digues")
            self.assertEqual(cursor.fetchone()[0], before)

    def test_create_troncon_transforms_and_preserves_all_vertices(self):
        coordinates = [
            [2.101, 48.801],
            [2.104, 48.804],
            [2.108, 48.802],
            [2.112, 48.807],
        ]
        created = create_troncon(
            self.connection,
            TronconCreate(
                digue_id=self.digue_id,
                libelle="Tronçon web multi-sommets",
                geometry={"type": "LineString", "coordinates": coordinates},
            ),
        )
        self.assertEqual(created["type"], "Feature")
        self.assertEqual(created["geometry"]["type"], "LineString")
        self.assertEqual(len(created["geometry"]["coordinates"]), 4)
        self.assertEqual(created["properties"]["nombre_sommets"], 4)
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT ST_SRID(geometry), ST_NPoints(geometry), "
                "ST_AsGeoJSON(ST_Transform(geometry, 4326))::jsonb "
                "FROM public.troncons WHERE id = %s",
                (created["properties"]["id"],),
            )
            srid, vertices, geometry = cursor.fetchone()
        self.assertEqual((srid, vertices), (3950, 4))
        self.assertEqual(geometry, created["geometry"])

    def test_create_troncon_rejects_degenerate_geometry_without_insert(self):
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.troncons")
            before = cursor.fetchone()[0]
        with self.assertRaisesRegex(HeritageCreationError, "dégénérée"):
            create_troncon(
                self.connection,
                TronconCreate(
                    digue_id=self.digue_id,
                    libelle="Tronçon dégénéré",
                    geometry={
                        "type": "LineString",
                        "coordinates": [[2.1, 48.8], [2.1, 48.8]],
                    },
                ),
            )
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.troncons")
            self.assertEqual(cursor.fetchone()[0], before)

    def test_create_point_desordre_transforms_reloads_and_keeps_reference(self):
        created = create_desordre(
            self.connection,
            DesordreCreate(
                designation="Point créé",
                type_desordre_id=self.type_desordre_id,
                geometry={"type": "Point", "coordinates": [2.25, 50.50]},
            ),
        )
        self.assertEqual(created["geometry"]["type"], "Point")
        self.assertEqual(created["properties"]["designation"], "Point créé")
        self.assertEqual(
            created["properties"]["type_desordre_id"], self.type_desordre_id
        )
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT ST_SRID(geometry), "
                "ST_X(ST_Transform(geometry, 4326)), "
                "ST_Y(ST_Transform(geometry, 4326)) "
                "FROM public.desordres WHERE id = %s",
                (created["properties"]["id"],),
            )
            srid, longitude, latitude = cursor.fetchone()
        self.assertEqual(srid, 3950)
        self.assertAlmostEqual(longitude, 2.25, places=7)
        self.assertAlmostEqual(latitude, 50.50, places=7)

    def test_create_point_desordre_from_xy_uses_writable_view(self):
        created = create_desordre(
            self.connection,
            DesordreCreate(
                designation="Point XY créé",
                coord_x_3950=12.5,
                coord_y_3950=9.25,
                troncon_ids=[self.reperage_troncon_id],
            ),
        )
        self.assertEqual(created["properties"]["coord_x_3950"], 12.5)
        self.assertEqual(created["properties"]["coord_y_3950"], 9.25)
        self.assertEqual(created["properties"]["reperage"]["nombre_troncons"], 1)
        self.assertTrue(created["properties"]["reperage"]["disponible"])

    def test_create_point_from_lonlat_with_optional_contexts(self):
        cases = (
            ([], None),
            ([self.reperage_troncon_id], self.type_desordre_id),
        )
        for troncon_ids, type_id in cases:
            with self.subTest(troncon_ids=troncon_ids, type_id=type_id):
                created = create_desordre(
                    self.connection,
                    DesordreCreate(
                        designation="Point longitude latitude",
                        longitude_4326=2.25,
                        latitude_4326=50.50,
                        troncon_ids=troncon_ids,
                        type_desordre_id=type_id,
                    ),
                )
                self.assertAlmostEqual(
                    created["properties"]["longitude_4326"], 2.25, places=7
                )
                self.assertAlmostEqual(
                    created["properties"]["latitude_4326"], 50.50, places=7
                )
                self.assertEqual(
                    created["properties"]["reperage"]["nombre_troncons"],
                    len(troncon_ids),
                )

    def test_create_multivertex_line_desordre_preserves_every_vertex(self):
        coordinates = [
            [2.101, 50.501], [2.104, 50.504],
            [2.108, 50.502], [2.112, 50.507],
        ]
        created = create_desordre(
            self.connection,
            DesordreCreate(
                designation="Ligne créée",
                geometry={"type": "LineString", "coordinates": coordinates},
            ),
        )
        self.assertEqual(created["geometry"]["type"], "LineString")
        self.assertEqual(created["properties"]["nombre_sommets"], 4)
        self.assertEqual(len(created["geometry"]["coordinates"]), 4)

    def test_create_polygon_desordre_and_disable_longitudinal_reperage(self):
        created = create_desordre(
            self.connection,
            DesordreCreate(
                designation="Polygone créé",
                geometry={
                    "type": "Polygon",
                    "coordinates": [[
                        [2.10, 50.50], [2.12, 50.50],
                        [2.12, 50.52], [2.10, 50.50],
                    ]],
                },
                troncon_ids=[self.reperage_troncon_id, self.second_troncon_id],
            ),
        )
        self.assertEqual(created["geometry"]["type"], "Polygon")
        self.assertEqual(created["properties"]["nombre_troncons"], 2)
        self.assertFalse(created["properties"]["reperage"]["disponible"])
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT ST_SRID(geometry), ST_NPoints(geometry), "
                "(SELECT count(*) FROM public.desordre_localisations_reperage "
                "WHERE desordre_id = d.id) "
                "FROM public.desordres AS d WHERE id = %s",
                (created["properties"]["id"],),
            )
            self.assertEqual(cursor.fetchone(), (3950, 4, 0))

    def test_polygon_graphical_update_recalculates_representative_point(self):
        created = create_desordre(
            self.connection,
            DesordreCreate(geometry={
                "type": "Polygon",
                "coordinates": [[[2, 50], [2.02, 50], [2.02, 50.02], [2, 50]]],
            }),
        )
        before = created["properties"]["longitude_4326"]
        feature = update_line_desordre_geometry(
            self.connection,
            uuid.UUID(created["properties"]["id"]),
            LineStringGeometryUpdate(geometry={
                "type": "Polygon",
                "coordinates": [[[3, 49], [3.02, 49], [3.02, 49.02], [3, 49]]],
            }),
        )
        self.assertEqual(feature["geometry"]["type"], "Polygon")
        self.assertNotEqual(feature["properties"]["longitude_4326"], before)

    def test_create_desordre_invalid_reference_and_polygon_roll_back(self):
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.desordres")
            before = cursor.fetchone()[0]
        with self.assertRaisesRegex(DesordreCreationError, "type"):
            create_desordre(
                self.connection,
                DesordreCreate(
                    type_desordre_id="type-absent",
                    geometry={"type": "Point", "coordinates": [2.1, 50.5]},
                ),
            )
        with self.assertRaisesRegex(DesordreCreationError, "tronçon"):
            create_desordre(
                self.connection,
                DesordreCreate(
                    geometry={"type": "Point", "coordinates": [2.1, 50.5]},
                    troncon_ids=[uuid.uuid4()],
                ),
            )
        with self.assertRaisesRegex(DesordreCreationError, "invalide"):
            create_desordre(
                self.connection,
                DesordreCreate(
                    designation="Polygone croisé",
                    geometry={
                        "type": "Polygon",
                        "coordinates": [[
                            [2.10, 50.50], [2.12, 50.52],
                            [2.12, 50.50], [2.10, 50.52], [2.10, 50.50],
                        ]],
                    },
                ),
            )
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.desordres")
            self.assertEqual(cursor.fetchone()[0], before)

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

    def test_put_unchanged_point_reperage_still_repositions_geometry(self):
        before = fetch_point_desordre(
            self.connection,
            self.reperage_desordre_id,
        )["properties"]["reperage"]
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT set_config('sirs.reperage_guard', 'REPERAGE', true)")
            cursor.execute(
                "UPDATE public.desordres SET geometry = "
                "ST_SetSRID(ST_Point(70, 30), 3950) WHERE id = %s",
                (self.reperage_desordre_id,),
            )
            cursor.execute("SELECT set_config('sirs.reperage_guard', '', true)")
        feature = update_point_reperage(
            self.connection,
            self.reperage_desordre_id,
            PointReperageUpdate(
                borne_debut_id=before["borne_debut_id"],
                distance_debut_m=before["distance_debut_m"],
                position_debut_relative=before["position_debut_relative"],
            ),
        )
        self.assertAlmostEqual(feature["properties"]["coord_x_3950"], 10)
        self.assertAlmostEqual(feature["properties"]["coord_y_3950"], 0)

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

    def test_put_linestring_endpoints_preserves_intermediate_vertices(self):
        feature = update_line_desordre_endpoints(
            self.connection,
            self.line_desordre_id,
            LineEndpoints(crs="EPSG:3950", debut=(-5, 4), fin=(95, 6)),
        )
        self.assertEqual(feature["properties"]["nombre_sommets"], 3)
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT ST_X(ST_PointN(geometry, 1)), ST_Y(ST_PointN(geometry, 1)), "
                "ST_X(ST_PointN(geometry, 2)), ST_Y(ST_PointN(geometry, 2)), "
                "ST_X(ST_PointN(geometry, 3)), ST_Y(ST_PointN(geometry, 3)) "
                "FROM public.desordres WHERE id = %s",
                (self.line_desordre_id,),
            )
            self.assertEqual(cursor.fetchone(), (-5, 4, 30, 8, 95, 6))

    def test_put_linestring_bornage_rebuilds_from_troncon(self):
        with self.connection.cursor() as cursor:
            cursor.execute(
                "UPDATE public.troncons SET geometry = "
                "ST_GeomFromText('LINESTRING(0 0,20 0,40 10,60 10,80 0,100 0)', 3950) "
                "WHERE id = %s",
                (self.reperage_troncon_id,),
            )
        feature = update_point_reperage(
            self.connection,
            self.line_desordre_id,
            PointReperageUpdate(
                borne_debut_id=self.borne_debut_id,
                distance_debut_m=10,
                position_debut_relative="APRES_BORNE",
                borne_fin_id=self.borne_fin_id,
                distance_fin_m=15,
                position_fin_relative="AVANT_BORNE",
            ),
        )
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT ST_Equals(d.geometry, ST_LineSubstring(t.geometry, "
                "10 / ST_Length(t.geometry), "
                "(ST_Length(t.geometry) - 15) / ST_Length(t.geometry))), "
                "ST_NPoints(d.geometry), "
                "ST_DWithin(d.geometry, ST_SetSRID(ST_Point(30, 8), 3950), 0.01) "
                "FROM public.desordres AS d JOIN public.troncons AS t ON t.id = %s "
                "WHERE d.id = %s",
                (self.reperage_troncon_id, self.line_desordre_id),
            )
            equals_substring, vertex_count, keeps_old_middle = cursor.fetchone()
        self.assertTrue(equals_substring)
        self.assertGreater(vertex_count, 2)
        self.assertFalse(keeps_old_middle)

    def test_put_unchanged_line_reperage_still_replaces_free_geometry(self):
        before = fetch_line_desordre(
            self.connection,
            self.line_desordre_id,
        )["properties"]["reperage"]
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT set_config('sirs.reperage_guard', 'REPERAGE', true)")
            cursor.execute(
                "UPDATE public.desordres SET geometry = ST_GeomFromText("
                "'LINESTRING(5 0,30 25,60 -20,80 0)', 3950) WHERE id = %s",
                (self.line_desordre_id,),
            )
            cursor.execute("SELECT set_config('sirs.reperage_guard', '', true)")
        feature = update_point_reperage(
            self.connection,
            self.line_desordre_id,
            PointReperageUpdate(
                borne_debut_id=before["borne_debut_id"],
                distance_debut_m=before["distance_debut_m"],
                position_debut_relative=before["position_debut_relative"],
                borne_fin_id=before["borne_fin_id"],
                distance_fin_m=before["distance_fin_m"],
                position_fin_relative=before["position_fin_relative"],
            ),
        )
        self.assertEqual(feature["geometry"]["type"], "LineString")
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT ST_Equals(d.geometry, ST_LineSubstring(t.geometry, 0.05, 0.8)), "
                "ST_DWithin(d.geometry, ST_SetSRID(ST_Point(30, 25), 3950), 0.01) "
                "FROM public.desordres AS d JOIN public.troncons AS t ON t.id = %s "
                "WHERE d.id = %s",
                (self.reperage_troncon_id, self.line_desordre_id),
            )
            equals_substring, keeps_free_middle = cursor.fetchone()
        self.assertTrue(equals_substring)
        self.assertFalse(keeps_free_middle)

    def test_point_link_update_rejects_multiple_troncons_transactionally(self):
        with self.assertRaisesRegex(PointDesordreUpdateError, "au plus un"):
            update_point_desordre(
                self.connection,
                self.desordre_id,
                PointDesordreUpdate(troncon_ids=[
                    self.reperage_troncon_id, self.second_troncon_id,
                ]),
            )
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM public.link_desordres_troncons "
                "WHERE desordre_id = %s", (self.desordre_id,),
            )
            self.assertEqual(cursor.fetchone()[0], 0)

    def test_link_transitions_keep_fk_and_reperage_coherent(self):
        troncon_a = self.reperage_troncon_id
        troncon_b = self.second_troncon_id

        def create_line(initial_links):
            feature = create_desordre(
                self.connection,
                DesordreCreate(
                    geometry={
                        "type": "LineString",
                        "coordinates": [[2.10, 50.50], [2.11, 50.51], [2.12, 50.50]],
                    },
                    troncon_ids=initial_links,
                ),
            )
            return uuid.UUID(feature["properties"]["id"])

        transitions = (
            ([], [troncon_a]),
            ([troncon_a], []),
            ([troncon_a], [troncon_b]),
            ([troncon_a], [troncon_a, troncon_b]),
            ([troncon_a, troncon_b], [troncon_b]),
            ([troncon_a, troncon_b], []),
        )
        for initial_links, final_links in transitions:
            with self.subTest(initial=initial_links, final=final_links):
                desordre_id = create_line(initial_links)
                feature = update_point_desordre(
                    self.connection,
                    desordre_id,
                    PointDesordreUpdate(troncon_ids=final_links),
                )
                self.assertEqual(
                    set(feature["properties"]["troncon_ids"]),
                    {str(item) for item in final_links},
                )
                with self.connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT count(*) FROM public.desordre_localisations_reperage "
                        "WHERE desordre_id = %s",
                        (desordre_id,),
                    )
                    localisation_count = cursor.fetchone()[0]
                self.assertEqual(localisation_count, 1 if len(final_links) == 1 else 0)

        point = create_desordre(
            self.connection,
            DesordreCreate(longitude_4326=2.25, latitude_4326=50.5),
        )
        point_id = uuid.UUID(point["properties"]["id"])
        for final_links in ([troncon_a], [], [troncon_b]):
            feature = update_point_desordre(
                self.connection,
                point_id,
                PointDesordreUpdate(troncon_ids=final_links),
            )
            self.assertEqual(
                set(feature["properties"]["troncon_ids"]),
                {str(item) for item in final_links},
            )

    def test_type_desordre_is_editable_for_all_geometries_and_nullable(self):
        for desordre_id in (self.desordre_id, self.line_desordre_id):
            feature = update_point_desordre(
                self.connection, desordre_id,
                PointDesordreUpdate(type_desordre_id=self.type_desordre_id),
            )
            self.assertEqual(
                feature["properties"]["type_desordre_id"], self.type_desordre_id
            )
            feature = update_point_desordre(
                self.connection, desordre_id,
                PointDesordreUpdate(type_desordre_id=None),
            )
            self.assertIsNone(feature["properties"]["type_desordre_id"])
        polygon = create_desordre(
            self.connection,
            DesordreCreate(geometry={
                "type": "Polygon",
                "coordinates": [[[2, 50], [2.1, 50], [2.1, 50.1], [2, 50]]],
            }),
        )
        polygon = update_point_desordre(
            self.connection, uuid.UUID(polygon["properties"]["id"]),
            PointDesordreUpdate(type_desordre_id=self.type_desordre_id),
        )
        self.assertEqual(
            polygon["properties"]["type_desordre_id"], self.type_desordre_id
        )
        with self.assertRaisesRegex(PointDesordreUpdateError, "type"):
            update_point_desordre(
                self.connection, self.desordre_id,
                PointDesordreUpdate(type_desordre_id="type-inactif-ou-absent"),
            )

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
