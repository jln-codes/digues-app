"""Moteur partagé d'exécution SQL PostgreSQL strictement en lecture seule."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import date, datetime, time
from decimal import Decimal
import json
import logging
from time import monotonic
from typing import Any
from uuid import UUID, uuid4

from .database import open_read_connection


READONLY_SQL_STATEMENT_TIMEOUT_MS = 30_000
READONLY_SQL_MAX_ROWS = 1_000
READONLY_SQL_MAX_RESULT_BYTES = 1_000_000
READONLY_SQL_FETCH_SIZE = 100

_FORBIDDEN_KEYWORDS = frozenset({
    "ALTER", "ANALYZE", "CALL", "CLUSTER", "COMMENT", "COPY", "CREATE",
    "DELETE", "DO", "DROP", "GRANT", "INSERT", "INTO", "LOCK", "MERGE",
    "REFRESH", "REINDEX", "REVOKE", "SHARE", "TRUNCATE", "UPDATE", "VACUUM",
})
_FORBIDDEN_FUNCTIONS = frozenset({
    "LO_EXPORT", "LO_IMPORT", "NEXTVAL", "PG_ADVISORY_LOCK",
    "PG_ADVISORY_LOCK_SHARED", "PG_ADVISORY_UNLOCK",
    "PG_ADVISORY_UNLOCK_ALL", "PG_CANCEL_BACKEND", "PG_RELOAD_CONF",
    "PG_TERMINATE_BACKEND", "PG_TRY_ADVISORY_LOCK",
    "PG_TRY_ADVISORY_LOCK_SHARED", "PG_ADVISORY_XACT_LOCK",
    "PG_ADVISORY_XACT_LOCK_SHARED", "PG_TRY_ADVISORY_XACT_LOCK",
    "PG_TRY_ADVISORY_XACT_LOCK_SHARED", "PG_NOTIFY", "SET_CONFIG", "SETVAL",
})

logger = logging.getLogger(__name__)


class ReadonlySqlValidationError(ValueError):
    """Requête refusée avant son envoi à PostgreSQL."""


class ReadonlySqlExecutionError(RuntimeError):
    """Échec contrôlé d'une requête de lecture."""

    def __init__(self, message: str, *, timed_out: bool = False) -> None:
        super().__init__(message)
        self.timed_out = timed_out


def _tokens(sql: str) -> list[tuple[str, int]]:
    """Extrait les mots et séparateurs hors chaînes, identifiants et commentaires."""

    tokens: list[tuple[str, int]] = []
    index = 0
    depth = 0
    length = len(sql)
    while index < length:
        char = sql[index]
        following = sql[index + 1] if index + 1 < length else ""

        if char.isspace():
            index += 1
            continue
        if char == "-" and following == "-":
            newline = sql.find("\n", index + 2)
            index = length if newline < 0 else newline + 1
            continue
        if char == "/" and following == "*":
            comment_depth = 1
            index += 2
            while index < length and comment_depth:
                pair = sql[index:index + 2]
                if pair == "/*":
                    comment_depth += 1
                    index += 2
                elif pair == "*/":
                    comment_depth -= 1
                    index += 2
                else:
                    index += 1
            if comment_depth:
                raise ReadonlySqlValidationError("Commentaire SQL non terminé.")
            continue
        if char == "'":
            index += 1
            while index < length:
                if sql[index] == "'":
                    if index + 1 < length and sql[index + 1] == "'":
                        index += 2
                        continue
                    index += 1
                    break
                index += 1
            else:
                raise ReadonlySqlValidationError("Chaîne SQL non terminée.")
            continue
        if char == '"':
            index += 1
            while index < length:
                if sql[index] == '"':
                    if index + 1 < length and sql[index + 1] == '"':
                        index += 2
                        continue
                    index += 1
                    break
                index += 1
            else:
                raise ReadonlySqlValidationError("Identifiant SQL non terminé.")
            continue
        if char == "$":
            tag_end = sql.find("$", index + 1)
            if tag_end >= 0:
                tag = sql[index:tag_end + 1]
                tag_body = tag[1:-1]
                valid_tag = (
                    not tag_body
                    or (
                        (tag_body[0].isalpha() or tag_body[0] == "_")
                        and tag_body.replace("_", "a").isalnum()
                    )
                )
                if valid_tag:
                    value_end = sql.find(tag, tag_end + 1)
                    if value_end < 0:
                        raise ReadonlySqlValidationError(
                            "Chaîne SQL dollar-quotée non terminée."
                        )
                    index = value_end + len(tag)
                    continue
        if char == "(":
            tokens.append((char, depth))
            depth += 1
            index += 1
            continue
        if char == ")":
            depth -= 1
            if depth < 0:
                raise ReadonlySqlValidationError("Parenthèses SQL déséquilibrées.")
            tokens.append((char, depth))
            index += 1
            continue
        if char == ";":
            tokens.append((char, depth))
            index += 1
            continue
        if char.isalpha() or char == "_":
            end = index + 1
            while end < length and (sql[end].isalnum() or sql[end] in "_$"):
                end += 1
            tokens.append((sql[index:end].upper(), depth))
            index = end
            continue
        index += 1

    if depth:
        raise ReadonlySqlValidationError("Parenthèses SQL déséquilibrées.")
    return tokens


def validate_readonly_sql(sql: str) -> str:
    """Valide une instruction SELECT/CTE unique sans la réécrire."""

    if not isinstance(sql, str) or not sql.strip():
        raise ReadonlySqlValidationError("Une requête SQL non vide est requise.")

    tokens = _tokens(sql)
    if not tokens:
        raise ReadonlySqlValidationError("Une requête SQL non vide est requise.")
    semicolons = [position for position, token in enumerate(tokens) if token[0] == ";"]
    if semicolons:
        if len(semicolons) != 1 or semicolons[0] != len(tokens) - 1:
            raise ReadonlySqlValidationError("Une seule instruction SQL est autorisée.")
        tokens.pop()
    if not tokens:
        raise ReadonlySqlValidationError("Une requête SQL non vide est requise.")

    words = [token for token, _depth in tokens if token not in {"(", ")"}]
    if not words:
        raise ReadonlySqlValidationError(
            "Seules les requêtes SELECT et WITH … SELECT sont autorisées."
        )
    forbidden = next((word for word in words if word in _FORBIDDEN_KEYWORDS), None)
    if forbidden:
        raise ReadonlySqlValidationError(f"Opération SQL interdite : {forbidden}.")
    forbidden_function = next(
        (word for word in words if word in _FORBIDDEN_FUNCTIONS), None
    )
    if forbidden_function:
        raise ReadonlySqlValidationError(
            f"Fonction SQL à effet de bord interdite : {forbidden_function}."
        )

    first = words[0]
    if first == "SELECT":
        return sql.strip()
    if first == "WITH" and any(
        token == "SELECT" and depth == 0 for token, depth in tokens
    ):
        return sql.strip()
    raise ReadonlySqlValidationError(
        "Seules les requêtes SELECT et WITH … SELECT sont autorisées."
    )


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, (bytes, bytearray)):
        return "\\x" + bytes(value).hex()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    # Les types non JSON, dont geometry si aucun loader n'est configuré,
    # restent consultables sous la représentation textuelle fournie par psycopg.
    return str(value)


def _row_size(row: list[Any]) -> int:
    return len(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


ConnectionFactory = Callable[[], AbstractContextManager[Any]]


def execute_readonly_query(
    sql: str,
    *,
    connection_factory: ConnectionFactory = open_read_connection,
) -> dict[str, Any]:
    """Exécute une analyse SQL dans une transaction PostgreSQL READ ONLY."""

    validated_sql = validate_readonly_sql(sql)
    started = monotonic()
    row_count = 0
    truncated = False
    try:
        with connection_factory() as connection:
            with connection.transaction():
                with connection.cursor() as control_cursor:
                    control_cursor.execute("SET TRANSACTION READ ONLY")
                    control_cursor.execute(
                        "SELECT set_config('statement_timeout', %s, true)",
                        (f"{READONLY_SQL_STATEMENT_TIMEOUT_MS}ms",),
                    )

                cursor_name = f"sirs_readonly_{uuid4().hex}"
                with connection.cursor(name=cursor_name) as cursor:
                    cursor.execute(validated_sql)
                    columns = [column.name for column in (cursor.description or ())]
                    rows: list[list[Any]] = []
                    result_bytes = _row_size(columns)
                    while True:
                        remaining = READONLY_SQL_MAX_ROWS - len(rows)
                        fetch_size = min(READONLY_SQL_FETCH_SIZE, remaining + 1)
                        batch = cursor.fetchmany(fetch_size)
                        if not batch:
                            break
                        for raw_row in batch:
                            if len(rows) >= READONLY_SQL_MAX_ROWS:
                                truncated = True
                                break
                            row = [_json_value(value) for value in raw_row]
                            size = _row_size(row)
                            if result_bytes + size > READONLY_SQL_MAX_RESULT_BYTES:
                                truncated = True
                                break
                            rows.append(row)
                            result_bytes += size
                        if truncated:
                            break

                    row_count = len(rows)
                    result = {
                        "columns": columns,
                        "rows": rows,
                        "truncated": truncated,
                    }
    except Exception as exc:
        timed_out = getattr(exc, "sqlstate", None) == "57014"
        logger.warning(
            "Requête SQL de lecture échouée (duration_ms=%d, timeout=%s)",
            round((monotonic() - started) * 1000),
            timed_out,
        )
        message = (
            "La requête SQL a dépassé le délai autorisé."
            if timed_out
            else "La requête SQL de lecture a échoué."
        )
        raise ReadonlySqlExecutionError(message, timed_out=timed_out) from exc

    logger.info(
        "Requête SQL de lecture réussie (duration_ms=%d, rows=%d, truncated=%s)",
        round((monotonic() - started) * 1000),
        row_count,
        truncated,
    )
    return result
