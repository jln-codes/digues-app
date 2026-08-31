import os
from pathlib import Path
import tempfile
import unittest

from dotenv import load_dotenv

from sirs_postgre.qgis_project import (
    ALL_LAYER_SPECS,
    DEFAULT_QGIS_PROJECT_PATH,
    DESORDRE_FILTERS,
    GROUP_PATHS,
    LAYER_SPECS,
    LOCALISATION_DISPLAY_EXPRESSION,
    LOCALISATION_HIDDEN_FIELDS,
    MINIMUM_QGIS_VERSION_INT,
    OSM_LAYER_SPEC,
    OSM_XYZ_URI,
    PyQGISUnavailableError,
    RELATION_SPECS,
    _create_relations,
    _create_osm_layer,
    _load_pyqgis,
    _register_layers,
    _temporary_pgpassword,
    generate_qgis_project,
    pyqgis_available,
    qgis_connection_from_config,
)
from sirs_postgre.target import PostgreSQLConfig


class FakeLayer:
    def __init__(self, layer_id):
        self._layer_id = layer_id

    def id(self):
        return self._layer_id


class FakeLayerTreeRoot:
    def __init__(self):
        self.layer_ids = set()
        self.nodes = {}

    def findLayer(self, layer_id):
        return self.nodes.get(layer_id)


class FakeGroup:
    def __init__(self, root):
        self.root = root

    def addLayer(self, layer):
        self.root.layer_ids.add(layer.id())
        node = FakeLayerTreeNode(layer.id())
        self.root.nodes[layer.id()] = node
        return node


class FakeLayerTreeNode:
    def __init__(self, layer_id):
        self.layer_id = layer_id
        self.visible = False

    def setItemVisibilityChecked(self, visible):
        self.visible = visible


class FakeServerProperties:
    def __init__(self):
        self.attribution = None
        self.attribution_url = None

    def setAttribution(self, attribution):
        self.attribution = attribution

    def setAttributionUrl(self, attribution_url):
        self.attribution_url = attribution_url


class FakeRasterLayer(FakeLayer):
    def __init__(self, uri, name, provider):
        super().__init__("generated")
        self.uri = uri
        self.name = name
        self.provider = provider
        self.properties = FakeServerProperties()

    def isValid(self):
        return True

    def setId(self, layer_id):
        self._layer_id = layer_id
        return True

    def serverProperties(self):
        return self.properties


class FakeRelationManager:
    def __init__(self):
        self.relations = []

    def addRelation(self, relation):
        self.relations.append(relation)


class FakeProject:
    def __init__(self):
        self._layers = {}
        self._root = FakeLayerTreeRoot()
        self._relation_manager = FakeRelationManager()

    def addMapLayer(self, layer, _add_to_legend):
        self._layers[layer.id()] = layer
        return layer

    def mapLayer(self, layer_id):
        return self._layers.get(layer_id)

    def mapLayers(self):
        return dict(self._layers)

    def layerTreeRoot(self):
        return self._root

    def relationManager(self):
        return self._relation_manager


class FakeRelationContext:
    def __init__(self, project):
        self.project = project


class FakeRelation:
    def __init__(self, context):
        self.context = context
        self.relation_id = None
        self.parent_layer_id = None
        self.child_layer_id = None
        self.field_pairs = []

    def setId(self, relation_id):
        self.relation_id = relation_id

    def setName(self, _name):
        pass

    def setReferencedLayer(self, layer_id):
        self.parent_layer_id = layer_id

    def setReferencingLayer(self, layer_id):
        self.child_layer_id = layer_id

    def addFieldPair(self, child_field, parent_field):
        self.field_pairs.append((child_field, parent_field))

    def updateRelationStatus(self):
        pass

    def isValid(self):
        return (
            self.context.project.mapLayer(self.parent_layer_id) is not None
            and self.context.project.mapLayer(self.child_layer_id) is not None
            and bool(self.field_pairs)
        )

    def validationError(self):
        return "relation invalide"


class QGISProjectSpecificationTest(unittest.TestCase):
    def test_default_output_is_a_gitignored_qgz(self):
        self.assertEqual(DEFAULT_QGIS_PROJECT_PATH, Path("qgis/sirs_postgre.qgz"))
        self.assertEqual(DEFAULT_QGIS_PROJECT_PATH.suffix, ".qgz")
        self.assertEqual(MINIMUM_QGIS_VERSION_INT, 33800)

    def test_layer_ids_and_names_are_stable_and_unique(self):
        self.assertEqual(
            len({spec.layer_id for spec in ALL_LAYER_SPECS}),
            len(ALL_LAYER_SPECS),
        )
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

    def test_openstreetmap_xyz_spec_is_self_contained_and_stable(self):
        self.assertEqual(OSM_LAYER_SPEC.layer_id, "sirs_openstreetmap")
        self.assertEqual(OSM_LAYER_SPEC.name, "OpenStreetMap")
        self.assertEqual(OSM_LAYER_SPEC.provider, "wms")
        self.assertEqual(OSM_LAYER_SPEC.group_path, ("Fonds de carte",))
        self.assertIn("https://tile.openstreetmap.org/", OSM_XYZ_URI)
        self.assertIn("%7Bz%7D/%7Bx%7D/%7By%7D.png", OSM_XYZ_URI)
        self.assertNotIn("token", OSM_XYZ_URI.casefold())
        self.assertNotIn("key=", OSM_XYZ_URI.casefold())

    def test_openstreetmap_uses_a_native_xyz_raster_layer(self):
        layer = _create_osm_layer({"QgsRasterLayer": FakeRasterLayer})

        self.assertEqual(layer.id(), "sirs_openstreetmap")
        self.assertEqual(layer.provider, "wms")
        self.assertEqual(layer.uri, OSM_XYZ_URI)
        self.assertEqual(
            layer.properties.attribution,
            "© OpenStreetMap contributors",
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

    def test_private_layer_ids_are_stable(self):
        private_ids = {
            spec.key: spec.layer_id for spec in LAYER_SPECS if spec.private
        }
        self.assertEqual(
            private_ids,
            {
                "desordre_localisations": (
                    "sirs_desordre_localisations_reperage"
                ),
                "systemes_bornes": "sirs_link_systemes_reperage_bornes",
            },
        )

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

    def test_private_layers_are_registered_but_absent_from_layer_tree(self):
        project = FakeProject()
        layers = {
            spec.key: FakeLayer(spec.layer_id) for spec in ALL_LAYER_SPECS
        }
        groups = {
            path: FakeGroup(project.layerTreeRoot())
            for path in GROUP_PATHS
        }

        _register_layers(project, groups, layers)

        self.assertEqual(
            set(project.mapLayers()),
            {spec.layer_id for spec in ALL_LAYER_SPECS},
        )
        for spec in (item for item in LAYER_SPECS if item.private):
            self.assertIs(project.mapLayer(spec.layer_id), layers[spec.key])
            self.assertIsNone(project.layerTreeRoot().findLayer(spec.layer_id))
        osm_node = project.layerTreeRoot().findLayer(OSM_LAYER_SPEC.layer_id)
        self.assertIsNotNone(osm_node)
        self.assertTrue(osm_node.visible)

    def test_relations_use_the_project_context_after_layer_registration(self):
        project = FakeProject()
        layers = {
            spec.key: FakeLayer(spec.layer_id) for spec in ALL_LAYER_SPECS
        }
        groups = {
            path: FakeGroup(project.layerTreeRoot())
            for path in GROUP_PATHS
        }
        _register_layers(project, groups, layers)

        _create_relations(
            {
                "QgsRelation": FakeRelation,
                "QgsRelationContext": FakeRelationContext,
            },
            project,
            layers,
        )

        relations = project.relationManager().relations
        self.assertEqual(len(relations), 3)
        self.assertTrue(all(relation.isValid() for relation in relations))
        self.assertEqual(
            {relation.relation_id for relation in relations},
            {spec.relation_id for spec in RELATION_SPECS},
        )
        self.assertTrue(
            all(
                relation.child_layer_id
                == "sirs_desordre_localisations_reperage"
                for relation in relations
            )
        )

    def test_group_tree_and_localisation_representation_are_readable(self):
        self.assertIn(("SIRS", "Patrimoine"), GROUP_PATHS)
        self.assertIn(("SIRS", "Désordres"), GROUP_PATHS)
        self.assertIn(("SIRS", "Repérage"), GROUP_PATHS)
        self.assertIn(("SIRS", "Diagnostic"), GROUP_PATHS)
        self.assertEqual(GROUP_PATHS[-1], ("Fonds de carte",))
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
