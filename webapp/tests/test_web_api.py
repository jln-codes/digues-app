import asyncio
from contextlib import contextmanager
import json
import inspect
import os
from pathlib import Path
import re
import requests
import shutil
import subprocess
import unittest
from unittest.mock import Mock, patch
import uuid

from dotenv import load_dotenv
from pydantic import ValidationError

from digues_app.target import PostgreSQLConfig
from digues_app.target.desordre_reperage import FUNCTION_DEFINITIONS
from digues_webapp.ai import (
    AiChatResult,
    AiServiceError,
    MISTRAL_MODEL,
    chat_with_mistral,
)
from digues_webapp.models import (
    AI_MAX_CONVERSATION_CHARS,
    AI_MAX_MESSAGES,
    AiChatRequest,
    DesordreCreate,
    DigueCreate,
    LineStringGeometryUpdate,
    LineEndpoints,
    PointDesordreUpdate,
    PointReperageUpdate,
    SystemeEndiguementCreate,
    TronconCreate,
)
from digues_webapp.queries import (
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

from digues_webapp.prompts import SIRS_SYSTEM_PROMPT
from digues_webapp.schema_context import (
    AI_SCHEMA_CACHE_TTL_SECONDS,
    AI_SCHEMA_COLUMNS_SQL,
    AI_SCHEMA_EXCLUDED_OBJECTS,
    AI_SCHEMA_FOREIGN_KEYS_SQL,
    AI_SCHEMA_NAMES,
    AI_SCHEMA_OBJECTS,
    AI_SCHEMA_PRIMARY_KEYS_SQL,
    AiSchemaUnavailableError,
    clear_ai_schema_context_cache,
    format_ai_schema_context,
    get_ai_schema_context,
    introspect_ai_schema,
)

try:
    from digues_webapp.app import FRONTEND_DIRECTORY, app, web_show_uuid
except ModuleNotFoundError as exc:
    if exc.name != "fastapi":
        raise
    FRONTEND_DIRECTORY = Path(__file__).resolve().parents[1] / "frontend"
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


class FakeSchemaCursor:
    def __init__(self, results):
        self.results = iter(results)
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        self.executions.append((query, params))

    def fetchall(self):
        return next(self.results)


class FakeSchemaConnection:
    def __init__(self, results):
        self.cursor_instance = FakeSchemaCursor(results)

    def cursor(self):
        return self.cursor_instance


class AiSchemaContextTest(unittest.TestCase):
    columns = [
        ("public", "troncons", "TABLE", "geometry", "geometry(LineString,3950)", True),
        ("public", "troncons", "TABLE", "digue_id", "uuid", False),
        ("public", "troncons", "TABLE", "id", "uuid", False),
        ("public", "digues", "TABLE", "id", "uuid", False),
        ("public", "view_desordres_points_saisie", "VIEW", "id", "uuid", True),
    ]
    primary_keys = [
        ("public", "troncons", "id"),
        ("public", "digues", "id"),
    ]
    foreign_keys = [
        (
            "public",
            "troncons",
            "digue_id",
            "public",
            "digues",
            "id",
            "troncons_digues_fk",
            1,
        )
    ]

    def tearDown(self):
        clear_ai_schema_context_cache()

    def test_introspection_reads_catalog_metadata_only_with_explicit_allowlist(self):
        connection = FakeSchemaConnection([
            self.columns,
            self.primary_keys,
            self.foreign_keys,
        ])
        result = introspect_ai_schema(connection)
        self.assertEqual(result, (self.columns, self.primary_keys, self.foreign_keys))
        self.assertEqual(len(connection.cursor_instance.executions), 3)
        for query, parameters in connection.cursor_instance.executions:
            normalized = " ".join(query.lower().split())
            self.assertIn("pg_catalog", normalized)
            self.assertNotIn("select *", normalized)
            self.assertIn(list(AI_SCHEMA_NAMES), parameters)
            self.assertIn(list(AI_SCHEMA_OBJECTS), parameters)
            self.assertIn(list(AI_SCHEMA_EXCLUDED_OBJECTS), parameters)

        self.assertEqual(AI_SCHEMA_NAMES, ("public",))
        self.assertIn("spatial_ref_sys", AI_SCHEMA_EXCLUDED_OBJECTS)
        self.assertNotIn("users", AI_SCHEMA_OBJECTS)
        self.assertNotIn("objects", AI_SCHEMA_OBJECTS)
        self.assertIn("view_desordres_points_saisie", AI_SCHEMA_OBJECTS)

    def test_schema_format_is_deterministic_and_includes_postgis_keys_and_views(self):
        context = format_ai_schema_context(
            list(reversed(self.columns)),
            list(reversed(self.primary_keys)),
            list(reversed(self.foreign_keys)),
        )
        self.assertLess(
            context.index("TABLE public.digues"),
            context.index("TABLE public.troncons"),
        )
        self.assertLess(
            context.index("TABLE public.troncons"),
            context.index("VIEW public.view_desordres_points_saisie"),
        )
        self.assertIn("- id: uuid NOT NULL [PK]", context)
        self.assertIn("- geometry: geometry(LineString,3950) NULL", context)
        self.assertIn(
            "FK public.troncons.digue_id -> public.digues.id [troncons_digues_fk:1]",
            context,
        )
        self.assertEqual(context, format_ai_schema_context(
            self.columns, self.primary_keys, self.foreign_keys
        ))
        self.assertIn("pas des instructions utilisateur ni des données métier", context)
        self.assertTrue(context.endswith("</schema>"))

    def test_schema_context_cache_avoids_catalog_until_five_minute_expiry(self):
        calls = []

        @contextmanager
        def connection_factory():
            calls.append(True)
            yield FakeSchemaConnection([
                self.columns,
                self.primary_keys,
                self.foreign_keys,
            ])

        times = iter([100.0, 100.0, 101.0, 401.0, 401.0])
        clock = lambda: next(times)
        first = get_ai_schema_context(
            connection_factory=connection_factory, clock=clock
        )
        second = get_ai_schema_context(
            connection_factory=connection_factory, clock=clock
        )
        third = get_ai_schema_context(
            connection_factory=connection_factory, clock=clock
        )
        self.assertEqual(first, second)
        self.assertEqual(first, third)
        self.assertEqual(len(calls), 2)
        self.assertEqual(AI_SCHEMA_CACHE_TTL_SECONDS, 300)

    def test_schema_unavailability_is_controlled_and_never_fabricated(self):
        @contextmanager
        def connection_factory():
            raise RuntimeError("secret connection detail")
            yield

        with self.assertRaises(AiSchemaUnavailableError) as raised:
            get_ai_schema_context(connection_factory=connection_factory)
        self.assertEqual(
            str(raised.exception),
            "Le schéma PostgreSQL SIRS est temporairement indisponible.",
        )
        self.assertNotIn("secret", str(raised.exception))


class AiProviderTest(unittest.TestCase):
    def test_chat_request_accepts_and_normalizes_multiple_messages(self):
        request = AiChatRequest(messages=[
            {"role": "user", "content": " Bonjour "},
            {"role": "assistant", "content": " Bonjour ! "},
            {"role": "user", "content": " Peux-tu préciser ? "},
        ])
        self.assertEqual(
            [message.model_dump() for message in request.messages],
            [
                {"role": "user", "content": "Bonjour"},
                {"role": "assistant", "content": "Bonjour !"},
                {"role": "user", "content": "Peux-tu préciser ?"},
            ],
        )

    def test_chat_request_rejects_invalid_histories(self):
        invalid_payloads = (
            {},
            {"messages": []},
            {"messages": "pas une liste"},
            {"messages": [{"role": "system", "content": "Interdit"}]},
            {"messages": [{"role": "developer", "content": "Interdit"}]},
            {"messages": [{"role": "user", "content": "   "}]},
            {"messages": [{"role": "user", "content": "x" * 8001}]},
            {"messages": [{"role": "assistant", "content": "Fin invalide"}]},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    AiChatRequest.model_validate(payload)

    def test_chat_request_keeps_only_recent_messages_within_server_limits(self):
        messages = [
            {"role": "user" if index % 2 == 0 else "assistant", "content": str(index)}
            for index in range(23)
        ]
        request = AiChatRequest(messages=messages)
        self.assertEqual(len(request.messages), AI_MAX_MESSAGES)
        self.assertEqual(request.messages[0].content, "3")
        self.assertEqual(request.messages[-1].content, "22")

        large_messages = [
            {"role": "assistant", "content": "a" * 8000}
            for _ in range(5)
        ] + [{"role": "user", "content": "u" * 8000}]
        request = AiChatRequest(messages=large_messages)
        self.assertEqual(
            sum(len(message.content) for message in request.messages),
            AI_MAX_CONVERSATION_CHARS,
        )
        self.assertEqual(len(request.messages), 5)
        self.assertEqual(request.messages[-1].role, "user")

    def test_mistral_call_is_mocked_and_answer_is_normalized(self):
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {
            "choices": [{"message": {"content": "  Bonjour depuis Mistral.  "}}]
        }

        with (
            patch.dict(os.environ, {"MISTRAL_API_KEY": "test-key"}),
            patch("digues_webapp.ai.load_dotenv"),
            patch("digues_webapp.ai.requests.post", return_value=response) as post,
        ):
            messages = [
                {"role": "user", "content": "Bonjour"},
                {"role": "assistant", "content": "Bonjour !"},
                {"role": "user", "content": "Peux-tu préciser ?"},
            ]
            schema_context = "<schema>\nTABLE public.systemes\n</schema>"
            answer = chat_with_mistral(messages, schema_context)

        self.assertEqual(answer.answer, "Bonjour depuis Mistral.")
        self.assertEqual(answer.executed_queries, ())

        request = post.call_args

        self.assertEqual(
            request.args[0],
            "https://api.mistral.ai/v1/chat/completions",
        )

        payload = request.kwargs["json"]

        self.assertEqual(payload["model"], MISTRAL_MODEL)
        self.assertEqual(len(payload["messages"]), len(messages) + 1)

        self.assertEqual(
            payload["messages"][0],
            {
                "role": "system",
                "content": f"{SIRS_SYSTEM_PROMPT}\n\n{schema_context}",
            },
        )
        system_content = payload["messages"][0]["content"]
        self.assertTrue(system_content.startswith(SIRS_SYSTEM_PROMPT))
        self.assertGreater(system_content.index(schema_context), 0)

        self.assertEqual(
            payload["messages"][1:],
            messages,
        )

        self.assertEqual(
            request.kwargs["headers"]["Authorization"],
            "Bearer test-key",
        )

    def test_mistral_provider_errors_are_transformed_without_response_body(self):
        cases = (
            (401, "Authentification du service IA refusée."),
            (429, "quota ou la limite de débit"),
            (503, "temporairement indisponible"),
        )
        for status_code, expected in cases:
            with self.subTest(status_code=status_code):
                response = Mock(status_code=status_code, ok=False)
                response.text = "provider-secret-detail"
                with (
                    patch.dict(os.environ, {"MISTRAL_API_KEY": "test-key"}),
                    patch("digues_webapp.ai.load_dotenv"),
                    patch("digues_webapp.ai.requests.post", return_value=response),
                    self.assertRaises(AiServiceError) as raised,
                ):
                    chat_with_mistral(
                        [{"role": "user", "content": "Bonjour"}], "schema"
                    )
                self.assertIn(expected, str(raised.exception))
                self.assertNotIn(response.text, str(raised.exception))

    def test_mistral_timeout_and_invalid_response_are_transformed(self):
        with (
            patch.dict(os.environ, {"MISTRAL_API_KEY": "test-key"}),
            patch("digues_webapp.ai.load_dotenv"),
            patch(
                "digues_webapp.ai.requests.post",
                side_effect=requests.Timeout(),
            ),
            self.assertRaises(AiServiceError) as timeout,
        ):
            chat_with_mistral(
                [{"role": "user", "content": "Bonjour"}], "schema"
            )
        self.assertEqual(timeout.exception.status_code, 504)

        with (
            patch.dict(os.environ, {"MISTRAL_API_KEY": "test-key"}),
            patch("digues_webapp.ai.load_dotenv"),
            patch(
                "digues_webapp.ai.requests.post",
                side_effect=requests.ConnectionError(),
            ),
            self.assertRaisesRegex(AiServiceError, "Impossible de joindre"),
        ):
            chat_with_mistral(
                [{"role": "user", "content": "Bonjour"}], "schema"
            )

        response = Mock(status_code=200, ok=True)
        response.json.return_value = {"choices": []}
        with (
            patch.dict(os.environ, {"MISTRAL_API_KEY": "test-key"}),
            patch("digues_webapp.ai.load_dotenv"),
            patch("digues_webapp.ai.requests.post", return_value=response),
            self.assertRaisesRegex(AiServiceError, "Réponse invalide"),
        ):
            chat_with_mistral(
                [{"role": "user", "content": "Bonjour"}], "schema"
            )


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
                "/api/ai/chat",
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
        ai_methods = {
            method
            for route in app.routes
            if route.path == "/api/ai/chat"
            for method in route.methods
        }
        self.assertEqual(ai_methods, {"POST"})

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


@unittest.skipIf(app is None, "FastAPI indisponible dans l’environnement de test")
class AiEndpointTest(unittest.TestCase):
    @staticmethod
    def endpoint():
        return next(
            route.endpoint for route in app.routes if route.path == "/api/ai/chat"
        )

    def test_empty_message_is_rejected_without_provider_call(self):
        with patch("digues_webapp.app.chat_with_mistral") as chat:
            with self.assertRaises(ValidationError):
                AiChatRequest(messages=[{"role": "user", "content": "   "}])
        chat.assert_not_called()

    def test_missing_api_key_returns_explicit_safe_error(self):
        with (
            patch.dict(os.environ, {"MISTRAL_API_KEY": ""}),
            patch("digues_webapp.ai.load_dotenv"),
            patch("digues_webapp.ai.requests.post") as post,
            patch("digues_webapp.app.get_ai_schema_context", return_value="schema"),
            self.assertRaises(AiServiceError) as raised,
        ):
            self.endpoint()(AiChatRequest(messages=[
                {"role": "user", "content": "Bonjour"}
            ]))
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            str(raised.exception),
            "L’assistant IA n’est pas configuré sur le serveur.",
        )
        post.assert_not_called()

    def test_endpoint_returns_normalized_answer_and_successful_queries_only(self):
        with (
            patch(
                "digues_webapp.app.chat_with_mistral",
                return_value=AiChatResult(
                    answer="Réponse simulée",
                    executed_queries=("SELECT 1", "SELECT 1"),
                ),
            ) as chat,
            patch(
                "digues_webapp.app.get_ai_schema_context",
                return_value="CONTEXTE SCHEMA",
            ),
        ):
            response = self.endpoint()(AiChatRequest(messages=[
                {"role": "user", "content": " Bonjour "},
                {"role": "assistant", "content": " Bonjour ! "},
                {"role": "user", "content": " Suite "},
            ]))
        self.assertEqual(response, {
            "answer": "Réponse simulée",
            "executed_queries": [{"sql": "SELECT 1"}, {"sql": "SELECT 1"}],
        })
        serialized = json.dumps(response)
        for forbidden in ("columns", "rows", "tool_call_id", "MISTRAL_API_KEY"):
            self.assertNotIn(forbidden, serialized)
        chat.assert_called_once_with(
            [
                {"role": "user", "content": "Bonjour"},
                {"role": "assistant", "content": "Bonjour !"},
                {"role": "user", "content": "Suite"},
            ],
            "CONTEXTE SCHEMA",
        )

    def test_endpoint_returns_empty_query_list_without_tool_call(self):
        with (
            patch(
                "digues_webapp.app.chat_with_mistral",
                return_value=AiChatResult(
                    answer="Réponse directe", executed_queries=()
                ),
            ),
            patch("digues_webapp.app.get_ai_schema_context", return_value="schema"),
        ):
            response = self.endpoint()(AiChatRequest(messages=[
                {"role": "user", "content": "Question générale"}
            ]))
        self.assertEqual(
            response,
            {"answer": "Réponse directe", "executed_queries": []},
        )

    def test_provider_error_is_returned_without_stack_trace(self):
        with (
            patch(
                "digues_webapp.app.chat_with_mistral",
                side_effect=AiServiceError("Impossible de joindre le service IA."),
            ),
            patch("digues_webapp.app.get_ai_schema_context", return_value="schema"),
            self.assertRaises(AiServiceError) as raised,
        ):
            self.endpoint()(AiChatRequest(messages=[
                {"role": "user", "content": "Bonjour"}
            ]))
        handler = app.exception_handlers[AiServiceError]
        response = asyncio.run(handler(None, raised.exception))
        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            json.loads(response.body),
            {"detail": "Impossible de joindre le service IA."},
        )

    def test_schema_error_is_returned_without_database_details(self):
        error = AiSchemaUnavailableError(
            "Le schéma PostgreSQL SIRS est temporairement indisponible."
        )
        handler = app.exception_handlers[AiSchemaUnavailableError]
        response = asyncio.run(handler(None, error))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(json.loads(response.body), {"detail": str(error)})


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

    def test_frontend_has_queries_main_view_and_docked_ai_states(self):
        page = (FRONTEND_DIRECTORY / "index.html").read_text(encoding="utf-8")
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        css = (FRONTEND_DIRECTORY / "css" / "app.css").read_text(encoding="utf-8")

        for expected in (
            'id="toggle-queries"',
            'aria-controls="queries-view"',
            'id="queries-view"',
            "Outil de requêtes — fonctionnalité à venir",
            'id="toggle-ai"',
            'aria-controls="ai-panel"',
            'id="ai-panel"',
            'id="close-ai"',
            'id="ai-conversation"',
            'id="ai-chat-form"',
            'id="ai-message"',
            'id="ai-send"',
        ):
            self.assertIn(expected, page)
        self.assertNotIn("Assistant IA — fonctionnalité à venir", page)

        self.assertIn("function setQueriesViewOpen(open)", script)
        self.assertIn("mapElement.hidden = open", script)
        self.assertIn("queriesView.hidden = !open", script)
        self.assertIn('primaryArea.classList.toggle("queries-open", open)', script)
        self.assertIn("function setAiPanelOpen(open)", script)
        self.assertIn("aiPanel.hidden = !open", script)
        self.assertIn("map.invalidateSize()", script)
        self.assertIn("display: flex", css.split(".app-workspace", 1)[1].split("}", 1)[0])
        self.assertIn("flex: 1 1 auto", css.split(".primary-area", 1)[1].split("}", 1)[0])
        self.assertIn("flex: 0 0 33.333%", css.split(".ai-panel {", 1)[1].split("}", 1)[0])
        self.assertIn("overflow: hidden", css.split(".primary-area", 1)[1].split("}", 1)[0])

    def test_frontend_queries_and_ai_state_transitions_are_independent(self):
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js indisponible pour le test d’état frontend.")
        state_source = "function refreshMapSize" + script.split(
            "function refreshMapSize", 1
        )[1].split("function appendAiMessage", 1)[0]
        program = state_source + """
const mapElement = { hidden: false };
const queriesView = { hidden: true };
const aiPanel = { hidden: true };
const heritagePanel = { hidden: true };
const mapLegend = { hidden: false };
const primaryArea = { classList: { toggle(name, value) { this[name] = value; } } };
const queriesToggleButton = { setAttribute(name, value) { this[name] = value; } };
const aiToggleButton = { setAttribute(name, value) { this[name] = value; } };
let invalidations = 0;
const map = { invalidateSize() { invalidations += 1; } };
const window = { requestAnimationFrame(callback) { callback(); } };
const snapshot = () => ({
  map: !mapElement.hidden,
  queries: !queriesView.hidden,
  ai: !aiPanel.hidden,
  queriesOpen: Boolean(primaryArea.classList["queries-open"]),
});
const states = [snapshot()];
setAiPanelOpen(true);
states.push(snapshot());
setAiPanelOpen(false);
setQueriesViewOpen(true);
states.push(snapshot());
setAiPanelOpen(true);
states.push(snapshot());
setQueriesViewOpen(false);
setAiPanelOpen(false);
states.push(snapshot());
process.stdout.write(JSON.stringify({ states, invalidations }));
"""
        result = json.loads(subprocess.check_output(
            [node, "-e", program], text=True, encoding="utf-8"
        ))
        self.assertEqual(result["states"], [
            {"map": True, "queries": False, "ai": False, "queriesOpen": False},
            {"map": True, "queries": False, "ai": True, "queriesOpen": False},
            {"map": False, "queries": True, "ai": False, "queriesOpen": True},
            {"map": False, "queries": True, "ai": True, "queriesOpen": True},
            {"map": True, "queries": False, "ai": False, "queriesOpen": False},
        ])
        self.assertEqual(result["invalidations"], 4)

    def test_frontend_ai_chat_posts_text_and_renders_with_text_content(self):
        page = (FRONTEND_DIRECTORY / "index.html").read_text(encoding="utf-8")
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        self.assertIn('fetchJson("/api/ai/chat"', script)
        self.assertIn("const aiConversationHistory = []", script)
        self.assertIn("aiConversationHistory.push({ role, content })", script)
        self.assertIn(
            "messages: aiConversationHistory.slice(-AI_HISTORY_MAX_MESSAGES)",
            script,
        )
        self.assertIn("{ error: true, remember: false }", script)
        self.assertIn("aiMessageInput.disabled = pending", script)
        self.assertIn("aiSendButton.disabled = pending", script)
        self.assertIn('event.key === "Enter"', script)
        self.assertIn("body.textContent = content", script)
        self.assertNotIn("body.innerHTML", script)
        self.assertNotIn("MISTRAL_API_KEY", page)
        self.assertNotIn("MISTRAL_API_KEY", script)
        self.assertNotIn("localStorage", script)
        self.assertNotIn("indexedDB", script)

    def test_frontend_renders_safe_collapsible_sql_with_copy_only(self):
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        css = (FRONTEND_DIRECTORY / "css" / "app.css").read_text(encoding="utf-8")
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js indisponible pour le test de rendu IA.")

        render_source = "async function copyTextToClipboard" + script.split(
            "async function copyTextToClipboard", 1
        )[1].split("function setAiRequestPending", 1)[0]
        program = render_source + r'''
class Element {
  constructor(tagName) {
    this.tagName = tagName;
    this.children = [];
    this.listeners = {};
    this.classList = { add: (...names) => { this.classes = names; } };
    this.textContent = "";
    this.open = false;
    this.scrollHeight = 10;
  }
  append(...children) { this.children.push(...children); }
  addEventListener(name, listener) { this.listeners[name] = listener; }
  setAttribute(name, value) { this[name] = value; }
  remove() { this.removed = true; }
  select() { this.selected = true; }
}
const document = {
  body: new Element("body"),
  createElement(tagName) { return new Element(tagName); },
  execCommand(command) { return command === "copy"; },
};
let copiedText = null;
Object.defineProperty(globalThis, "navigator", {
  configurable: true,
  value: { clipboard: { async writeText(text) { copiedText = text; } } },
});
const window = { setTimeout(callback) { callback(); } };
const aiConversation = new Element("conversation");
const aiConversationEmpty = { remove() {} };
const aiConversationHistory = [];

(async () => {
  appendAiMessage("assistant", "Sans SQL");
  const noSqlChildren = aiConversation.children[0].children.length;
  const unsafeSql = "SELECT '<script>alert(1)</script>'";
  appendAiMessage("assistant", "Avec SQL", {
    executedQueries: [{ sql: unsafeSql }],
  });
  appendAiMessage("assistant", "Deux SQL", {
    executedQueries: [{ sql: "SELECT 1" }, { sql: "SELECT 1" }],
  });
  const details = aiConversation.children[1].children[2];
  const query = details.children[1];
  const code = query.children[1].children[0];
  const button = query.children[2];
  await button.listeners.click();
  const multiple = aiConversation.children[2].children[2];
  process.stdout.write(JSON.stringify({
    noSqlChildren,
    detailsTag: details.tagName,
    detailsOpen: details.open,
    summary: details.children[0].textContent,
    code: code.textContent,
    copiedText,
    buttonText: button.textContent,
    multipleQueries: multiple.children.length - 1,
    history: aiConversationHistory,
  }));
})();
'''
        result = json.loads(subprocess.check_output([node, "-e", program], text=True))
        self.assertEqual(result["noSqlChildren"], 2)
        self.assertEqual(result["detailsTag"], "details")
        self.assertFalse(result["detailsOpen"])
        self.assertIn("SQL", result["summary"])
        self.assertIn("1", result["summary"])
        self.assertEqual(result["code"], "SELECT '<script>alert(1)</script>'")
        self.assertEqual(result["copiedText"], result["code"])
        self.assertEqual(result["buttonText"], "Copier")
        self.assertEqual(result["multipleQueries"], 2)
        self.assertEqual(len(result["history"]), 3)
        self.assertTrue(all(set(item) == {"role", "content"} for item in result["history"]))
        self.assertIn('document.createElement("details")', render_source)
        self.assertIn("code.textContent = query.sql", render_source)
        self.assertNotIn("innerHTML", render_source)
        self.assertIn('document.execCommand("copy")', render_source)
        self.assertIn('copyButton.textContent = "Copié"', render_source)
        self.assertNotIn("Exécuter", render_source)
        self.assertNotIn("Ouvrir dans Requêtes", render_source)
        self.assertIn(".ai-sql-details summary", css)

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
            'id="desordre-editor"',
            '<option value="Point">Point</option>',
            '<option value="LineString">LineString</option>',
            '<option value="Polygon">Polygon</option>',
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
        source = (
            Path(__file__).resolve().parents[1]
            / "backend"
            / "digues_webapp"
            / "queries.py"
        ).read_text()
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
        for identifier in ("desordre-create-line-coordinates", "desordre-create-bornage",
                           "polygon-representative-point"):
            self.assertIn(f'id="{identifier}"', page)
        self.assertIn('id="polygon-representative-x" type="text" readonly', page)
        self.assertNotIn('name="line-edit-mode"', page)
        self.assertIn('data-layer-toggle="Polygon"', page)
        self.assertNotIn("L.control.layers", script)
        self.assertIn("map.removeLayer(layer)", script)
        self.assertIn('fetchJson("/api/config")', script)
        self.assertIn("body:not(.show-uuid) .technical-identifier", css)

    def test_disorder_forms_share_visual_components_without_id_selectors(self):
        page = (FRONTEND_DIRECTORY / "index.html").read_text(encoding="utf-8")
        css = (FRONTEND_DIRECTORY / "css" / "app.css").read_text(encoding="utf-8")
        self.assertEqual(page.count('class="disorder-form"'), 1)
        self.assertIn('id="desordre-editor" class="disorder-form"', page)
        self.assertNotIn('id="desordre-create-editor"', page)
        self.assertNotIn('id="point-editor"', page)
        self.assertNotIn('id="line-editor"', page)
        self.assertEqual(page.count('class="form-section"'), 4)
        self.assertIn(
            'id="desordre-localisation" class="form-section localisation-editor"',
            page,
        )
        self.assertIn(
            'id="desordre-create-bornage-end" class="form-section"',
            page,
        )
        self.assertIn(
            'id="desordre-create-geometry" '
            'class="line-geometry-editor geometry-editor"',
            page,
        )
        self.assertIn('id="point-map-editor" hidden', page)
        self.assertIn('id="line-map-editor" hidden', page)
        for common_rule in (
            ".disorder-form label",
            ".disorder-form input",
            ".disorder-form .checkbox-field",
            ".form-section",
            ".form-section > legend",
            ".disorder-form input[readonly]",
            ".geometry-editor",
        ):
            self.assertIn(common_rule, css)
        for obsolete_selector in (
            "#desordre-create-editor label",
            "#point-editor label",
            "#line-editor label",
            "#desordre-create-editor fieldset",
            "#point-editor fieldset",
        ):
            self.assertNotIn(obsolete_selector, css)

    def test_shared_form_styles_preserve_hidden_modes_and_control_ids(self):
        page = (FRONTEND_DIRECTORY / "index.html").read_text(encoding="utf-8")
        css = (FRONTEND_DIRECTORY / "css" / "app.css").read_text(encoding="utf-8")
        hidden_rule = css.split(".disorder-form [hidden]", 1)[1].split("}", 1)[0]
        mode_hidden_rule = css.split(
            ".mode-selector .authority-choice[hidden]", 1
        )[1].split("}", 1)[0]
        self.assertIn("display: none !important", hidden_rule)
        self.assertIn("display: none !important", mode_hidden_rule)
        for identifier in (
            "desordre-create-geometry-type",
            "desordre-mode-selector",
            "polygon-representative-point",
            "bornage-mode",
            "reproject-bornage",
            "save-line-bornage",
        ):
            self.assertEqual(page.count(f'id="{identifier}"'), 1)

    def test_frontend_centralizes_modes_and_never_queries_empty_reperage(self):
        page = (FRONTEND_DIRECTORY / "index.html").read_text(encoding="utf-8")
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        self.assertEqual(page.count('class="disorder-form"'), 1)
        self.assertIn("function availableDisorderModes", script)
        self.assertIn('return ["map"]', script)
        self.assertIn('const modes = ["map", "xy", "lonlat"]', script)
        self.assertIn(".filter(Boolean)", script)
        availability = script.split(
            "async function refreshCreationReperageAvailability", 1
        )[1].split("async function openDesordreCreation", 1)[0]
        self.assertLess(availability.index("if (!eligible)"), availability.index(
            "loadTronconReperageOptions"
        ))
        self.assertIn("requestVersion !== creationReperageRequestVersion", availability)
        self.assertNotIn("Not Found", script)

    def test_disorder_mode_selectors_use_direct_compact_authorities(self):
        page = (FRONTEND_DIRECTORY / "index.html").read_text(encoding="utf-8")
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        css = (FRONTEND_DIRECTORY / "css" / "app.css").read_text(encoding="utf-8")

        def choices(name):
            pattern = (
                rf'<input[^>]*name="{re.escape(name)}"[^>]*value="([^"]+)"[^>]*>'
                rf'\s*([^<]+?)\s*</label>'
            )
            return re.findall(pattern, page)

        expected_full = [
            ("map", "Carto"),
            ("xy", "X/Y"),
            ("lonlat", "Lat/Lon"),
            ("bornage", "Bornage"),
        ]
        self.assertEqual(choices("desordre-mode"), expected_full)
        for obsolete_name in (
            "desordre-point-method", "desordre-line-method",
            "desordre-polygon-method", "coordinate-family", "line-edit-mode",
        ):
            self.assertEqual(choices(obsolete_name), [])

        self.assertNotRegex(
            page,
            r'<input[^>]*type="radio"[^>]*value="coordinates"',
        )
        self.assertNotRegex(page, r'>\s*Coordonnées\s*</(?:label|button)>')
        self.assertIn(
            'desordreCreateLineCrs.value = method === "lonlat" '
            '? "EPSG:4326" : "EPSG:3950"',
            script,
        )
        mode_rule = css.split(".mode-selector {", 1)[1].split("}", 1)[0]
        choice_rule = css.split(
            ".mode-selector .authority-choice {", 1
        )[1].split("}", 1)[0]
        self.assertIn("flex-wrap: nowrap", mode_rule)
        self.assertIn("gap: 0.25rem", mode_rule)
        self.assertIn("padding: 0.45rem 0.35rem", choice_rule)
        self.assertIn("white-space: nowrap", choice_rule)

    def test_single_disorder_editor_routes_state_to_existing_operations(self):
        page = (FRONTEND_DIRECTORY / "index.html").read_text(encoding="utf-8")
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")

        self.assertEqual(page.count('<form id="desordre-editor"'), 1)
        self.assertEqual(page.count('class="disorder-form"'), 1)
        self.assertEqual(
            script.count('desordreEditorForm.addEventListener("submit"'), 1
        )
        for state_field in (
            "mode,", "geometryType,", "objectId,", "data,",
        ):
            self.assertIn(state_field, script.split(
                "function setDisorderEditorState", 1
            )[1].split("}", 1)[0])
        self.assertIn('setDisorderEditorState("create", "Point")', script)
        for geometry_type in ("Point", "LineString", "Polygon"):
            self.assertIn(
                f'prepareDisorderEditorForEdit("{geometry_type}"', script
            )

        self.assertIn('fetchJson("/api/desordres", {', script)
        self.assertIn('saveLineRequest("/endpoints"', script)
        self.assertIn('saveLineRequest("/reperage"', script)
        self.assertIn(')}/geometry`', script)
        self.assertIn(')}/reperage`', script)
        self.assertIn("st_setpoint", inspect.getsource(
            update_line_desordre_endpoints
        ).lower())

        html_ids = set(re.findall(r'id="([^"]+)"', page))
        queried_ids = set(re.findall(
            r'document\.querySelector\("#([^"]+)"\)', script
        ))
        self.assertEqual(queried_ids - html_ids, set())
        for removed_id in (
            "desordre-create-editor", "point-editor", "line-editor",
        ):
            self.assertNotIn(removed_id, page)
            self.assertNotIn(f'#{removed_id}', script)

        create_shell = script.split("async function openDesordreCreation", 1)[1]
        create_shell = create_shell.split("function closeDesordreDraft", 1)[0]
        self.assertIn("editorTabs.hidden = true", create_shell)
        for opener in ("openPointEditor", "openLineEditor"):
            edit_shell = script.split(f"function {opener}", 1)[1]
            edit_shell = edit_shell.split("\n}", 1)[0]
            self.assertIn("editorTabs.hidden = false", edit_shell)
        polygon_shell = script.split("function renderPolygonServerFeature", 1)[1]
        polygon_shell = polygon_shell.split("\n}", 1)[0]
        self.assertIn("editorTabs.hidden = false", polygon_shell)

    def test_create_linestring_bornage_follows_rendered_troncon_cardinality(self):
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        css = (FRONTEND_DIRECTORY / "css" / "app.css").read_text(encoding="utf-8")
        available_source = "function availableDisorderModes" + script.split(
            "function availableDisorderModes", 1
        )[1].split("function setModeChoiceAvailability", 1)[0]
        choice_source = "function setModeChoiceAvailability" + script.split(
            "function setModeChoiceAvailability", 1
        )[1].split("function creationBornageChoiceState", 1)[0]
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
        renderer = script.split("function renderDisorderModeChoices", 1)[1].split(
            "function updateLineCoordinateLabels", 1
        )[0]
        self.assertIn("desordreBornageChoice", renderer)
        selection_handler = script.split(
            'desordreCreateTroncons.addEventListener("change"', 1
        )[1].split('startDesordreDrawButton.addEventListener', 1)[0]
        self.assertLess(
            selection_handler.index("renderDisorderModeChoices(false)"),
            selection_handler.index("refreshCreationReperageAvailability()"),
        )
        payload_builder = script.split("function buildDesordreCreationPayload", 1)[1]
        payload_builder = payload_builder.split(
            'function configureDesordreLayer', 1
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
        renderer = script.split("function renderDisorderModeChoices", 1)[1].split(
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
            'name="desordre-mode" value="bornage"',
            'id="desordre-create-troncons"',
            'id="line-reperage-summary"',
            'id="desordre-create-borne-start"',
            'id="desordre-create-distance-start"',
            'id="desordre-create-sense-start"',
        ):
            self.assertIn(identifier, page)
        main_context = page.split('id="desordre-create-bornage"', 1)[0]
        bornage_panel = page.split('id="desordre-create-bornage"', 1)[1].split(
            "</section>", 1
        )[0]
        self.assertIn("Tronçons concernés", main_context)
        self.assertIn("Repérage actuel", main_context)
        self.assertNotIn("Tronçon associé", bornage_panel)
        self.assertNotIn("Système de repérage", bornage_panel)
        self.assertNotIn("PR calculé", bornage_panel)
        for editable_label in ("Borne", "Distance (m)", "Sens"):
            self.assertIn(editable_label, bornage_panel)
        self.assertIn("buildPointReperagePayload", script)
        self.assertIn("borne_debut_id: reperageFields.borne.value", script)
        self.assertIn("distance_debut_m: distance", script)
        self.assertIn("position_debut_relative: reperageFields.sens.value", script)
        self.assertIn("currentReperage = reperage", script)
        self.assertIn("options.systeme_reperage_id", script)
        self.assertIn("/reperage`", script)
        self.assertIn("renderPointServerFeature(feature)", script)
        self.assertIn("updatePointLayer(feature)", script)

    def test_reproject_buttons_and_warnings_match_editable_geometry_types(self):
        page = (FRONTEND_DIRECTORY / "index.html").read_text(encoding="utf-8")
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        bornage_actions = page.split('id="desordre-bornage-actions"', 1)[1].split(
            "</section>", 1
        )[0]
        self.assertIn('id="reproject-bornage"', bornage_actions)
        self.assertLess(
            bornage_actions.index('id="reproject-bornage"'),
            bornage_actions.index('id="save-line-bornage"'),
        )
        self.assertEqual(page.count('>Reprojeter</button>'), 1)
        self.assertIn("modifier le bornage repositionne le point", page)
        self.assertIn("Les sommets de la géométrie actuelle sont perdus", page)
        self.assertIn(
            'desordreBornageActions.hidden = !editing || method !== "bornage"',
            script,
        )
        self.assertIn("desordreEditorForm.requestSubmit()", script)
        self.assertIn("applyLineReperage", script)
        polygon_editor = script.split("function renderPolygonServerFeature", 1)[1].split(
            "desordreEditorForm.addEventListener", 1
        )[0]
        self.assertIn('prepareDisorderEditorForEdit("Polygon"', polygon_editor)
        self.assertIn("renderDisorderModeChoices(false)", polygon_editor)

    def test_reproject_actions_use_current_payload_without_dirty_check(self):
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        handler = script.split(
            'reprojectBornageButton.addEventListener("click"', 1
        )[1].split("saveLineBornageButton.addEventListener", 1)[0]
        self.assertIn("desordreEditorForm.requestSubmit(", handler)
        self.assertIn("applyLineReperage", handler)
        self.assertNotIn("initialFormValues", handler)
        self.assertNotIn("initialLineReperageValues", handler)

    def test_frontend_has_explicit_linestring_editing_without_drag_writes(self):
        page = (FRONTEND_DIRECTORY / "index.html").read_text(encoding="utf-8")
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")
        self.assertIn("leaflet-editable@1.2.0", page)
        for identifier in (
            'id="desordre-editor"',
            'id="start-line-edit"',
            'id="validate-line-edit"',
            'id="cancel-line-edit"',
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

    def test_disorder_geometry_type_and_reperage_labels_remain_stable(self):
        page = (FRONTEND_DIRECTORY / "index.html").read_text(encoding="utf-8")
        script = (FRONTEND_DIRECTORY / "js" / "map.js").read_text(encoding="utf-8")

        self.assertIn("Type de géométrie", page)
        for geometry_type in ("Point", "LineString", "Polygon"):
            self.assertIn(
                f'<option value="{geometry_type}">{geometry_type}</option>',
                page,
            )
        self.assertNotIn("Nombre de sommets", page)
        self.assertNotIn('id="line-vertex-count"', page)
        self.assertNotIn("Repérage relu", page)
        self.assertIn("Repérage actuel", page)
        self.assertNotIn("vertexCount", script)

        renderer = script.split("function renderLineServerFeature", 1)[1].split(
            "function lineBornageDraftModified", 1
        )[0]
        self.assertIn(
            "disorderFields.geometryType.value = feature.geometry.type;",
            renderer,
        )
        self.assertNotIn("properties.type_geometrie", renderer)
        self.assertIn("disorderFields.reperage.value", renderer)

        point_renderer = script.split("function renderPointServerFeature", 1)[1].split(
            "function lineReperageSummary", 1
        )[0]
        self.assertIn(
            "disorderFields.reperage.value = lineReperageSummary(properties.reperage);",
            point_renderer,
        )
        controls = script.split("function updateDisorderEditorControls", 1)[1].split(
            "async function refreshCreationReperageAvailability", 1
        )[0]
        self.assertIn(
            "desordreLineDerived.hidden = !editing || (!point && !line);",
            controls,
        )


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
                Path(__file__).resolve().parents[2] / "config.env",
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

    def test_ai_introspection_matches_current_postgis_business_catalog(self):
        columns, primary_keys, foreign_keys = introspect_ai_schema(self.connection)
        relation_names = {(row[0], row[1], row[2]) for row in columns}
        self.assertIn(("public", "systemes", "TABLE"), relation_names)
        self.assertIn(("public", "view_desordres_points_saisie", "VIEW"), relation_names)
        self.assertNotIn(("public", "spatial_ref_sys", "TABLE"), relation_names)
        self.assertTrue(any(row[:3] == ("public", "systemes", "id") for row in primary_keys))
        self.assertTrue(any(
            row[:6] == (
                "public", "troncons", "digue_id", "public", "digues", "id"
            )
            for row in foreign_keys
        ))
        geometry_types = {
            row[4] for row in columns if row[3] == "geometry"
        }
        self.assertIn("geometry(LineString,3950)", geometry_types)

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
