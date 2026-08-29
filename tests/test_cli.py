import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from sirs_postgre.cli import SOURCE_CLASSES, main
from sirs_postgre.source import CouchDBConfig, CouchDBSourceStatus
from sirs_postgre.target import (
    PostgreSQLConfig,
    PostgreSQLRecreateStatus,
    PostgreSQLSchemaStatus,
    PostgreSQLStatus,
)
from sirs_postgre.target.schema import EXPECTED_TABLES


class FakeSourceClient:
    def __init__(self, *, username=None, password=None, check_error=None):
        self.config = CouchDBConfig(username=username, password=password)
        self.check_error = check_error

    def check_connection(self):
        if self.check_error:
            raise self.check_error
        return CouchDBSourceStatus("cabbalr", "3.4.2", 4_768)

    def count_by_class(self, class_name):
        return {
            SOURCE_CLASSES["SystemeEndiguement"]: 9,
            SOURCE_CLASSES["Digue"]: 26,
            SOURCE_CLASSES["TronconDigue"]: 104,
            SOURCE_CLASSES["Desordre"]: 1_598,
        }[class_name]


class CLITest(unittest.TestCase):
    @patch("sirs_postgre.cli.initialize_postgresql_schema")
    @patch("sirs_postgre.cli.PostgreSQLConfig.from_env")
    def test_init_schema_reports_tables_without_migrating_data(
        self, target_config, initialize_schema
    ):
        config = PostgreSQLConfig()
        target_config.return_value = config
        initialize_schema.return_value = PostgreSQLSchemaStatus(
            tables=EXPECTED_TABLES,
            postgis_version="3.4.2",
        )
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["init-schema"])
        self.assertEqual(result, 0)
        initialize_schema.assert_called_once_with(config)
        text = output.getvalue()
        self.assertIn("[OK] Schéma métier initialisé", text)
        self.assertIn("[OK] Table présente : photo", text)

    @patch("sirs_postgre.cli.recreate_postgresql")
    @patch("sirs_postgre.cli.PostgreSQLConfig.from_env")
    def test_recreate_reports_success_without_real_database_changes(
        self, target_config, recreate_target
    ):
        config = object()
        target_config.return_value = config
        recreate_target.return_value = PostgreSQLRecreateStatus(
            database="sirs_postgre",
            terminated_connections=2,
            postgis_version="3.4.2",
        )
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["recreate"])
        self.assertEqual(result, 0)
        recreate_target.assert_called_once_with(config)
        text = output.getvalue()
        self.assertIn("[OK] Connexions fermées : 2", text)
        self.assertIn("[OK] Base supprimée : sirs_postgre", text)
        self.assertIn("[OK] Base créée : sirs_postgre", text)
        self.assertIn("[OK] PostGIS activée : 3.4.2", text)
        self.assertIn("[OK] Base cible prête", text)

    @patch("sirs_postgre.cli.run_check", return_value=0)
    def test_config_env_is_loaded_without_overriding_shell_environment(self, _run_check):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.env"
            config_path.write_text(
                "SIRS_TEST_FROM_CONFIG=config-value\n"
                "SIRS_TEST_PRIORITY=config-value\n",
                encoding="utf-8",
            )
            with (
                patch("sirs_postgre.cli.CONFIG_ENV_PATH", config_path),
                patch.dict(
                    os.environ,
                    {"SIRS_TEST_PRIORITY": "shell-value"},
                    clear=False,
                ),
            ):
                os.environ.pop("SIRS_TEST_FROM_CONFIG", None)
                result = main(["check", "--target-only"])
                self.assertEqual(result, 0)
                self.assertEqual(os.environ["SIRS_TEST_FROM_CONFIG"], "config-value")
                self.assertEqual(os.environ["SIRS_TEST_PRIORITY"], "shell-value")
                os.environ.pop("SIRS_TEST_FROM_CONFIG", None)

    @patch("sirs_postgre.cli.run_check", return_value=0)
    def test_missing_config_env_is_optional(self, _run_check):
        with tempfile.TemporaryDirectory() as directory:
            missing_path = Path(directory) / "missing-config.env"
            with patch("sirs_postgre.cli.CONFIG_ENV_PATH", missing_path):
                self.assertEqual(main(["check", "--target-only"]), 0)

    @patch("sirs_postgre.cli.check_postgresql")
    @patch("sirs_postgre.cli.PostgreSQLConfig.from_env")
    @patch("sirs_postgre.cli.connect_couchdb")
    def test_check_reports_both_connections_and_source_counts(
        self, connect_source, target_config, check_target
    ):
        connect_source.return_value = FakeSourceClient()
        target_config.return_value = PostgreSQLConfig()
        check_target.return_value = PostgreSQLStatus(
            "sirs_postgre",
            "postgres",
            "17.2",
            "3.5.2",
            frozenset(EXPECTED_TABLES),
        )
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["check"])
        self.assertEqual(result, 0)
        text = output.getvalue()
        self.assertIn("SystemeEndiguement: 9", text)
        self.assertIn("Desordre: 1598", text)
        self.assertIn("Cible PostgreSQL", text)
        self.assertIn("systeme_endiguement: présente", text)
        self.assertIn("photo: présente", text)
        self.assertIn(
            "[INFO] CouchDB : authentification non configurée ; connexion réussie",
            text,
        )
        self.assertIn(
            "[INFO] PostgreSQL : mot de passe non fourni ; "
            "authentification locale réussie",
            text,
        )

    @patch("sirs_postgre.cli.check_postgresql")
    @patch("sirs_postgre.cli.PostgreSQLConfig.from_env")
    @patch("sirs_postgre.cli.connect_couchdb")
    def test_check_reports_configured_authentication_without_exposing_passwords(
        self, connect_source, target_config, check_target
    ):
        connect_source.return_value = FakeSourceClient(
            username="reader", password="couch-secret"
        )
        target_config.return_value = PostgreSQLConfig(password="postgres-secret")
        check_target.return_value = PostgreSQLStatus(
            "sirs_postgre", "postgres", "16.15", "3.4.2"
        )
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["check"])
        self.assertEqual(result, 0)
        text = output.getvalue()
        self.assertIn("[INFO] CouchDB : authentification configurée", text)
        self.assertIn("[INFO] PostgreSQL : authentification configurée", text)
        self.assertNotIn("couch-secret", text)
        self.assertNotIn("postgres-secret", text)

    @patch("sirs_postgre.cli.connect_couchdb")
    def test_check_couchdb_failure_mentions_missing_credentials(self, connect_source):
        connect_source.return_value = FakeSourceClient(
            check_error=RuntimeError("indisponible")
        )
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["check", "--source-only"])
        self.assertEqual(result, 1)
        self.assertIn("authentification CouchDB non configurée", output.getvalue())

    @patch("sirs_postgre.cli.check_postgresql", side_effect=RuntimeError("refusée"))
    @patch("sirs_postgre.cli.PostgreSQLConfig.from_env")
    def test_check_postgresql_failure_mentions_missing_password(
        self, target_config, _check_target
    ):
        target_config.return_value = PostgreSQLConfig(password=None)
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["check", "--target-only"])
        self.assertEqual(result, 1)
        self.assertIn("aucun mot de passe PostgreSQL fourni", output.getvalue())

    @patch("sirs_postgre.cli.connect_couchdb")
    def test_check_couchdb_error_never_displays_password(self, connect_source):
        connect_source.return_value = FakeSourceClient(
            username="reader",
            password="couch-secret",
            check_error=RuntimeError("échec avec couch-secret"),
        )
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["check", "--source-only"])
        self.assertEqual(result, 1)
        self.assertNotIn("couch-secret", output.getvalue())

    @patch(
        "sirs_postgre.cli.check_postgresql",
        side_effect=RuntimeError("échec avec postgres-secret"),
    )
    @patch("sirs_postgre.cli.PostgreSQLConfig.from_env")
    def test_check_postgresql_error_never_displays_password(
        self, target_config, _check_target
    ):
        target_config.return_value = PostgreSQLConfig(password="postgres-secret")
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["check", "--target-only"])
        self.assertEqual(result, 1)
        self.assertNotIn("postgres-secret", output.getvalue())

    @patch("sirs_postgre.cli.connect_couchdb", side_effect=RuntimeError("indisponible"))
    def test_check_returns_failure_for_unreachable_source(self, _connect_source):
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["check", "--source-only"])
        self.assertEqual(result, 1)
        self.assertIn("[ERREUR] Source CouchDB", output.getvalue())


if __name__ == "__main__":
    unittest.main()
