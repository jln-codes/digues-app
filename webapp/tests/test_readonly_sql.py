from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from dotenv import load_dotenv

from digues_webapp.database import (
    PostgreSQLConfig,
    configure_extension_search_path,
    extension_search_path,
    open_read_connection,
)
from digues_webapp.readonly_sql import (
    READONLY_SQL_STATEMENT_TIMEOUT_MS,
    ReadonlySqlExecutionError,
    ReadonlySqlValidationError,
    execute_readonly_query,
    validate_readonly_sql,
)


class FakeTransaction:
    def __init__(self, events):
        self.events = events

    def __enter__(self):
        self.events.append(("transaction_enter",))
        return self

    def __exit__(self, exc_type, *_args):
        self.events.append(("transaction_exit", exc_type))
        return False


class FakeControlCursor:
    def __init__(self, events):
        self.events = events

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        self.events.append(("control", query, params))


class FakeResultCursor:
    def __init__(self, events, columns, rows, error=None):
        self.events = events
        self.description = [SimpleNamespace(name=name) for name in columns]
        self.rows = list(rows)
        self.error = error

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query):
        self.events.append(("query", query))
        if self.error:
            raise self.error

    def fetchmany(self, size):
        self.events.append(("fetchmany", size))
        batch, self.rows = self.rows[:size], self.rows[size:]
        return batch


class FakeReadonlyConnection:
    def __init__(self, columns=(), rows=(), error=None):
        self.events = []
        self.columns = columns
        self.rows = rows
        self.error = error

    def transaction(self):
        return FakeTransaction(self.events)

    def cursor(self, name=None):
        if name is None:
            return FakeControlCursor(self.events)
        self.events.append(("server_cursor", name))
        return FakeResultCursor(
            self.events, self.columns, self.rows, error=self.error
        )


def factory_for(connection):
    @contextmanager
    def factory():
        yield connection

    return factory


class FakeExtensionCursor:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchall(self):
        return list(self.rows)


class WebDatabaseConfigurationTest(unittest.TestCase):
    def test_database_url_takes_priority_over_legacy_variables(self):
        environment = {
            "DATABASE_URL": "postgresql://dsn-user:secret@example.invalid/dsn_db",
            "SIRS_POSTGRE_HOST": "legacy-host",
            "SIRS_POSTGRE_PORT": "15432",
            "SIRS_POSTGRE_DATABASE": "legacy_db",
            "SIRS_POSTGRE_USER": "legacy_user",
            "SIRS_POSTGRE_PASSWORD": "legacy_secret",
            "SIRS_POSTGRE_CONNECT_TIMEOUT": "7",
        }
        with patch.dict("os.environ", environment, clear=True):
            config = PostgreSQLConfig.from_env()

        self.assertEqual(config.connect_kwargs()["conninfo"], environment["DATABASE_URL"])
        self.assertEqual(config.connect_kwargs()["connect_timeout"], 7)
        self.assertEqual(config.safe_location, "DSN fourni par DATABASE_URL")

    def test_legacy_postgresql_variables_are_preserved_without_database_url(self):
        environment = {
            "SIRS_POSTGRE_HOST": "db.internal",
            "SIRS_POSTGRE_PORT": "15432",
            "SIRS_POSTGRE_DATABASE": "sirs",
            "SIRS_POSTGRE_USER": "webapp",
            "SIRS_POSTGRE_PASSWORD": "secret",
            "SIRS_POSTGRE_CONNECT_TIMEOUT": "12",
        }
        with patch.dict("os.environ", environment, clear=True):
            kwargs = PostgreSQLConfig.from_env().connect_kwargs(autocommit=False)

        self.assertEqual(kwargs["host"], "db.internal")
        self.assertEqual(kwargs["port"], 15432)
        self.assertEqual(kwargs["dbname"], "sirs")
        self.assertEqual(kwargs["user"], "webapp")
        self.assertEqual(kwargs["password"], "secret")
        self.assertEqual(kwargs["connect_timeout"], 12)
        self.assertFalse(kwargs["autocommit"])

    def test_extension_search_path_quotes_dynamic_extension_schemas(self):
        self.assertEqual(
            extension_search_path("extensions", 'postgis"custom'),
            'pg_catalog, public, "extensions", "postgis""custom"',
        )

    def test_configure_extension_search_path_reads_pg_catalog_and_namespace(self):
        cursor = FakeExtensionCursor([
            ("postgis", "3.5.0", "extensions"),
            ("pgcrypto", "1.3", "crypto"),
        ])
        status = configure_extension_search_path(cursor)

        self.assertEqual(status.postgis_schema, "extensions")
        self.assertEqual(status.pgcrypto_schema, "crypto")
        self.assertIn("FROM pg_extension AS e", cursor.queries[0][0])
        self.assertIn("JOIN pg_namespace AS n", cursor.queries[0][0])
        self.assertEqual(
            cursor.queries[1],
            (
                "SELECT set_config('search_path', %s, false)",
                ('pg_catalog, public, "extensions", "crypto"',),
            ),
        )


class ReadonlySqlValidationTest(unittest.TestCase):
    def test_accepts_advanced_read_queries_without_rewriting_them(self):
        queries = (
            "SELECT id, libelle FROM public.systemes",
            "WITH actifs AS (SELECT id FROM public.systemes WHERE valid) "
            "SELECT * FROM actifs",
            "SELECT d.id FROM public.digues d JOIN public.systemes s "
            "ON s.id = d.systeme_endiguement_id",
            "SELECT digue_id, count(*) FROM public.troncons GROUP BY digue_id",
            "SELECT ST_Length(geometry) FROM public.troncons",
            "/* SELECT sûre */ SELECT 'UPDATE; DELETE', \"update\" FROM exemple;",
            "SELECT $$INSERT; DROP$$",
        )
        for sql in queries:
            with self.subTest(sql=sql):
                self.assertEqual(validate_readonly_sql(sql), sql.strip())

    def test_rejects_mutating_and_administrative_operations(self):
        queries = (
            "INSERT INTO t VALUES (1)",
            "UPDATE t SET value = 1",
            "DELETE FROM t",
            "CREATE TABLE t (id int)",
            "ALTER TABLE t ADD COLUMN value int",
            "DROP TABLE t",
            "TRUNCATE t",
            "MERGE INTO t USING u ON false WHEN NOT MATCHED THEN INSERT DEFAULT VALUES",
            "GRANT SELECT ON t TO role",
            "REVOKE SELECT ON t FROM role",
            "COMMENT ON TABLE t IS 'x'",
            "VACUUM t",
            "ANALYZE t",
            "REFRESH MATERIALIZED VIEW v",
            "CLUSTER t",
            "REINDEX TABLE t",
            "COPY t TO '/tmp/t.csv'",
            "WITH changed AS (DELETE FROM t RETURNING id) SELECT * FROM changed",
            "SELECT value INTO temporary_table FROM t",
            "SELECT nextval('sequence')",
            "SELECT set_config('search_path', 'public', false)",
            "SELECT pg_advisory_lock(1)",
            "SELECT pg_notify('channel', 'payload')",
        )
        for sql in queries:
            with self.subTest(sql=sql), self.assertRaises(
                ReadonlySqlValidationError
            ):
                validate_readonly_sql(sql)

    def test_rejects_multiple_or_malformed_statements(self):
        queries = (
            "SELECT 1; SELECT 2",
            "SELECT 1;;",
            "SELECT 'unterminated",
            "SELECT 1 /* unterminated",
            "WITH source AS (SELECT 1)",
            "VALUES (1)",
            "",
        )
        for sql in queries:
            with self.subTest(sql=sql), self.assertRaises(
                ReadonlySqlValidationError
            ):
                validate_readonly_sql(sql)


class ReadonlySqlEngineTest(unittest.TestCase):
    def test_configures_read_only_transaction_and_local_timeout(self):
        connection = FakeReadonlyConnection(["value"], [(1,)])
        result = execute_readonly_query(
            "SELECT 1 AS value", connection_factory=factory_for(connection)
        )

        self.assertEqual(
            result, {"columns": ["value"], "rows": [[1]], "truncated": False}
        )
        self.assertEqual(connection.events[0], ("transaction_enter",))
        self.assertEqual(
            connection.events[1], ("control", "SET TRANSACTION READ ONLY", None)
        )
        self.assertEqual(
            connection.events[2],
            (
                "control",
                "SELECT set_config('statement_timeout', %s, true)",
                (f"{READONLY_SQL_STATEMENT_TIMEOUT_MS}ms",),
            ),
        )
        self.assertEqual(connection.events[-1], ("transaction_exit", None))

    def test_returns_columns_empty_rows_and_json_safe_values(self):
        identifier = uuid.uuid4()
        connection = FakeReadonlyConnection(
            ["nothing", "amount", "day", "id", "geometry"],
            [(None, Decimal("1.20"), date(2026, 9, 4), identifier, b"\x01\x02")],
        )
        result = execute_readonly_query(
            "SELECT values", connection_factory=factory_for(connection)
        )
        self.assertEqual(
            result["rows"],
            [[None, "1.20", "2026-09-04", str(identifier), "\\x0102"]],
        )

        empty = execute_readonly_query(
            "SELECT values",
            connection_factory=factory_for(FakeReadonlyConnection(["id"], [])),
        )
        self.assertEqual(
            empty, {"columns": ["id"], "rows": [], "truncated": False}
        )

    def test_transport_row_limit_does_not_rewrite_aggregation(self):
        connection = FakeReadonlyConnection(["count"], [(42,)])
        sql = "SELECT COUNT(*) FROM public.systemes"
        aggregate = execute_readonly_query(
            sql, connection_factory=factory_for(connection)
        )
        self.assertEqual(aggregate["rows"], [[42]])
        self.assertIn(("query", sql), connection.events)

        limited_connection = FakeReadonlyConnection(
            ["id"], [(1,), (2,), (3,)]
        )
        with patch("digues_webapp.readonly_sql.READONLY_SQL_MAX_ROWS", 2):
            limited = execute_readonly_query(
                "SELECT id FROM t",
                connection_factory=factory_for(limited_connection),
            )
        self.assertEqual(limited["rows"], [[1], [2]])
        self.assertTrue(limited["truncated"])

    def test_serialized_size_limit_truncates_before_oversized_row(self):
        connection = FakeReadonlyConnection(["text"], [("a" * 30,), ("b",)])
        with patch("digues_webapp.readonly_sql.READONLY_SQL_MAX_RESULT_BYTES", 20):
            result = execute_readonly_query(
                "SELECT text FROM t", connection_factory=factory_for(connection)
            )
        self.assertEqual(result["rows"], [])
        self.assertTrue(result["truncated"])

    def test_database_timeout_is_normalized_and_rolls_back_transaction(self):
        error = RuntimeError("canceling statement due to statement timeout")
        error.sqlstate = "57014"
        connection = FakeReadonlyConnection(["value"], [], error=error)
        with self.assertRaises(ReadonlySqlExecutionError) as raised:
            execute_readonly_query(
                "SELECT pg_sleep(1)", connection_factory=factory_for(connection)
            )
        self.assertTrue(raised.exception.timed_out)
        self.assertNotIn("statement timeout", str(raised.exception))
        self.assertEqual(
            connection.events[-1], ("transaction_exit", RuntimeError)
        )


class ReadonlySqlPostGISIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import psycopg

            load_dotenv(
                Path(__file__).resolve().parents[2] / "config.env",
                override=False,
            )
            config = PostgreSQLConfig.from_env()
            with psycopg.connect(
                **config.connect_kwargs(autocommit=True)
            ) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT PostGIS_Version()")
                    cursor.fetchone()
        except Exception as exc:
            raise unittest.SkipTest(f"PostGIS local indisponible : {exc}")

    def test_real_readonly_engine_supports_aggregations_and_postgis(self):
        transaction = execute_readonly_query(
            "SELECT current_setting('transaction_read_only') AS read_only"
        )
        self.assertEqual(transaction["rows"], [["on"]])

        aggregate = execute_readonly_query(
            "SELECT COUNT(*) AS total FROM public.systemes"
        )
        self.assertEqual(aggregate["columns"], ["total"])
        self.assertEqual(len(aggregate["rows"]), 1)
        self.assertIsInstance(aggregate["rows"][0][0], int)

        spatial = execute_readonly_query(
            "SELECT ST_AsText(ST_SetSRID(ST_Point(1, 2), 3950)) AS geometry_wkt, "
            "ST_SetSRID(ST_Point(1, 2), 3950) AS geometry_raw"
        )
        self.assertEqual(spatial["rows"][0][0], "POINT(1 2)")
        self.assertIsInstance(spatial["rows"][0][1], str)
        self.assertTrue(spatial["rows"][0][1])

    def test_postgresql_read_only_barrier_rejects_mutation_after_validation(self):
        with (
            patch(
                "digues_webapp.readonly_sql.validate_readonly_sql",
                return_value="UPDATE public.systemes SET valid = valid",
            ),
            self.assertRaises(ReadonlySqlExecutionError) as raised,
        ):
            execute_readonly_query("SELECT 1")
        self.assertFalse(raised.exception.timed_out)

        import psycopg

        with open_read_connection() as connection:
            with self.assertRaises(psycopg.errors.ReadOnlySqlTransaction):
                with connection.transaction():
                    with connection.cursor() as cursor:
                        cursor.execute("SET TRANSACTION READ ONLY")
                        cursor.execute(
                            "UPDATE public.systemes SET valid = valid"
                        )

    def test_postgresql_statement_timeout_is_local_to_execution(self):
        with (
            patch("digues_webapp.readonly_sql.READONLY_SQL_STATEMENT_TIMEOUT_MS", 10),
            self.assertRaises(ReadonlySqlExecutionError) as raised,
        ):
            execute_readonly_query("SELECT pg_sleep(0.1)")
        self.assertTrue(raised.exception.timed_out)


if __name__ == "__main__":
    unittest.main()
