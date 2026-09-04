"""Adaptateur Mistral avec consultation SQL SIRS strictement en lecture seule."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from .prompts import SIRS_SYSTEM_PROMPT
from .readonly_sql import (
    ReadonlySqlExecutionError,
    ReadonlySqlValidationError,
    execute_readonly_query,
)


LOGGER = logging.getLogger(__name__)
CONFIG_ENV_PATH = Path(__file__).resolve().parents[3] / "config.env"
MISTRAL_CHAT_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "mistral-small-latest"
MISTRAL_TIMEOUT_SECONDS = 30
MISTRAL_MAX_TOOL_CALLS = 5
SIRS_SQL_TOOL_NAME = "query_sirs_database"
SIRS_SQL_TOOL = {
    "type": "function",
    "function": {
        "name": SIRS_SQL_TOOL_NAME,
        "description": (
            "Consulte la base PostgreSQL/PostGIS SIRS courante en lecture seule. "
            "Utilise exclusivement le schéma fourni comme source de vérité. "
            "SELECT, WITH/CTE, jointures, agrégations et fonctions PostGIS de "
            "lecture sont autorisés. Toute écriture ou modification du schéma "
            "est refusée par le serveur. Un résultat avec truncated=true est "
            "incomplet et ne représente pas toutes les lignes correspondantes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "Requête PostgreSQL/PostGIS de lecture à exécuter.",
                }
            },
            "required": ["sql"],
            "additionalProperties": False,
        },
    },
}


class AiServiceError(RuntimeError):
    """Erreur de service IA présentable sans détail sensible."""

    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class AiChatResult:
    """Réponse textuelle et SQL exécutés avec succès pour cette seule requête."""

    answer: str
    executed_queries: tuple[str, ...]


def _api_key() -> str:
    load_dotenv(CONFIG_ENV_PATH, override=False)
    api_key = os.getenv("MISTRAL_API_KEY", "").strip()
    if not api_key:
        raise AiServiceError(
            "L’assistant IA n’est pas configuré sur le serveur.",
            status_code=503,
        )
    return api_key


def _message_from_response(payload: Any) -> dict[str, Any]:
    try:
        message = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AiServiceError("Réponse invalide du service IA.") from exc
    if not isinstance(message, dict):
        raise AiServiceError("Réponse invalide du service IA.")
    return message


def _answer_from_message(message: dict[str, Any]) -> str:
    content = message.get("content")

    if isinstance(content, str):
        answer = content.strip()
    elif isinstance(content, list):
        answer = "".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ).strip()
    else:
        answer = ""
    if not answer:
        raise AiServiceError("Réponse invalide du service IA.")
    return answer


def _completion(
    mistral_messages: list[dict[str, Any]],
    *,
    api_key: str,
    tool_choice: str,
) -> dict[str, Any]:
    try:
        response = requests.post(
            MISTRAL_CHAT_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": MISTRAL_MODEL,
                "messages": mistral_messages,
                "tools": [SIRS_SQL_TOOL],
                "tool_choice": tool_choice,
                "parallel_tool_calls": True,
            },
            timeout=MISTRAL_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        LOGGER.warning("Délai d’attente Mistral dépassé")
        raise AiServiceError(
            "Le service IA n’a pas répondu à temps.", status_code=504
        ) from exc
    except requests.RequestException as exc:
        LOGGER.warning("Connexion à Mistral impossible: %s", type(exc).__name__)
        raise AiServiceError("Impossible de joindre le service IA.") from exc

    if response.status_code in {401, 403}:
        LOGGER.warning("Authentification Mistral refusée (HTTP %s)", response.status_code)
        raise AiServiceError("Authentification du service IA refusée.")
    if response.status_code == 429:
        LOGGER.warning("Limite Mistral atteinte (HTTP 429)")
        raise AiServiceError(
            "Le quota ou la limite de débit du service IA est atteint.",
            status_code=503,
        )
    if response.status_code >= 500:
        LOGGER.warning("Erreur serveur Mistral (HTTP %s)", response.status_code)
        raise AiServiceError("Le service IA est temporairement indisponible.")
    if not response.ok:
        LOGGER.warning("Requête Mistral refusée (HTTP %s)", response.status_code)
        raise AiServiceError("Impossible d’obtenir une réponse de l’assistant.")

    try:
        payload = response.json()
    except ValueError as exc:
        LOGGER.warning("Réponse Mistral non JSON")
        raise AiServiceError("Réponse invalide du service IA.") from exc
    return _message_from_response(payload)


def _tool_error(message: str) -> dict[str, Any]:
    return {"ok": False, "error": message}


def _run_sql_tool(
    tool_call: dict[str, Any],
) -> tuple[str, dict[str, Any], str | None]:
    try:
        function = tool_call["function"]
        name = function["name"]
        arguments_json = function["arguments"]
    except (KeyError, TypeError) as exc:
        raise AiServiceError("Réponse d’outil invalide du service IA.") from exc

    if not isinstance(name, str) or not name:
        raise AiServiceError("Réponse d’outil invalide du service IA.")
    if name != SIRS_SQL_TOOL_NAME:
        return name, _tool_error("Outil non autorisé."), None
    if not isinstance(arguments_json, str):
        return (
            name,
            _tool_error("Arguments JSON invalides pour l’outil de lecture."),
            None,
        )
    try:
        arguments = json.loads(arguments_json)
    except (TypeError, ValueError):
        return name, _tool_error("Arguments JSON invalides pour l’outil de lecture."), None
    if not isinstance(arguments, dict) or set(arguments) != {"sql"}:
        return (
            name,
            _tool_error("L’argument sql est obligatoire et doit être unique."),
            None,
        )
    sql = arguments["sql"]
    if not isinstance(sql, str) or not sql.strip():
        return name, _tool_error("L’argument sql doit être une chaîne non vide."), None

    try:
        return name, execute_readonly_query(sql), sql
    except ReadonlySqlValidationError:
        return (
            name,
            _tool_error(
                "La requête de lecture a été refusée par la politique de sécurité."
            ),
            None,
        )
    except ReadonlySqlExecutionError as exc:
        error = (
            "La requête de lecture a dépassé le délai autorisé."
            if exc.timed_out
            else "La requête de lecture a échoué."
        )
        return name, _tool_error(error), None
    except Exception as exc:  # protection de frontière, sans fuite vers le navigateur
        LOGGER.error("Échec interne de l’outil SQL: %s", type(exc).__name__)
        return name, _tool_error("La requête de lecture a échoué."), None


def chat_with_mistral(
    messages: list[dict[str, str]], schema_context: str
) -> AiChatResult:
    """Envoie l'historique validé avec le contexte système SIRS."""

    mistral_messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": f"{SIRS_SYSTEM_PROMPT}\n\n{schema_context}",
        },
        *messages,
    ]

    api_key = _api_key()
    tool_call_count = 0
    force_final_answer = False
    executed_queries: list[str] = []

    while True:
        message = _completion(
            mistral_messages,
            api_key=api_key,
            tool_choice="none" if force_final_answer else "auto",
        )
        tool_calls = message.get("tool_calls") or []
        if not isinstance(tool_calls, list):
            raise AiServiceError("Réponse d’outil invalide du service IA.")
        if not tool_calls:
            return AiChatResult(
                answer=_answer_from_message(message),
                executed_queries=tuple(executed_queries),
            )
        if force_final_answer:
            raise AiServiceError(
                "L’assistant n’a pas pu finaliser sa réponse après les consultations."
            )

        normalized_calls: list[dict[str, Any]] = []
        tool_results: list[dict[str, Any]] = []
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                raise AiServiceError("Réponse d’outil invalide du service IA.")
            if tool_call.get("type") != "function":
                raise AiServiceError("Type d’outil non autorisé par le serveur.")
            tool_call_id = tool_call.get("id")
            if not isinstance(tool_call_id, str) or not tool_call_id:
                raise AiServiceError("Réponse d’outil invalide du service IA.")
            function = tool_call.get("function")
            if not isinstance(function, dict):
                raise AiServiceError("Réponse d’outil invalide du service IA.")
            function_name = function.get("name")
            if not isinstance(function_name, str) or not function_name:
                raise AiServiceError("Réponse d’outil invalide du service IA.")

            if tool_call_count >= MISTRAL_MAX_TOOL_CALLS:
                result = _tool_error(
                    "Limite de consultations SQL atteinte pour cette question."
                )
            else:
                tool_call_count += 1
                function_name, result, executed_sql = _run_sql_tool(tool_call)
                if executed_sql is not None:
                    executed_queries.append(executed_sql)

            normalized_calls.append({
                "id": tool_call_id,
                "type": "function",
                "function": function,
            })
            tool_results.append({
                "role": "tool",
                "name": function_name,
                "content": json.dumps(
                    result, ensure_ascii=False, separators=(",", ":")
                ),
                "tool_call_id": tool_call_id,
            })

        mistral_messages.append({
            "role": "assistant",
            "content": message.get("content") or "",
            "tool_calls": normalized_calls,
        })
        mistral_messages.extend(tool_results)
        if tool_call_count >= MISTRAL_MAX_TOOL_CALLS:
            force_final_answer = True
