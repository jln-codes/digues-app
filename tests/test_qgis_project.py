import gc
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dotenv import load_dotenv

from sirs_postgre.qgis_project import (
    ALL_LAYER_SPECS,
    DEFAULT_QGIS_PROJECT_PATH,
    DESORDRE_FILTERS,
    DESORDRE_GENERAL_FIELDS,
    FORM_SYNCHRONIZATION_MESSAGE,
    GROUP_PATHS,
    LAYER_SPECS,
    LINE_COORDINATE_FIELDS,
    LOCALISATION_DISPLAY_EXPRESSION,
    LOCALISATION_HIDDEN_FIELDS,
    LOCALISATION_VISIBLE_FIELDS,
    MINIMUM_QGIS_VERSION_INT,
    OSM_LAYER_SPEC,
    OSM_XYZ_URI,
    POINT_COORDINATE_FIELDS,
    POSITION_VALUE_MAP,
    PyQGISUnavailableError,
    QGISProjectError,
    RELATION_SPECS,
    _create_relations,
    _create_osm_layer,
    _configure_desordre_form,
    _configure_localisation_form,
    _clear_qgis_project,
    _load_pyqgis,
    _register_layers,
    _temporary_pgpassword,
    _verify_written_project,
    generate_qgis_project,
    pyqgis_available,
    qgis_connection_from_config,
)
from sirs_postgre.target import PostgreSQLConfig
from sirs_postgre.target.desordre_reperage import (
    TABLE_DEFINITIONS as DESORDRE_REPERAGE_TABLE_DEFINITIONS,
)
from sirs_postgre.target.schema import TABLE_DEFINITIONS as CORE_TABLE_DEFINITIONS


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


class FakeFields:
    def __init__(self, names):
        self.names = list(names)

    def indexFromName(self, name):
        try:
            return self.names.index(name)
        except ValueError:
            return -1


class FakeEditorWidgetSetup:
    def __init__(self, widget_type, config):
        self.widget_type = widget_type
        self.config = config


class FakeField:
    def __init__(self, name, _field_type):
        self.name = name


class FakeAttributeElement:
    def __init__(self, name, _index_or_parent, parent=None):
        self.name = name
        self.parent = parent


class FakeAttributeContainer:
    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent
        self.children = []
        self.visibility_expression = None

    def addChildElement(self, child):
        self.children.append(child)

    def setVisibilityExpression(self, expression):
        self.visibility_expression = expression


class FakeEditFormConfig:
    def __init__(self):
        self.root = FakeAttributeContainer("root")
        self.current_layout = None
        self.read_only = set()

    def clearTabs(self):
        self.root.children.clear()

    def setLayout(self, layout):
        self.current_layout = layout

    def invisibleRootContainer(self):
        return self.root

    def setReadOnly(self, index, read_only):
        if read_only:
            self.read_only.add(index)
        else:
            self.read_only.discard(index)


class FakeEditableLayer(FakeLayer):
    def __init__(self, layer_id, fields):
        super().__init__(layer_id)
        self._fields = FakeFields(fields)
        self.widgets = {}
        self.aliases = {}
        self.expressions = {}
        self.form = FakeEditFormConfig()
        self.display_expression = None

    def fields(self):
        return self._fields

    def setEditorWidgetSetup(self, index, setup):
        self.widgets[self._fields.names[index]] = setup

    def setFieldAlias(self, index, alias):
        self.aliases[self._fields.names[index]] = alias

    def addExpressionField(self, expression, field):
        self._fields.names.append(field.name)
        index = len(self._fields.names) - 1
        self.expressions[field.name] = expression
        return index

    def editFormConfig(self):
        return self.form

    def setEditFormConfig(self, form):
        self.form = form

    def setDisplayExpression(self, expression):
        self.display_expression = expression


class FakeQgis:
    class AttributeFormLayout:
        DragAndDrop = "drag-and-drop"


class FakeVariant:
    Double = "double"
    String = "string"


class FakeExpression:
    def __init__(self, expression):
        self.expression = expression


class FakeOptionalExpression:
    def __init__(self, expression):
        self.expression = expression


FORM_API = {
    "Qgis": FakeQgis,
    "QVariant": FakeVariant,
    "QgsField": FakeField,
    "QgsEditorWidgetSetup": FakeEditorWidgetSetup,
    "QgsAttributeEditorContainer": FakeAttributeContainer,
    "QgsAttributeEditorField": FakeAttributeElement,
    "QgsAttributeEditorRelation": FakeAttributeElement,
    "QgsExpression": FakeExpression,
    "QgsOptionalExpression": FakeOptionalExpression,
}


class RecordingClearContainer(dict):
    def __init__(self, name, events):
        super().__init__({"wrapper": object()})
        self.name = name
        self.events = events

    def clear(self):
        self.events.append(self.name)
        super().clear()


class RecordingClearProject:
    def __init__(self, events, *, readable=True):
        self.events = events
        self.readable = readable

    def read(self, _path):
        return self.readable

    def clear(self):
        self.events.append("project")


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
        self.assertEqual(
            by_key["desordres_point"].table,
            "view_desordres_points_saisie",
        )
        self.assertEqual(by_key["desordres_point"].subset, "")
        for key, subset in expected.items():
            with self.subTest(key=key):
                if key != "desordres_point":
                    self.assertEqual(by_key[key].table, "desordres")
                    self.assertEqual(by_key[key].subset, subset)
                self.assertEqual(by_key[key].geometry_column, "geometry")

    def test_child_table_is_private_and_has_no_primary_geometry(self):
        by_key = {spec.key: spec for spec in LAYER_SPECS}
        child = by_key["desordre_localisations"]
        self.assertTrue(child.private)
        self.assertIsNone(child.group_path)
        self.assertEqual(child.geometry_column, "")
        self.assertNotIn("position_debut_source", LOCALISATION_HIDDEN_FIELDS)
        self.assertNotIn("position_fin_source", LOCALISATION_HIDDEN_FIELDS)

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
                "desordre_troncons": "sirs_link_desordres_troncons",
                "systemes_bornes": "sirs_view_systemes_reperage_bornes",
            },
        )

    def test_relation_ids_are_deterministic_and_cover_each_parent(self):
        self.assertEqual(
            tuple(spec.relation_id for spec in RELATION_SPECS),
            (
                "desordre_point_localisations_reperage",
                "desordre_ligne_localisations_reperage",
                "desordre_polygone_localisations_reperage",
                "desordre_point_troncons",
                "desordre_ligne_troncons",
                "desordre_polygone_troncons",
            ),
        )
        self.assertEqual(
            {spec.parent_layer_key for spec in RELATION_SPECS},
            {"desordres_point", "desordres_line", "desordres_polygon"},
        )
        self.assertEqual(
            {spec.child_layer_key for spec in RELATION_SPECS},
            {"desordre_localisations", "desordre_troncons"},
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
        self.assertEqual(len(relations), 6)
        self.assertTrue(all(relation.isValid() for relation in relations))
        self.assertEqual(
            {relation.relation_id for relation in relations},
            {spec.relation_id for spec in RELATION_SPECS},
        )
        self.assertTrue(
            {relation.child_layer_id for relation in relations}
            == {
                "sirs_desordre_localisations_reperage",
                "sirs_link_desordres_troncons",
            }
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

    def test_sirs_position_vocabulary_excludes_sur_borne(self):
        self.assertEqual(
            POSITION_VALUE_MAP,
            {
                "map": [
                    {"Amont": "AVANT_BORNE"},
                    {"Aval": "APRES_BORNE"},
                ]
            },
        )
        self.assertNotIn("SUR_BORNE", repr(POSITION_VALUE_MAP))
        self.assertIn(
            'WHEN "distance_debut_m" = 0 THEN \' sur la borne\'',
            LOCALISATION_DISPLAY_EXPRESSION,
        )

    def test_localisation_widgets_filter_systems_and_bornes_by_label(self):
        fields = set(LOCALISATION_VISIBLE_FIELDS)
        fields.update(LOCALISATION_HIDDEN_FIELDS)
        layer = FakeEditableLayer("child", sorted(fields))
        layers = {
            "troncons": FakeLayer("sirs_troncons"),
            "systemes_reperage": FakeLayer("sirs_systemes_reperage"),
            "bornes_reperage": FakeLayer("sirs_bornes_reperage"),
            "systemes_bornes": FakeLayer("sirs_view_systemes_reperage_bornes"),
        }

        _configure_localisation_form(FORM_API, layer, layers)

        systeme = layer.widgets["systeme_reperage_id"]
        self.assertEqual(systeme.widget_type, "ValueRelation")
        self.assertIn("current_value('troncon_id')", systeme.config["FilterExpression"])
        for field_name in ("borne_debut_id", "borne_fin_id"):
            with self.subTest(field=field_name):
                setup = layer.widgets[field_name]
                self.assertEqual(setup.widget_type, "ValueRelation")
                self.assertEqual(setup.config["Key"], "borne_id")
                self.assertEqual(setup.config["Value"], "libelle_affichage")
                self.assertIn(
                    "current_value('systeme_reperage_id')",
                    setup.config["FilterExpression"],
                )
        for field_name in ("position_debut_relative", "position_fin_relative"):
            self.assertEqual(layer.widgets[field_name].config, POSITION_VALUE_MAP)

    def test_localisation_form_exposes_only_operational_fields(self):
        fields = set(LOCALISATION_VISIBLE_FIELDS)
        fields.update(LOCALISATION_HIDDEN_FIELDS)
        layer = FakeEditableLayer("child", sorted(fields))
        layers = {
            "troncons": FakeLayer("sirs_troncons"),
            "systemes_reperage": FakeLayer("sirs_systemes_reperage"),
            "bornes_reperage": FakeLayer("sirs_bornes_reperage"),
            "systemes_bornes": FakeLayer("sirs_view_systemes_reperage_bornes"),
        }

        _configure_localisation_form(FORM_API, layer, layers)

        read_only_names = {
            layer._fields.names[index] for index in layer.form.read_only
        }
        self.assertEqual(
            read_only_names,
            {"troncon_id", "pr_debut", "pr_fin"},
        )
        for field_name in LOCALISATION_HIDDEN_FIELDS:
            if field_name in layer._fields.names:
                self.assertEqual(layer.widgets[field_name].widget_type, "Hidden")
        groups = layer.form.root.children
        self.assertEqual([group.name for group in groups], ["Repérage"])
        self.assertTrue(all(len(group.children) >= 2 for group in groups))
        self.assertIn("pr_debut", [item.name for item in groups[0].children])

    def test_point_coordinates_are_editable_and_reperage_is_conditional(self):
        fields = [*DESORDRE_GENERAL_FIELDS, *(s.name for s in POINT_COORDINATE_FIELDS)]
        layer = FakeEditableLayer("sirs_desordres_points", fields)

        _configure_desordre_form(
            FORM_API,
            layer,
            "desordre_point_localisations_reperage",
            "desordre_point_troncons",
            coordinate_fields=POINT_COORDINATE_FIELDS,
            coordinates_editable=True,
        )

        for spec in POINT_COORDINATE_FIELDS:
            self.assertNotIn(spec.name, layer.expressions)
            self.assertEqual(layer.widgets[spec.name].config["Precision"], 6 if "4326" in spec.name else 2)
        root_items = layer.form.root.children
        groups = [item for item in root_items if isinstance(item, FakeAttributeContainer)]
        self.assertEqual([group.name for group in groups], ["Général", "Coordonnées", "Repérage"])
        self.assertTrue(all(len(group.children) >= 2 for group in groups))
        visibility = groups[-1].visibility_expression.expression.expression
        self.assertIn("relation_aggregate", visibility)
        self.assertIn("count", visibility)
        self.assertIn("= 1", visibility)
        self.assertIn("geometry_type", visibility)
        self.assertEqual(
            layer.expressions["synchronisation_formulaire"],
            repr(FORM_SYNCHRONIZATION_MESSAGE),
        )
        self.assertIn(
            "Repérage indisponible : plusieurs tronçons sont associés au désordre.",
            layer.expressions["statut_reperage_formulaire"],
        )
        self.assertIn("après application", FORM_SYNCHRONIZATION_MESSAGE)
        self.assertIn("une seule famille", FORM_SYNCHRONIZATION_MESSAGE.casefold())
        self.assertIn(
            "synchronisation_formulaire",
            [item.name for item in root_items],
        )

    def test_line_has_endpoint_coordinates_and_polygon_does_not(self):
        for layer_id, coordinate_fields in (
            ("sirs_desordres_lignes", LINE_COORDINATE_FIELDS),
            ("sirs_desordres_polygones", ()),
        ):
            with self.subTest(layer=layer_id):
                layer = FakeEditableLayer(layer_id, DESORDRE_GENERAL_FIELDS)
                _configure_desordre_form(
                    FORM_API,
                    layer,
                    "relation_id",
                    "troncon_relation_id",
                    coordinate_fields=coordinate_fields,
                )
                for spec in coordinate_fields:
                    self.assertIn(spec.name, layer.expressions)
                self.assertEqual(
                    bool(coordinate_fields),
                    "Coordonnées" in [item.name for item in layer.form.root.children],
                )

    def test_coordinate_fields_do_not_exist_in_postgresql_definition(self):
        sql = "\n".join(
            [
                *CORE_TABLE_DEFINITIONS.values(),
                *DESORDRE_REPERAGE_TABLE_DEFINITIONS.values(),
            ]
        )
        for spec in POINT_COORDINATE_FIELDS:
            self.assertNotIn(spec.name, "\n".join(CORE_TABLE_DEFINITIONS.values()))

    def test_form_configuration_is_deterministic(self):
        def snapshot():
            fields = set(LOCALISATION_VISIBLE_FIELDS)
            fields.update(LOCALISATION_HIDDEN_FIELDS)
            layer = FakeEditableLayer("child", sorted(fields))
            layers = {
                "troncons": FakeLayer("sirs_troncons"),
                "systemes_reperage": FakeLayer("sirs_systemes_reperage"),
                "bornes_reperage": FakeLayer("sirs_bornes_reperage"),
                "systemes_bornes": FakeLayer(
                    "sirs_view_systemes_reperage_bornes"
                ),
            }
            _configure_localisation_form(FORM_API, layer, layers)
            return (
                layer._fields.names,
                {
                    name: (setup.widget_type, setup.config)
                    for name, setup in layer.widgets.items()
                },
                layer.aliases,
                layer.expressions,
                [
                    (group.name, [item.name for item in group.children])
                    for group in layer.form.root.children
                ],
            )

        self.assertEqual(snapshot(), snapshot())

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
            PyQGISUnavailableError, "QGIS/OSGeo4W|Sous Linux|QGIS 3.38"
        ):
            _load_pyqgis()

    def test_qgis_cleanup_releases_wrappers_before_project(self):
        events = []
        groups = RecordingClearContainer("groups", events)
        layers = RecordingClearContainer("layers", events)
        project = RecordingClearProject(events)

        with patch(
            "sirs_postgre.qgis_project.gc.collect",
            side_effect=lambda: events.append("gc"),
        ):
            _clear_qgis_project(project, groups, layers)

        self.assertEqual(events, ["groups", "layers", "gc", "project", "gc"])
        self.assertFalse(groups)
        self.assertFalse(layers)

    def test_failed_verification_also_clears_its_project(self):
        events = []
        verification = RecordingClearProject(events, readable=False)
        with patch(
            "sirs_postgre.qgis_project.gc.collect",
            side_effect=lambda: events.append("gc"),
        ):
            with self.assertRaisesRegex(QGISProjectError, "QGZ écrit est illisible"):
                _verify_written_project(
                    {"QgsProject": lambda: verification},
                    Path("invalid.qgz"),
                )

        self.assertEqual(events, ["gc", "project", "gc", "gc"])


@unittest.skipUnless(pyqgis_available(), "PyQGIS indisponible")
class QGISProjectIntegrationTest(unittest.TestCase):
    def test_generation_reloads_cleans_up_and_returns_normally(self):
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
            gc.collect()
            self.assertTrue(output.is_file())
            self.assertEqual(set(result.relation_ids), {
                spec.relation_id for spec in RELATION_SPECS
            })


if __name__ == "__main__":
    unittest.main()
