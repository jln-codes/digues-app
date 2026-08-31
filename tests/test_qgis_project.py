import os
from pathlib import Path
import tempfile
import unittest

from dotenv import load_dotenv

from sirs_postgre.qgis_project import (
    DEFAULT_QGIS_PROJECT_PATH,
    DESORDRE_FILTERS,
    GROUP_PATHS,
    LAYER_SPECS,
    LOCALISATION_DISPLAY_EXPRESSION,
    LOCALISATION_HIDDEN_FIELDS,
    MINIMUM_QGIS_VERSION_INT,
    PyQGISUnavailableError,
    RELATION_SPECS,
    _load_pyqgis,
    _temporary_pgpassword,
    generate_qgis_project,
    pyqgis_available,
    qgis_connection_from_config,
)
from sirs_postgre.target import PostgreSQLConfig


class QGISProjectSpecificationTest(unittest.TestCase):
    def test_default_output_is_a_gitignored_qgz(self):
        self.assertEqual(DEFAULT_QGIS_PROJECT_PATH, Path("qgis/sirs_postgre.qgz"))
        self.assertEqual(DEFAULT_QGIS_PROJECT_PATH.suffix, ".qgz")
        self.assertEqual(MINIMUM_QGIS_VERSION_INT, 33800)

    def test_layer_ids_and_names_are_stable_and_unique(self):
        self.assertEqual(len({spec.layer_id for spec in LAYER_SPECS}), len(LAYER_SPECS))
        by_key = {spec.key: spec for spec in LAYER_SPECS}
        self.assertEqual(by_key["troncons"].name, "Tronçons")
        self.assertEqual(by_key["desordres_point"].name, "Désordres — Points")
        self.assertEqual(by_key["desordres_line"].name, "Désordres — Lignes")
        self.assertEqual(
            by_key["desordres_polygon"].name,
            "Désordres — Polygones",
        )
        self.assertEqual(
            by_key["diagnostic_reperage"].name,
            "Diagnostic repérage des désordres",
        )

    def test_disorder_instances_share_the_table_with_distinct_filters(self):
        by_key = {spec.key: spec for spec in LAYER_SPECS}
        expected = {
            "desordres_point": DESORDRE_FILTERS["point"],
            "desordres_line": DESORDRE_FILTERS["line"],
            "desordres_polygon": DESORDRE_FILTERS["polygon"],
        }
        for key, subset in expected.items():
            with self.subTest(key=key):
                self.assertEqual(by_key[key].table, "desordres")
                self.assertEqual(by_key[key].subset, subset)
                self.assertEqual(by_key[key].geometry_column, "geometry")

    def test_child_table_is_private_and_has_no_primary_geometry(self):
        by_key = {spec.key: spec for spec in LAYER_SPECS}
        child = by_key["desordre_localisations"]
        self.assertTrue(child.private)
        self.assertIsNone(child.group_path)
        self.assertEqual(child.geometry_column, "")
        self.assertIn("position_debut_source", LOCALISATION_HIDDEN_FIELDS)
        self.assertIn("position_fin_source", LOCALISATION_HIDDEN_FIELDS)

    def test_relation_ids_are_deterministic_and_cover_each_parent(self):
        self.assertEqual(
            tuple(spec.relation_id for spec in RELATION_SPECS),
            (
                "desordre_point_localisations_reperage",
                "desordre_ligne_localisations_reperage",
                "desordre_polygone_localisations_reperage",
            ),
        )
        self.assertEqual(
            {spec.parent_layer_key for spec in RELATION_SPECS},
            {"desordres_point", "desordres_line", "desordres_polygon"},
        )
        self.assertTrue(
            all(
                spec.child_layer_key == "desordre_localisations"
                for spec in RELATION_SPECS
            )
        )

    def test_group_tree_and_localisation_representation_are_readable(self):
        self.assertIn(("SIRS", "Patrimoine"), GROUP_PATHS)
        self.assertIn(("SIRS", "Désordres"), GROUP_PATHS)
        self.assertIn(("SIRS", "Repérage"), GROUP_PATHS)
        self.assertIn(("SIRS", "Diagnostic"), GROUP_PATHS)
        self.assertIn("Tronçons", LOCALISATION_DISPLAY_EXPRESSION)
        self.assertIn("Bornes", LOCALISATION_DISPLAY_EXPRESSION)
        self.assertIn("format_number", LOCALISATION_DISPLAY_EXPRESSION)

    def test_connection_reuses_target_config_without_retaining_password(self):
        config = PostgreSQLConfig(
            host="db.internal",
            port=5544,
            database="sirs_test",
            user="qgis_user",
            password="secret-value",
        )
        connection = qgis_connection_from_config(config, authcfg="auth-qgis")
        self.assertEqual(connection.host, "db.internal")
        self.assertEqual(connection.port, 5544)
        self.assertEqual(connection.database, "sirs_test")
        self.assertEqual(connection.user, "qgis_user")
        self.assertEqual(connection.authcfg, "auth-qgis")
        self.assertNotIn("secret-value", repr(connection))

    def test_dsn_is_parsed_without_copying_its_password(self):
        config = PostgreSQLConfig(
            dsn=(
                "host=dsn.example port=5545 dbname=sirs_dsn "
                "user=dsn_user password=dsn-secret"
            )
        )
        connection = qgis_connection_from_config(config)
        self.assertEqual(
            (connection.host, connection.port, connection.database, connection.user),
            ("dsn.example", 5545, "sirs_dsn", "dsn_user"),
        )
        self.assertNotIn("dsn-secret", repr(connection))

    def test_temporary_pgpassword_is_restored(self):
        previous = os.environ.get("PGPASSWORD")
        os.environ["PGPASSWORD"] = "before"
        try:
            with _temporary_pgpassword("during"):
                self.assertEqual(os.environ["PGPASSWORD"], "during")
            self.assertEqual(os.environ["PGPASSWORD"], "before")
        finally:
            if previous is None:
                os.environ.pop("PGPASSWORD", None)
            else:
                os.environ["PGPASSWORD"] = previous

    def test_missing_pyqgis_has_an_explicit_error(self):
        if pyqgis_available():
            self.skipTest("PyQGIS est disponible dans cet environnement")
        with self.assertRaisesRegex(
            PyQGISUnavailableError, "OSGeo4W Shell|QGIS 3.38"
        ):
            _load_pyqgis()


@unittest.skipUnless(pyqgis_available(), "PyQGIS indisponible")
class QGISProjectIntegrationTest(unittest.TestCase):
    def test_generated_project_is_reloaded_and_verified(self):
        load_dotenv(
            Path(__file__).resolve().parents[1] / "config.env",
            override=False,
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "sirs_postgre.qgz"
            result = generate_qgis_project(
                PostgreSQLConfig.from_env(),
                output,
            )
            self.assertTrue(output.is_file())
            self.assertEqual(set(result.relation_ids), {
                spec.relation_id for spec in RELATION_SPECS
            })


if __name__ == "__main__":
    unittest.main()
