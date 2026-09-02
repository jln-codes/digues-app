import io
import os
import tempfile
import unittest
from collections import defaultdict
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from sirs_postgre.cli import SOURCE_CLASSES, main
from sirs_postgre.migration import TargetNotEmptyError
from sirs_postgre.source import CouchDBConfig, CouchDBDatabaseInfo, CouchDBSourceStatus
from sirs_postgre.target import (
    PostgreSQLConfig,
    PostgreSQLRecreateStatus,
    PostgreSQLSchemaStatus,
    PostgreSQLStatus,
)
from sirs_postgre.target.schema import EXPECTED_TABLES
from sirs_postgre.qgis_project import QGISProjectResult


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
            SOURCE_CLASSES["SystemeReperage"]: 104,
            SOURCE_CLASSES["BorneDigue"]: 208,
            SOURCE_CLASSES["Desordre"]: 1_598,
        }[class_name]

    def get_database_info(self):
        return CouchDBDatabaseInfo(
            source_database="cabbalr",
            epsg_code="EPSG:3950",
            crs_wkt='PROJCS["RGF93 / CC50",AUTHORITY["EPSG","3950"]]',
            proj4="+proj=lcc",
        )


class CLITest(unittest.TestCase):
    @patch("sirs_postgre.qgis_project.generate_qgis_project")
    @patch("sirs_postgre.cli.PostgreSQLConfig.from_env")
    def test_qgis_project_command_uses_default_output(
        self, target_config, generate_project
    ):
        config = PostgreSQLConfig()
        target_config.return_value = config
        output = Path("qgis/sirs_postgre.qgz").resolve()
        generate_project.return_value = QGISProjectResult(
            output=output,
            layer_ids=("layer",),
            relation_ids=("relation",),
            groups=("SIRS",),
            connection="postgres@127.0.0.1:5432/sirs_postgre",
        )
        captured = io.StringIO()
        with redirect_stdout(captured):
            result = main(["qgis-project"])
        self.assertEqual(result, 0)
        generate_project.assert_called_once_with(
            config,
            Path("qgis/sirs_postgre.qgz"),
            authcfg=None,
        )
        self.assertIn("mot de passe non enregistré", captured.getvalue())

    @patch("sirs_postgre.qgis_project.generate_qgis_project")
    @patch("sirs_postgre.cli.PostgreSQLConfig.from_env")
    def test_qgis_project_accepts_output_and_authcfg(
        self, target_config, generate_project
    ):
        config = PostgreSQLConfig()
        target_config.return_value = config
        output = Path("build/pilote.qgz")
        generate_project.return_value = QGISProjectResult(
            output=output.resolve(),
            layer_ids=(),
            relation_ids=(),
            groups=(),
            connection="postgres@127.0.0.1:5432/sirs_postgre",
        )
        captured = io.StringIO()
        with redirect_stdout(captured):
            result = main(
                [
                    "qgis-project",
                    "--output",
                    str(output),
                    "--authcfg",
                    "qgis-auth-id",
                ]
            )
        self.assertEqual(result, 0)
        generate_project.assert_called_once_with(
            config,
            output,
            authcfg="qgis-auth-id",
        )

    @patch(
        "sirs_postgre.qgis_project.generate_qgis_project",
        side_effect=RuntimeError("PyQGIS indisponible"),
    )
    @patch("sirs_postgre.cli.PostgreSQLConfig.from_env")
    def test_qgis_project_failure_is_explicit_and_redacted(
        self, target_config, _generate_project
    ):
        target_config.return_value = PostgreSQLConfig(password="secret")
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["qgis-project"])
        self.assertEqual(result, 1)
        self.assertIn("PyQGIS indisponible", output.getvalue())
        self.assertNotIn("secret", output.getvalue())

    @patch("sirs_postgre.cli.generate_coverage_report")
    @patch("sirs_postgre.cli.connect_couchdb")
    def test_diagnose_command_generates_the_expected_report(
        self, connect_source, generate_report
    ):
        client = object()
        connect_source.return_value = client
        generate_report.return_value = SimpleNamespace(
            path=Path("/project/audits/bilan.md"),
            total_classes=12,
            non_migrated_documents=3,
            anomalies_json_path=Path("/project/audits/anomalies.json"),
            anomalies_csv_path=Path("/project/audits/anomalies.csv"),
            anomaly_register=SimpleNamespace(
                active=(object(), object()),
                counts_by_severity={
                    "INFO": 1,
                    "WARNING": 1,
                    "ERROR": 0,
                    "BLOCKING": 0,
                },
            ),
        )
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["diagnose"])
        self.assertEqual(result, 0)
        generate_report.assert_called_once_with(client)
        self.assertIn("audits/bilan.md", output.getvalue())
        self.assertIn("audits/anomalies.json", output.getvalue())
        self.assertIn("audits/anomalies.csv", output.getvalue())

    @patch(
        "sirs_postgre.cli.migrate_core",
        side_effect=TargetNotEmptyError("cible non vide"),
    )
    def test_migrate_core_non_empty_target_prints_recovery_commands(self, _migrate):
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["migrate-core"])
        self.assertEqual(result, 1)
        text = output.getvalue()
        self.assertIn("La base cible contient déjà des données", text)
        self.assertIn("sirs-postgre recreate", text)
        self.assertIn("sirs-postgre init-schema", text)
        self.assertIn("sirs-postgre migrate-core", text)

    @patch("sirs_postgre.cli.generate_coverage_report")
    @patch("sirs_postgre.cli.connect_couchdb")
    @patch("sirs_postgre.cli.migrate_core")
    def test_successful_migrate_core_generates_all_three_diagnostics(
        self, migrate, connect_source, generate_report
    ):
        prepared = SimpleNamespace(
            categories_desordre=(),
            types_desordre=(),
            urgences=(),
            systemes=(),
            digues=(),
            digues_without_system=0,
            troncons=(),
            reperage=SimpleNamespace(
                systemes=(),
                bornes=(),
                default_system_count=0,
            ),
            desordres=(),
            desordre_geometry_counts={"point": 0, "linestring": 0, "null": 0},
            desordre_source_geometry_present=0,
            desordre_source_geometry_absent=0,
            observations=(),
            photos=(),
            synthetic_observations=0,
            direct_troncon_photos=0,
            direct_other_photos=0,
            ouvrages=SimpleNamespace(
                rows={}, migrated_count=0, deferred_count=0, invalid_counts={}
            ),
            amenagements=SimpleNamespace(
                amenagements=(),
                associated_ouvrages=(),
                deferred_chemins=0,
                deferred_prestations=0,
            ),
            vegetation=SimpleNamespace(
                geometry_counts={
                    "point": 0,
                    "linestring": 0,
                    "polygon": 0,
                    "null": 0,
                },
                method_counts={},
                deferred_treatments=0,
                deferred_planifications=0,
            ),
            warnings=(),
        )
        migrate.return_value = SimpleNamespace(
            prepared=prepared,
            validation=SimpleNamespace(table_counts=defaultdict(int)),
        )
        client = object()
        connect_source.return_value = client
        generate_report.return_value = SimpleNamespace(
            path=Path("/project/audits/bilan.md"),
            anomalies_json_path=Path("/project/audits/anomalies.json"),
            anomalies_csv_path=Path("/project/audits/anomalies.csv"),
        )
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["migrate-core"])
        self.assertEqual(result, 0)
        migrate.assert_called_once_with(
            reproject_on_troncon=True,
            on_troncon_tolerance=0.0001,
        )
        generate_report.assert_called_once_with(client)
        text = output.getvalue()
        self.assertIn("audits/bilan.md", text)
        self.assertIn("audits/anomalies.json", text)
        self.assertIn("audits/anomalies.csv", text)

    @patch(
        "sirs_postgre.cli.migrate_core",
        side_effect=RuntimeError("arrêt après lecture des options"),
    )
    def test_migrate_core_accepts_reprojection_options(self, migrate):
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(
                [
                    "migrate-core",
                    "--no-reproject-on-troncon",
                    "--on-troncon-tolerance",
                    "0.25",
                ]
            )
        self.assertEqual(result, 1)
        migrate.assert_called_once_with(
            reproject_on_troncon=False,
            on_troncon_tolerance=0.25,
        )

    def test_migrate_core_rejects_negative_or_non_finite_tolerance(self):
        for value in ("-0.1", "nan", "inf"):
            with self.subTest(value=value), self.assertRaises(SystemExit):
                main(["migrate-core", "--on-troncon-tolerance", value])

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
            pgcrypto_version="1.3",
        )
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["init-schema"])
        self.assertEqual(result, 0)
        initialize_schema.assert_called_once_with(config)
        text = output.getvalue()
        self.assertIn("[OK] Schéma métier initialisé", text)
        self.assertIn("[OK] pgcrypto disponible : 1.3", text)
        self.assertIn("[OK] Table présente : photos", text)

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
            pgcrypto_version="1.3",
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
        self.assertIn("[OK] pgcrypto activée : 1.3", text)
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
            "1.3",
        )
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["check"])
        self.assertEqual(result, 0)
        text = output.getvalue()
        self.assertIn("SystemeEndiguement: 9", text)
        self.assertIn("Desordre: 1598", text)
        self.assertIn("SystemeReperage: 104", text)
        self.assertIn("BorneDigue: 208", text)
        self.assertIn("Source CRS: EPSG:3950", text)
        self.assertIn("Target CRS: EPSG:3950", text)
        self.assertIn("Transformation: non", text)
        self.assertIn("Cible PostgreSQL", text)
        self.assertIn("systemes: présente", text)
        self.assertIn("photos: présente", text)
        self.assertIn("pgcrypto: 1.3", text)
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
