import json
import os
import unittest
from unittest.mock import Mock, call, patch

from sirs_webapp.ai import (
    MISTRAL_MAX_TOOL_CALLS,
    SIRS_SQL_TOOL,
    SIRS_SQL_TOOL_NAME,
    AiServiceError,
    chat_with_mistral,
)
from sirs_webapp.readonly_sql import (
    ReadonlySqlValidationError,
    execute_readonly_query,
)


def mistral_response(message):
    response = Mock(status_code=200, ok=True)
    response.json.return_value = {"choices": [{"message": message}]}
    return response


def tool_call(tool_call_id, arguments, *, name=SIRS_SQL_TOOL_NAME):
    return {
        "id": tool_call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


class MistralSqlToolTest(unittest.TestCase):
    def chat(self, responses):
        return (
            patch.dict(os.environ, {"MISTRAL_API_KEY": "test-key"}),
            patch("sirs_webapp.ai.load_dotenv"),
            patch("sirs_webapp.ai.requests.post", side_effect=responses),
        )

    def test_direct_answer_does_not_execute_sql(self):
        response = mistral_response({
            "role": "assistant",
            "content": "Réponse générale sans consultation.",
        })
        environment, dotenv, post = self.chat([response])
        with (
            environment,
            dotenv,
            post as mocked_post,
            patch("sirs_webapp.ai.execute_readonly_query") as execute,
        ):
            answer = chat_with_mistral(
                [{"role": "user", "content": "Qu’est-ce qu’une digue ?"}],
                "<schema></schema>",
            )

        self.assertEqual(answer.answer, "Réponse générale sans consultation.")
        self.assertEqual(answer.executed_queries, ())
        execute.assert_not_called()
        request = mocked_post.call_args.kwargs["json"]
        self.assertEqual(request["tools"], [SIRS_SQL_TOOL])
        self.assertEqual(request["tool_choice"], "auto")
        self.assertTrue(request["parallel_tool_calls"])
        system_prompt = request["messages"][0]["content"]
        self.assertIn("query_sirs_database", system_prompt)
        self.assertIn("ne devine jamais une valeur", system_prompt)
        self.assertIn("réellement été exécuté avec succès", system_prompt)
        parameters = SIRS_SQL_TOOL["function"]["parameters"]
        self.assertEqual(parameters["required"], ["sql"])
        self.assertFalse(parameters["additionalProperties"])

    def test_simple_sql_call_is_returned_to_mistral_with_matching_id(self):
        first = mistral_response({
            "role": "assistant",
            "content": "",
            "tool_calls": [tool_call("call-1", '{"sql":"SELECT id FROM public.systemes"}')],
        })
        final = mistral_response({
            "role": "assistant",
            "content": "Un système a été trouvé.",
        })
        result = {"columns": ["id"], "rows": [["systeme-1"]], "truncated": False}
        environment, dotenv, post = self.chat([first, final])
        with (
            environment,
            dotenv,
            post as mocked_post,
            patch(
                "sirs_webapp.ai.execute_readonly_query", return_value=result
            ) as execute,
        ):
            answer = chat_with_mistral(
                [{"role": "user", "content": "Quels systèmes existent ?"}],
                "schema",
            )

        self.assertEqual(answer.answer, "Un système a été trouvé.")
        self.assertEqual(
            answer.executed_queries,
            ("SELECT id FROM public.systemes",),
        )
        execute.assert_called_once_with("SELECT id FROM public.systemes")
        self.assertEqual(mocked_post.call_count, 2)
        second_messages = mocked_post.call_args_list[1].kwargs["json"]["messages"]
        assistant = second_messages[-2]
        tool = second_messages[-1]
        self.assertEqual(assistant["tool_calls"][0]["id"], "call-1")
        self.assertEqual(tool["role"], "tool")
        self.assertEqual(tool["name"], SIRS_SQL_TOOL_NAME)
        self.assertEqual(tool["tool_call_id"], "call-1")
        self.assertEqual(json.loads(tool["content"]), result)

    def test_aggregation_and_truncation_are_preserved_in_tool_results(self):
        first = mistral_response({
            "role": "assistant",
            "content": "",
            "tool_calls": [
                tool_call("aggregate", '{"sql":"SELECT COUNT(*) FROM public.systemes"}'),
                tool_call("details", '{"sql":"SELECT * FROM public.troncons"}'),
            ],
        })
        final = mistral_response({"role": "assistant", "content": "Synthèse."})
        results = [
            {"columns": ["count"], "rows": [[42]], "truncated": False},
            {"columns": ["id"], "rows": [["t1"]], "truncated": True},
        ]
        environment, dotenv, post = self.chat([first, final])
        with (
            environment,
            dotenv,
            post as mocked_post,
            patch("sirs_webapp.ai.execute_readonly_query", side_effect=results) as execute,
        ):
            answer = chat_with_mistral(
                [{"role": "user", "content": "Compte et détaille."}], "schema"
            )

        self.assertEqual(answer.answer, "Synthèse.")
        self.assertEqual(
            answer.executed_queries,
            (
                "SELECT COUNT(*) FROM public.systemes",
                "SELECT * FROM public.troncons",
            ),
        )
        self.assertEqual(execute.call_count, 2)
        messages = mocked_post.call_args_list[1].kwargs["json"]["messages"]
        tool_messages = [message for message in messages if message["role"] == "tool"]
        self.assertEqual(
            [message["tool_call_id"] for message in tool_messages],
            ["aggregate", "details"],
        )
        self.assertEqual(json.loads(tool_messages[0]["content"]), results[0])
        self.assertTrue(json.loads(tool_messages[1]["content"])["truncated"])

    def test_refused_sql_returns_controlled_tool_error(self):
        first = mistral_response({
            "role": "assistant",
            "content": "",
            "tool_calls": [tool_call("write", '{"sql":"UPDATE public.systemes SET valid=false"}')],
        })
        final = mistral_response({
            "role": "assistant",
            "content": "Je ne peux pas modifier les données.",
        })
        environment, dotenv, post = self.chat([first, final])
        with (
            environment,
            dotenv,
            post as mocked_post,
            patch(
                "sirs_webapp.ai.execute_readonly_query",
                side_effect=ReadonlySqlValidationError("UPDATE interdit"),
            ) as execute,
        ):
            answer = chat_with_mistral(
                [{"role": "user", "content": "Modifie les systèmes."}], "schema"
            )

        self.assertEqual(answer.answer, "Je ne peux pas modifier les données.")
        self.assertEqual(answer.executed_queries, ())
        execute.assert_called_once()
        tool = mocked_post.call_args_list[1].kwargs["json"]["messages"][-1]
        error = json.loads(tool["content"])
        self.assertFalse(error["ok"])
        self.assertIn("politique de sécurité", error["error"])
        self.assertNotIn("UPDATE interdit", tool["content"])

    def test_unknown_tool_is_refused_without_execution(self):
        first = mistral_response({
            "role": "assistant",
            "content": "",
            "tool_calls": [tool_call("unknown", "{}", name="delete_everything")],
        })
        final = mistral_response({"role": "assistant", "content": "Outil refusé."})
        environment, dotenv, post = self.chat([first, final])
        with (
            environment,
            dotenv,
            post as mocked_post,
            patch("sirs_webapp.ai.execute_readonly_query") as execute,
        ):
            answer = chat_with_mistral(
                [{"role": "user", "content": "Test"}], "schema"
            )

        execute.assert_not_called()
        self.assertEqual(answer.executed_queries, ())
        tool = mocked_post.call_args_list[1].kwargs["json"]["messages"][-1]
        self.assertEqual(tool["name"], "delete_everything")
        self.assertEqual(json.loads(tool["content"])["error"], "Outil non autorisé.")

    def test_invalid_arguments_are_reported_without_execution(self):
        cases = ("{", "{}", '{"sql":12}', '{"sql":"   "}', '{"sql":"SELECT 1","extra":true}')
        for index, arguments in enumerate(cases):
            with self.subTest(arguments=arguments):
                first = mistral_response({
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [tool_call(f"invalid-{index}", arguments)],
                })
                final = mistral_response({"role": "assistant", "content": "Corrigé."})
                environment, dotenv, post = self.chat([first, final])
                with (
                    environment,
                    dotenv,
                    post as mocked_post,
                    patch("sirs_webapp.ai.execute_readonly_query") as execute,
                ):
                    answer = chat_with_mistral(
                        [{"role": "user", "content": "Test"}], "schema"
                    )
                execute.assert_not_called()
                self.assertEqual(answer.executed_queries, ())
                tool = mocked_post.call_args_list[1].kwargs["json"]["messages"][-1]
                self.assertFalse(json.loads(tool["content"])["ok"])

    def test_successive_tool_rounds_are_supported(self):
        responses = [
            mistral_response({
                "role": "assistant", "content": "",
                "tool_calls": [tool_call("first", '{"sql":"SELECT 1"}')],
            }),
            mistral_response({
                "role": "assistant", "content": "",
                "tool_calls": [tool_call("second", '{"sql":"SELECT 2"}')],
            }),
            mistral_response({"role": "assistant", "content": "Terminé."}),
        ]
        environment, dotenv, post = self.chat(responses)
        with (
            environment,
            dotenv,
            post as mocked_post,
            patch(
                "sirs_webapp.ai.execute_readonly_query",
                side_effect=[
                    {"columns": ["one"], "rows": [[1]], "truncated": False},
                    {"columns": ["two"], "rows": [[2]], "truncated": False},
                ],
            ) as execute,
        ):
            answer = chat_with_mistral(
                [{"role": "user", "content": "Deux analyses."}], "schema"
            )

        self.assertEqual(answer.answer, "Terminé.")
        self.assertEqual(answer.executed_queries, ("SELECT 1", "SELECT 2"))
        self.assertEqual(execute.call_args_list, [call("SELECT 1"), call("SELECT 2")])
        self.assertEqual(mocked_post.call_count, 3)

    def test_tool_loop_is_capped_then_final_answer_is_forced(self):
        responses = [
            mistral_response({
                "role": "assistant", "content": "",
                "tool_calls": [tool_call(f"call-{index}", '{"sql":"SELECT 1"}')],
            })
            for index in range(MISTRAL_MAX_TOOL_CALLS)
        ] + [mistral_response({"role": "assistant", "content": "Réponse bornée."})]
        environment, dotenv, post = self.chat(responses)
        with (
            environment,
            dotenv,
            post as mocked_post,
            patch(
                "sirs_webapp.ai.execute_readonly_query",
                return_value={"columns": ["one"], "rows": [[1]], "truncated": False},
            ) as execute,
        ):
            answer = chat_with_mistral(
                [{"role": "user", "content": "Boucle."}], "schema"
            )

        self.assertEqual(answer.answer, "Réponse bornée.")
        self.assertEqual(
            answer.executed_queries,
            tuple("SELECT 1" for _ in range(MISTRAL_MAX_TOOL_CALLS)),
        )
        self.assertEqual(execute.call_count, MISTRAL_MAX_TOOL_CALLS)
        self.assertEqual(mocked_post.call_count, MISTRAL_MAX_TOOL_CALLS + 1)
        self.assertTrue(all(
            item.kwargs["json"]["tool_choice"] == "auto"
            for item in mocked_post.call_args_list[:-1]
        ))
        self.assertEqual(
            mocked_post.call_args_list[-1].kwargs["json"]["tool_choice"], "none"
        )


class MistralSqlToolPostGISIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            execute_readonly_query("SELECT COUNT(*) FROM public.systemes")
        except Exception as exc:
            raise unittest.SkipTest(f"PostgreSQL local indisponible : {exc}")

    def test_simulated_tool_call_executes_a_real_postgresql_select(self):
        responses = [
            mistral_response({
                "role": "assistant", "content": "",
                "tool_calls": [tool_call(
                    "real-select",
                    '{"sql":"SELECT COUNT(*) AS total FROM public.systemes"}',
                )],
            }),
            mistral_response({
                "role": "assistant", "content": "Le comptage a été effectué."
            }),
        ]
        with (
            patch.dict(os.environ, {"MISTRAL_API_KEY": "test-key"}),
            patch("sirs_webapp.ai.load_dotenv"),
            patch("sirs_webapp.ai.requests.post", side_effect=responses) as post,
        ):
            answer = chat_with_mistral(
                [{"role": "user", "content": "Combien de systèmes ?"}], "schema"
            )

        self.assertEqual(answer.answer, "Le comptage a été effectué.")
        self.assertEqual(
            answer.executed_queries,
            ("SELECT COUNT(*) AS total FROM public.systemes",),
        )
        tool = post.call_args_list[1].kwargs["json"]["messages"][-1]
        result = json.loads(tool["content"])
        self.assertEqual(result["columns"], ["total"])
        self.assertEqual(len(result["rows"]), 1)
        self.assertFalse(result["truncated"])


if __name__ == "__main__":
    unittest.main()
