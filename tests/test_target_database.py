import os
import unittest
from unittest.mock import patch

from sirs_postgre.target.database import (
    PostgreSQLConfig,
    PostgreSQLConfigurationError,
    check_connection,
    validate_recreatable_database_name,
)


class FakeCursor:
    def __init__(self, row, rows=()):
        self.row = row
        self.rows = rows
        self.query = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        self.query = query

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, row, rows=()):
        self.cursor_instance = FakeCursor(row, rows)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.cursor_instance


class PostgreSQLInfrastructureTest(unittest.TestCase):
    def test_recreate_rejects_empty_protected_and_unsafe_database_names(self):
        unsafe_names = (
            "",
            " ",
            "postgres",
            "POSTGRES",
            "template0",
            "template1",
            "database with spaces",
            "../production",
            "a" * 64,
        )
        for database in unsafe_names:
            with self.subTest(database=database):
                with self.assertRaises(PostgreSQLConfigurationError):
                    validate_recreatable_database_name(database)
        self.assertEqual(
            validate_recreatable_database_name("sirs_postgre"), "sirs_postgre"
        )

    def test_recreate_rejects_configured_admin_database(self):
        with self.assertRaises(PostgreSQLConfigurationError):
            validate_recreatable_database_name(
                "maintenance", admin_database="maintenance"
            )

    def test_admin_connection_reuses_credentials_and_enables_autocommit(self):
        config = PostgreSQLConfig(
            host="db.test",
            port=5544,
            database="sirs_postgre",
            user="operator",
            password="secret",
            admin_database="maintenance",
        )
        kwargs = config.admin_connect_kwargs()
        self.assertEqual(kwargs["host"], "db.test")
        self.assertEqual(kwargs["port"], 5544)
        self.assertEqual(kwargs["user"], "operator")
        self.assertEqual(kwargs["password"], "secret")
        self.assertEqual(kwargs["dbname"], "maintenance")
        self.assertIs(kwargs["autocommit"], True)

    def test_admin_connection_overrides_database_from_dsn(self):
        config = PostgreSQLConfig(
            dsn="postgresql://operator:secret@db.test/sirs_postgre",
            admin_database="postgres",
        )
        kwargs = config.admin_connect_kwargs()
        self.assertEqual(kwargs["conninfo"], config.dsn)
        self.assertEqual(kwargs["dbname"], "postgres")
        self.assertIs(kwargs["autocommit"], True)

    def test_environment_configuration_has_no_password_default(self):
        with patch.dict(os.environ, {}, clear=True):
            config = PostgreSQLConfig.from_env()
        self.assertEqual(config.database, "sirs_postgre")
        self.assertIsNone(config.password)

    def test_dsn_is_prioritary_and_not_exposed_in_safe_location(self):
        with patch.dict(
            os.environ,
            {"SIRS_POSTGRE_DSN": "postgresql://user:secret@db.test/sirs"},
            clear=True,
        ):
            config = PostgreSQLConfig.from_env()
        self.assertEqual(config.safe_location, "DSN fourni par SIRS_POSTGRE_DSN")
        self.assertNotIn("secret", config.safe_location)
        self.assertIs(config.password_configured, True)

    def test_password_diagnostic_supports_separate_configuration_and_dsn(self):
        self.assertIs(PostgreSQLConfig(password=None).password_configured, False)
        self.assertIs(PostgreSQLConfig(password="secret").password_configured, True)
        self.assertIs(
            PostgreSQLConfig(
                dsn="postgresql://operator@db.test/sirs_postgre"
            ).password_configured,
            False,
        )

    def test_connection_check_only_executes_a_select(self):
        calls = []
        connection = FakeConnection(("sirs", "reader", "17.2", "3.5.2", "1.3"))

        def connector(**kwargs):
            calls.append(kwargs)
            return connection

        status = check_connection(PostgreSQLConfig(), connector=connector)
        self.assertEqual(status.database, "sirs")
        self.assertEqual(status.postgis_version, "3.5.2")
        self.assertEqual(status.pgcrypto_version, "1.3")
        self.assertTrue(connection.cursor_instance.query.startswith("SELECT"))
        self.assertTrue(calls[0]["autocommit"])


if __name__ == "__main__":
    unittest.main()
