"""Génération reproductible du projet QGIS pilote de digues-app.

Ce module reste importable sans QGIS. Tous les imports ``qgis.*`` sont confinés
à :func:`_load_pyqgis`, appelée uniquement par la commande de génération.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import gc
import os
from pathlib import Path
from typing import Any, Iterator

from .target import PostgreSQLConfig


DEFAULT_QGIS_PROJECT_PATH = Path("qgis/digues_app.qgz")
TARGET_SRID = 3950
MINIMUM_QGIS_VERSION_INT = 33800


class QGISProjectError(RuntimeError):
    """Le projet QGIS n'a pas pu être construit ou vérifié."""


class PyQGISUnavailableError(QGISProjectError):
    """Le Python utilisé ne fournit pas les bindings PyQGIS."""


@dataclass(frozen=True)
class LayerSpec:
    key: str
    layer_id: str
    name: str
    table: str
    geometry_column: str = ""
    key_column: str = "id"
    subset: str = ""
    wkb_type: str | None = None
    group_path: tuple[str, ...] | None = None
    private: bool = False
    read_only: bool = False
    color: str | None = None


@dataclass(frozen=True)
class RelationSpec:
    relation_id: str
    name: str
    parent_layer_key: str
    child_layer_key: str
    parent_field: str = "id"
    child_field: str = "desordre_id"


@dataclass(frozen=True)
class RasterLayerSpec:
    key: str
    layer_id: str
    name: str
    uri: str
    provider: str
    group_path: tuple[str, ...]
    private: bool = False


@dataclass(frozen=True)
class QGISConnection:
    host: str
    port: int
    database: str
    user: str
    authcfg: str | None = None

    @property
    def safe_description(self) -> str:
        return f"{self.user}@{self.host}:{self.port}/{self.database}"


@dataclass(frozen=True)
class QGISProjectResult:
    output: Path
    layer_ids: tuple[str, ...]
    relation_ids: tuple[str, ...]
    groups: tuple[str, ...]
    connection: str


@dataclass(frozen=True)
class VirtualFieldSpec:
    """Champ calculé uniquement dans QGIS, sans modification de PostgreSQL."""

    name: str
    alias: str
    expression: str
    variant: str = "Double"


GROUP_PATHS = (
    ("SIRS",),
    ("SIRS", "Patrimoine"),
    ("SIRS", "Désordres"),
    ("SIRS", "Repérage"),
    ("SIRS", "Diagnostic"),
    ("Fonds de carte",),
)

OSM_XYZ_URI = (
    "type=xyz&url=https://tile.openstreetmap.org/"
    "%7Bz%7D/%7Bx%7D/%7By%7D.png&zmax=19&zmin=0&crs=EPSG3857"
)

OSM_LAYER_SPEC = RasterLayerSpec(
    key="openstreetmap",
    layer_id="sirs_openstreetmap",
    name="OpenStreetMap",
    uri=OSM_XYZ_URI,
    provider="wms",
    group_path=("Fonds de carte",),
)

DESORDRE_FILTERS = {
    "point": "GeometryType(\"geometry\") = 'POINT'",
    "line": "GeometryType(\"geometry\") = 'LINESTRING'",
    "polygon": "GeometryType(\"geometry\") = 'POLYGON'",
}

LAYER_SPECS = (
    LayerSpec(
        "troncons",
        "sirs_troncons",
        "Tronçons",
        "troncons",
        "geometry",
        wkb_type="LineString",
        group_path=("SIRS", "Patrimoine"),
        color="#5f6f52",
    ),
    LayerSpec(
        "desordres_point",
        "sirs_desordres_points",
        "Désordres — Points",
        "view_desordres_points_saisie",
        "geometry",
        wkb_type="Point",
        group_path=("SIRS", "Désordres"),
        color="#d73027",
    ),
    LayerSpec(
        "desordres_line",
        "sirs_desordres_lignes",
        "Désordres — Lignes",
        "desordres",
        "geometry",
        subset=DESORDRE_FILTERS["line"],
        wkb_type="LineString",
        group_path=("SIRS", "Désordres"),
        color="#fc8d59",
    ),
    LayerSpec(
        "desordres_polygon",
        "sirs_desordres_polygones",
        "Désordres — Polygones",
        "desordres",
        "geometry",
        subset=DESORDRE_FILTERS["polygon"],
        wkb_type="Polygon",
        group_path=("SIRS", "Désordres"),
        color="#fee08b",
    ),
    LayerSpec(
        "systemes_reperage",
        "sirs_systemes_reperage",
        "Systèmes de repérage",
        "systemes_reperage",
        group_path=("SIRS", "Repérage"),
    ),
    LayerSpec(
        "bornes_reperage",
        "sirs_bornes_reperage",
        "Bornes",
        "bornes_reperage",
        "geometry",
        wkb_type="Point",
        group_path=("SIRS", "Repérage"),
        color="#2c7bb6",
    ),
    LayerSpec(
        "diagnostic_reperage",
        "sirs_diagnostic_reperage_desordres",
        "Diagnostic repérage des désordres",
        "view_desordre_localisations_reperage",
        group_path=("SIRS", "Diagnostic"),
        read_only=True,
    ),
    # La table enfant est enregistrée dans QgsProject mais privée et absente de
    # l'arbre. Une source sans colonne géométrique empêche ses deux Point de
    # traçabilité historique de devenir des couches cartographiques.
    LayerSpec(
        "desordre_localisations",
        "sirs_desordre_localisations_reperage",
        "Localisations de repérage des désordres",
        "desordre_localisations_reperage",
        private=True,
    ),
    LayerSpec(
        "desordre_troncons",
        "sirs_link_desordres_troncons",
        "Tronçons concernés par les désordres",
        "link_desordres_troncons",
        private=True,
    ),
    # Vue privée fournissant les rôles spatiaux début/fin dans le système.
    LayerSpec(
        "systemes_bornes",
        "sirs_view_systemes_reperage_bornes",
        "Liens systèmes–bornes (technique)",
        "view_systemes_reperage_bornes",
        private=True,
        read_only=True,
    ),
)

ALL_LAYER_SPECS = (*LAYER_SPECS, OSM_LAYER_SPEC)

RELATION_SPECS = (
    RelationSpec(
        "desordre_point_localisations_reperage",
        "Localisations de repérage — désordre ponctuel",
        "desordres_point",
        "desordre_localisations",
    ),
    RelationSpec(
        "desordre_ligne_localisations_reperage",
        "Localisations de repérage — désordre linéaire",
        "desordres_line",
        "desordre_localisations",
    ),
    RelationSpec(
        "desordre_polygone_localisations_reperage",
        "Localisations de repérage — désordre surfacique",
        "desordres_polygon",
        "desordre_localisations",
    ),
    RelationSpec(
        "desordre_point_troncons",
        "Tronçons concernés — désordre ponctuel",
        "desordres_point",
        "desordre_troncons",
    ),
    RelationSpec(
        "desordre_ligne_troncons",
        "Tronçons concernés — désordre linéaire",
        "desordres_line",
        "desordre_troncons",
    ),
    RelationSpec(
        "desordre_polygone_troncons",
        "Tronçons concernés — désordre surfacique",
        "desordres_polygon",
        "desordre_troncons",
    ),
)

DESORDRE_GENERAL_FIELDS = (
    "designation",
    "type_desordre_id",
    "commentaire",
    "date_debut",
    "date_fin",
    "valid",
)

POINT_COORDINATE_FIELDS = (
    VirtualFieldSpec("coord_x_3950", "X", "x($geometry)"),
    VirtualFieldSpec("coord_y_3950", "Y", "y($geometry)"),
    VirtualFieldSpec(
        "longitude_4326",
        "Longitude",
        "x(transform($geometry, 'EPSG:3950', 'EPSG:4326'))",
    ),
    VirtualFieldSpec(
        "latitude_4326",
        "Latitude",
        "y(transform($geometry, 'EPSG:3950', 'EPSG:4326'))",
    ),
)

FORM_SYNCHRONIZATION_MESSAGE = (
    "Une seule famille de saisie par opération. Les valeurs dérivées sont "
    "actualisées après application et relecture."
)

LINE_COORDINATE_FIELDS = (
    VirtualFieldSpec(
        "debut_x_3950", "X début", "x(start_point($geometry))"
    ),
    VirtualFieldSpec(
        "debut_y_3950", "Y début", "y(start_point($geometry))"
    ),
    VirtualFieldSpec(
        "fin_x_3950", "X fin", "x(end_point($geometry))"
    ),
    VirtualFieldSpec(
        "fin_y_3950", "Y fin", "y(end_point($geometry))"
    ),
)

LOCALISATION_VISIBLE_FIELDS = (
    "troncon_id",
    "systeme_reperage_id",
    "borne_debut_id",
    "distance_debut_m",
    "position_debut_relative",
    "pr_debut",
    "borne_fin_id",
    "distance_fin_m",
    "position_fin_relative",
    "pr_fin",
)

LOCALISATION_HIDDEN_FIELDS = (
    "id",
    "desordre_id",
    "offset_debut_m",
    "offset_fin_m",
    "valid",
)

FIELD_ALIASES = {
    "troncon_id": "Tronçon",
    "systeme_reperage_id": "Système de repérage",
    "borne_debut_id": "Borne de début",
    "distance_debut_m": "Distance (m)",
    "position_debut_relative": "Position",
    "borne_fin_id": "Borne de fin",
    "distance_fin_m": "Distance fin (m)",
    "position_fin_relative": "Position fin",
    "pr_debut": "PR début",
    "pr_fin": "PR fin",
    "valid": "Valide",
}

POSITION_VALUE_MAP = {
    "map": [
        {"Amont": "AVANT_BORNE"},
        {"Aval": "APRES_BORNE"},
    ]
}

LOCALISATION_DISPLAY_EXPRESSION = """
with_variable(
  'troncon_label',
  attribute(get_feature('Tronçons', 'id', "troncon_id"), 'libelle'),
  with_variable(
    'borne_label',
    attribute(get_feature('Bornes', 'id', "borne_debut_id"), 'libelle'),
    concat(
      coalesce(@troncon_label, 'Tronçon ?'),
      ' — ',
      coalesce(@borne_label, 'Borne ?'),
      CASE
        WHEN "distance_debut_m" IS NULL THEN ''
        ELSE concat(' ', format_number("distance_debut_m", 2), ' m')
      END,
      CASE
        WHEN "distance_debut_m" = 0 THEN ' sur la borne'
        WHEN "position_debut_relative" = 'AVANT_BORNE' THEN ' amont'
        WHEN "position_debut_relative" = 'APRES_BORNE' THEN ' aval'
        ELSE ''
      END
    )
  )
)
""".strip()


def pyqgis_available() -> bool:
    """Teste un PyQGIS compatible sans confondre le dossier local ``qgis/``."""

    try:
        from qgis.core import Qgis, QgsApplication  # type: ignore
    except (ImportError, ModuleNotFoundError):
        return False
    return (
        QgsApplication is not None
        and Qgis.QGIS_VERSION_INT >= MINIMUM_QGIS_VERSION_INT
    )


def qgis_connection_from_config(
    config: PostgreSQLConfig,
    *,
    authcfg: str | None = None,
) -> QGISConnection:
    """Extrait la connexion existante sans exposer ni conserver le mot de passe."""

    host = config.host
    port = config.port
    database = config.database
    user = config.user
    if config.dsn:
        try:
            from psycopg.conninfo import conninfo_to_dict

            values = conninfo_to_dict(config.dsn)
        except Exception as exc:
            raise QGISProjectError(
                "Impossible de convertir SIRS_POSTGRE_DSN en connexion QGIS"
            ) from exc
        host = str(values.get("host") or host)
        port = int(values.get("port") or port)
        database = str(values.get("dbname") or database)
        user = str(values.get("user") or user)
    if not host or not database or not user:
        raise QGISProjectError(
            "La connexion QGIS nécessite host, port, database et user"
        )
    return QGISConnection(host, port, database, user, authcfg or None)


def _runtime_password(config: PostgreSQLConfig) -> str | None:
    if config.password:
        return config.password
    if not config.dsn:
        return None
    try:
        from psycopg.conninfo import conninfo_to_dict

        value = conninfo_to_dict(config.dsn).get("password")
        return str(value) if value else None
    except Exception:
        return None


@contextmanager
def _temporary_pgpassword(password: str | None) -> Iterator[None]:
    """Autorise libpq pendant la génération sans écrire le secret dans le QGZ."""

    previous = os.environ.get("PGPASSWORD")
    if password:
        os.environ["PGPASSWORD"] = password
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("PGPASSWORD", None)
        else:
            os.environ["PGPASSWORD"] = previous


def _load_pyqgis() -> dict[str, Any]:
    try:
        from qgis.PyQt.QtCore import QVariant  # type: ignore
        from qgis.PyQt.QtGui import QColor  # type: ignore
        from qgis.core import (  # type: ignore
            Qgis,
            QgsApplication,
            QgsAttributeEditorContainer,
            QgsAttributeEditorField,
            QgsAttributeEditorRelation,
            QgsCoordinateReferenceSystem,
            QgsDataSourceUri,
            QgsEditorWidgetSetup,
            QgsExpression,
            QgsField,
            QgsMapLayer,
            QgsOptionalExpression,
            QgsProject,
            QgsRasterLayer,
            QgsRelation,
            QgsRelationContext,
            QgsSingleSymbolRenderer,
            QgsSymbol,
            QgsVectorLayer,
        )
    except (ImportError, ModuleNotFoundError) as exc:
        raise PyQGISUnavailableError(
            "PyQGIS est indisponible dans ce Python. Sous Windows, utilisez "
            "l’environnement QGIS/OSGeo4W (par exemple python-qgis.bat). "
            "Sous Linux, utilisez un Python ayant accès aux bindings PyQGIS "
            "système de l’installation QGIS. Aucun QGZ n’a été créé."
        ) from exc
    if Qgis.QGIS_VERSION_INT < MINIMUM_QGIS_VERSION_INT:
        raise PyQGISUnavailableError(
            "QGIS 3.38 ou plus récent est requis pour produire des layer IDs "
            "stables. Version détectée : " + Qgis.QGIS_VERSION
        )
    return locals()


def _layer_error(layer: Any) -> str:
    try:
        return str(layer.error().summary())
    except Exception:
        return "erreur inconnue du fournisseur PostgreSQL"


def _set_widget(layer: Any, field_name: str, setup: Any) -> None:
    index = layer.fields().indexFromName(field_name)
    if index >= 0:
        layer.setEditorWidgetSetup(index, setup)


def _set_alias(layer: Any, field_name: str, alias: str) -> None:
    index = layer.fields().indexFromName(field_name)
    if index >= 0:
        layer.setFieldAlias(index, alias)


def _add_fields_to_container(
    api: dict[str, Any], layer: Any, container: Any, field_names: tuple[str, ...]
) -> None:
    editor_field = api["QgsAttributeEditorField"]
    for field_name in field_names:
        index = layer.fields().indexFromName(field_name)
        if index >= 0:
            container.addChildElement(editor_field(field_name, index, container))


def _add_virtual_fields(
    api: dict[str, Any], layer: Any, specs: tuple[VirtualFieldSpec, ...]
) -> None:
    """Ajoute des expressions déterministes et explicitement non modifiables."""

    for spec in specs:
        index = layer.fields().indexFromName(spec.name)
        if index < 0:
            index = layer.addExpressionField(
                spec.expression,
                api["QgsField"](spec.name, getattr(api["QVariant"], spec.variant)),
            )
        if index < 0:
            raise QGISProjectError(f"Champ virtuel QGIS refusé : {spec.name}")
        layer.setFieldAlias(index, spec.alias)


def _add_group(
    api: dict[str, Any],
    layer: Any,
    root: Any,
    name: str,
    field_names: tuple[str, ...],
) -> None:
    """Crée seulement les groupes contenant réellement plusieurs champs."""

    present = tuple(
        field_name
        for field_name in field_names
        if layer.fields().indexFromName(field_name) >= 0
    )
    if len(present) < 2:
        _add_fields_to_container(api, layer, root, present)
        return
    container = api["QgsAttributeEditorContainer"](name, root)
    root.addChildElement(container)
    _add_fields_to_container(api, layer, container, present)


def _configure_desordre_form(
    api: dict[str, Any],
    layer: Any,
    localisation_relation_id: str,
    troncons_relation_id: str,
    *,
    coordinate_fields: tuple[VirtualFieldSpec, ...] = (),
    coordinates_editable: bool = False,
) -> None:
    if coordinate_fields:
        _add_virtual_fields(api, layer, coordinate_fields)
    status_fields = (
        VirtualFieldSpec(
            "statut_reperage_formulaire",
            "Disponibilité du repérage",
            "with_variable('n', relation_aggregate("
            f"'{troncons_relation_id}', 'count', \"id\"), "
            "CASE WHEN @n = 0 THEN 'Repérage indisponible : aucun tronçon associé.' "
            "WHEN @n > 1 THEN 'Repérage indisponible : plusieurs tronçons sont associés au désordre.' "
            "ELSE 'Repérage disponible.' END)",
            "String",
        ),
        VirtualFieldSpec(
            "synchronisation_formulaire",
            "Saisie",
            repr(FORM_SYNCHRONIZATION_MESSAGE),
            "String",
        ),
        VirtualFieldSpec(
            "avertissement_recalage",
            "Attention",
            "CASE WHEN geometry_type($geometry) = 'LineString' THEN "
            "'Modifier le repérage remplacera la ligne par la portion du tronçon.' "
            "ELSE 'Modifier le repérage repositionnera le point sur le tronçon.' END",
            "String",
        ),
    )
    _add_virtual_fields(api, layer, status_fields)
    config = layer.editFormConfig()
    for spec in coordinate_fields:
        index = layer.fields().indexFromName(spec.name)
        if index >= 0 and not coordinates_editable:
            config.setReadOnly(index, True)
    for spec in status_fields:
        index = layer.fields().indexFromName(spec.name)
        if index >= 0:
            config.setReadOnly(index, True)
    if coordinates_editable:
        for spec in coordinate_fields:
            precision = 6 if spec.name in {"longitude_4326", "latitude_4326"} else 2
            _set_widget(
                layer,
                spec.name,
                api["QgsEditorWidgetSetup"](
                    "Range",
                    {
                        "Min": -1_000_000_000.0,
                        "Max": 1_000_000_000.0,
                        "Step": 10 ** (-precision),
                        "Precision": precision,
                        "Style": "SpinBox",
                        "AllowNull": False,
                    },
                ),
            )
    config.clearTabs()
    config.setLayout(api["Qgis"].AttributeFormLayout.DragAndDrop)
    root = config.invisibleRootContainer()
    _add_group(api, layer, root, "Général", DESORDRE_GENERAL_FIELDS)
    if coordinate_fields:
        _add_group(
            api,
            layer,
            root,
            "Coordonnées",
            tuple(spec.name for spec in coordinate_fields),
        )
    root.addChildElement(
        api["QgsAttributeEditorRelation"](troncons_relation_id, root)
    )
    _add_fields_to_container(
        api,
        layer,
        root,
        ("statut_reperage_formulaire", "synchronisation_formulaire"),
    )
    # Deux éléments cohérents justifient ce groupe conditionnel : avertissement
    # et formulaire de repérage. QField réévalue l'expression à l'ouverture.
    reperage = api["QgsAttributeEditorContainer"]("Repérage", root)
    root.addChildElement(reperage)
    _add_fields_to_container(api, layer, reperage, ("avertissement_recalage",))
    reperage.addChildElement(
        api["QgsAttributeEditorRelation"](localisation_relation_id, reperage)
    )
    reperage.setVisibilityExpression(
        api["QgsOptionalExpression"](
            api["QgsExpression"](
                "relation_aggregate("
                f"'{troncons_relation_id}', 'count', \"id\") = 1 "
                "AND geometry_type($geometry) IN ('Point', 'LineString')"
            )
        )
    )
    layer.setEditFormConfig(config)
    layer.setDisplayExpression(
        "coalesce(\"designation\", concat('Désordre ', left(to_string(\"id\"), 8)))"
    )


def _configure_localisation_form(
    api: dict[str, Any], layer: Any, layers: dict[str, Any]
) -> None:
    hidden = api["QgsEditorWidgetSetup"]("Hidden", {})
    for field_name in LOCALISATION_HIDDEN_FIELDS:
        _set_widget(layer, field_name, hidden)
    for field_name, alias in FIELD_ALIASES.items():
        _set_alias(layer, field_name, alias)

    value_relation = api["QgsEditorWidgetSetup"]
    _set_widget(
        layer,
        "troncon_id",
        value_relation(
            "ValueRelation",
            {
                "Layer": layers["troncons"].id(),
                "Key": "id",
                "Value": "libelle",
                "AllowNull": True,
                "OrderByValue": True,
                "UseCompleter": True,
            },
        ),
    )
    _set_widget(
        layer,
        "systeme_reperage_id",
        value_relation(
            "ValueRelation",
            {
                "Layer": layers["systemes_reperage"].id(),
                "Key": "id",
                "Value": "libelle",
                "AllowNull": True,
                "OrderByValue": True,
                "UseCompleter": True,
                "FilterExpression": (
                    '"troncon_id" = current_value(\'troncon_id\')'
                ),
            },
        ),
    )
    for field_name in ("borne_debut_id", "borne_fin_id"):
        _set_widget(
            layer,
            field_name,
            value_relation(
                "ValueRelation",
                {
                    "Layer": layers["systemes_bornes"].id(),
                    "Key": "borne_id",
                    "Value": "libelle_affichage",
                    "AllowNull": True,
                    "OrderByValue": True,
                    "UseCompleter": True,
                    "FilterExpression": (
                        '"systeme_reperage_id" = '
                        "current_value('systeme_reperage_id')"
                    ),
                },
            ),
        )
    value_map = api["QgsEditorWidgetSetup"]
    for field_name in ("position_debut_relative", "position_fin_relative"):
        _set_widget(
            layer,
            field_name,
            value_map("ValueMap", POSITION_VALUE_MAP),
        )
    for field_name in ("distance_debut_m", "distance_fin_m"):
        _set_widget(
            layer,
            field_name,
            api["QgsEditorWidgetSetup"](
                "Range",
                {
                    "Min": 0.0,
                    "Max": 1_000_000.0,
                    "Step": 0.01,
                    "Precision": 2,
                    "Style": "SpinBox",
                    "AllowNull": True,
                },
            ),
        )
    for field_name in ("pr_debut", "pr_fin"):
        _set_widget(
            layer,
            field_name,
            api["QgsEditorWidgetSetup"](
                "Range",
                {
                    "Min": -1_000_000_000.0,
                    "Max": 1_000_000_000.0,
                    "Step": 0.01,
                    "Precision": 2,
                    "Style": "SpinBox",
                    "AllowNull": True,
                },
            ),
        )

    config = layer.editFormConfig()
    read_only_fields = ("troncon_id", "pr_debut", "pr_fin")
    for field_name in read_only_fields:
        index = layer.fields().indexFromName(field_name)
        if index >= 0:
            config.setReadOnly(index, True)
    config.clearTabs()
    config.setLayout(api["Qgis"].AttributeFormLayout.DragAndDrop)
    root = config.invisibleRootContainer()
    _add_group(
        api, layer, root, "Repérage", LOCALISATION_VISIBLE_FIELDS
    )
    layer.setEditFormConfig(config)
    layer.setDisplayExpression(LOCALISATION_DISPLAY_EXPRESSION)


def _configure_desordre_troncons_form(
    api: dict[str, Any], layer: Any, layers: dict[str, Any]
) -> None:
    hidden = api["QgsEditorWidgetSetup"]("Hidden", {})
    for field_name in ("id", "desordre_id"):
        _set_widget(layer, field_name, hidden)
    _set_alias(layer, "troncon_id", "Tronçon concerné")
    _set_widget(
        layer,
        "troncon_id",
        api["QgsEditorWidgetSetup"](
            "ValueRelation",
            {
                "Layer": layers["troncons"].id(),
                "Key": "id",
                "Value": "libelle",
                "AllowNull": False,
                "OrderByValue": True,
                "UseCompleter": True,
            },
        ),
    )
    config = layer.editFormConfig()
    config.clearTabs()
    config.setLayout(api["Qgis"].AttributeFormLayout.DragAndDrop)
    root = config.invisibleRootContainer()
    _add_fields_to_container(api, layer, root, ("troncon_id",))
    layer.setEditFormConfig(config)
    layer.setDisplayExpression(
        "attribute(get_feature('Tronçons', 'id', \"troncon_id\"), 'libelle')"
    )


def _configure_lookup_layers(layers: dict[str, Any]) -> None:
    for key in ("troncons", "systemes_reperage", "bornes_reperage"):
        layers[key].setDisplayExpression('coalesce("libelle", to_string("id"))')
    layers["diagnostic_reperage"].setDisplayExpression(
        'coalesce("resume_localisation", to_string("id"))'
    )


def _apply_simple_style(api: dict[str, Any], layer: Any, color: str | None) -> None:
    if not color or layer.geometryType() < 0:
        return
    symbol = api["QgsSymbol"].defaultSymbol(layer.geometryType())
    if symbol is None:
        return
    symbol.setColor(api["QColor"](color))
    layer.setRenderer(api["QgsSingleSymbolRenderer"](symbol))


def _create_layer(
    api: dict[str, Any], connection: QGISConnection, spec: LayerSpec
) -> Any:
    uri = api["QgsDataSourceUri"]()
    uri.setConnection(
        connection.host,
        str(connection.port),
        connection.database,
        connection.user,
        "",
        api["QgsDataSourceUri"].SslPrefer,
        connection.authcfg or "",
    )
    uri.setDataSource(
        "public",
        spec.table,
        spec.geometry_column,
        spec.subset,
        spec.key_column,
    )
    if spec.geometry_column:
        uri.setSrid(str(TARGET_SRID))
    if spec.wkb_type:
        uri.setWkbType(getattr(api["Qgis"].WkbType, spec.wkb_type))
    layer = api["QgsVectorLayer"](uri.uri(False), spec.name, "postgres")
    if not layer.isValid():
        raise QGISProjectError(
            f"Couche PostgreSQL invalide ({spec.name}) : {_layer_error(layer)}"
        )
    if not layer.setId(spec.layer_id):
        raise QGISProjectError(f"Layer ID QGIS refusé : {spec.layer_id}")
    if spec.private:
        layer.setFlags(layer.flags() | api["QgsMapLayer"].Private)
    if spec.read_only:
        layer.setReadOnly(True)
    _apply_simple_style(api, layer, spec.color)
    return layer


def _create_osm_layer(api: dict[str, Any]) -> Any:
    layer = api["QgsRasterLayer"](
        OSM_LAYER_SPEC.uri,
        OSM_LAYER_SPEC.name,
        OSM_LAYER_SPEC.provider,
    )
    if not layer.isValid():
        raise QGISProjectError(
            "Couche XYZ OpenStreetMap invalide : " + _layer_error(layer)
        )
    if not layer.setId(OSM_LAYER_SPEC.layer_id):
        raise QGISProjectError(
            f"Layer ID QGIS refusé : {OSM_LAYER_SPEC.layer_id}"
        )
    server_properties = layer.serverProperties()
    server_properties.setAttribution("© OpenStreetMap contributors")
    server_properties.setAttributionUrl(
        "https://www.openstreetmap.org/copyright"
    )
    return layer


def _create_groups(project: Any) -> dict[tuple[str, ...], Any]:
    root = project.layerTreeRoot()
    result: dict[tuple[str, ...], Any] = {(): root}
    for path in GROUP_PATHS:
        result[path] = result[path[:-1]].addGroup(path[-1])
    result[("SIRS", "Diagnostic")].setExpanded(False)
    return result


def _register_layers(
    project: Any,
    groups: dict[tuple[str, ...], Any],
    layers: dict[str, Any],
) -> None:
    """Enregistre toutes les couches avant toute résolution de relation.

    Les couches privées appartiennent au registre du projet mais ne reçoivent
    volontairement aucun nœud dans l'arbre des couches.
    """

    for spec in ALL_LAYER_SPECS:
        layer = layers[spec.key]
        registered = project.addMapLayer(layer, False)
        if registered is None or project.mapLayer(spec.layer_id) is None:
            raise QGISProjectError(
                f"Couche non enregistrée dans QgsProject : {spec.layer_id}"
            )
        if project.mapLayer(spec.layer_id).id() != spec.layer_id:
            raise QGISProjectError(
                f"Layer ID instable après enregistrement : {spec.layer_id}"
            )
        if spec.group_path is not None:
            node = groups[spec.group_path].addLayer(layer)
            node.setItemVisibilityChecked(True)

    for spec in (item for item in LAYER_SPECS if item.private):
        if project.layerTreeRoot().findLayer(spec.layer_id) is not None:
            raise QGISProjectError(
                f"Couche privée exposée dans le layer tree : {spec.layer_id}"
            )


def _create_relations(
    api: dict[str, Any], project: Any, layers: dict[str, Any]
) -> None:
    relation_context = api["QgsRelationContext"](project)
    for spec in RELATION_SPECS:
        relation = api["QgsRelation"](relation_context)
        relation.setId(spec.relation_id)
        relation.setName(spec.name)
        relation.setReferencedLayer(layers[spec.parent_layer_key].id())
        relation.setReferencingLayer(layers[spec.child_layer_key].id())
        relation.addFieldPair(spec.child_field, spec.parent_field)
        relation.updateRelationStatus()
        if not relation.isValid():
            raise QGISProjectError(
                f"Relation QGIS invalide {spec.relation_id}: "
                f"{relation.validationError()}"
            )
        project.relationManager().addRelation(relation)


def _clear_qgis_project(
    project: Any,
    *reference_containers: dict[Any, Any] | None,
) -> None:
    """Libère les wrappers Python avant les objets C++ possédés par le projet."""

    for container in reference_containers:
        if container is not None:
            container.clear()
    gc.collect()
    if project is not None:
        project.clear()
    gc.collect()


def _inspect_written_project(
    api: dict[str, Any], verification: Any, output: Path
) -> None:
    if not verification.read(str(output)):
        raise QGISProjectError(f"Le QGZ écrit est illisible : {output}")
    actual_layers = set(verification.mapLayers())
    expected_layers = {spec.layer_id for spec in ALL_LAYER_SPECS}
    if actual_layers != expected_layers:
        raise QGISProjectError(
            "Couche(s) absente(s) après relecture : "
            + ", ".join(sorted(expected_layers - actual_layers))
        )
    invalid_layers = sorted(
        layer_id
        for layer_id, layer in verification.mapLayers().items()
        if not layer.isValid()
    )
    if invalid_layers:
        raise QGISProjectError(
            "Source(s) PostgreSQL invalide(s) après relecture : "
            + ", ".join(invalid_layers)
        )
    actual_relations = set(verification.relationManager().relations())
    expected_relations = {spec.relation_id for spec in RELATION_SPECS}
    if actual_relations != expected_relations:
        raise QGISProjectError(
            "Relation(s) absente(s) après relecture : "
            + ", ".join(sorted(expected_relations - actual_relations))
        )
    invalid_relations = sorted(
        relation_id
        for relation_id, relation in (
            verification.relationManager().relations().items()
        )
        if not relation.isValid()
    )
    if invalid_relations:
        raise QGISProjectError(
            "Relation(s) invalide(s) après relecture : "
            + ", ".join(invalid_relations)
        )
    for path in GROUP_PATHS:
        if verification.layerTreeRoot().findGroup(path[-1]) is None:
            raise QGISProjectError(f"Groupe QGIS absent après relecture : {path[-1]}")
    basemap_group = verification.layerTreeRoot().findGroup("Fonds de carte")
    root_children = verification.layerTreeRoot().children()
    if (
        basemap_group is None
        or not root_children
        or root_children[-1].name() != "Fonds de carte"
    ):
        raise QGISProjectError(
            "Le groupe Fonds de carte n'est pas en bas du layer tree"
        )
    osm_node = basemap_group.findLayer(OSM_LAYER_SPEC.layer_id)
    if osm_node is None or not osm_node.itemVisibilityChecked():
        raise QGISProjectError(
            "Le fond OpenStreetMap n'est pas présent et activé par défaut"
        )
    for spec in (item for item in LAYER_SPECS if item.private):
        if verification.mapLayer(spec.layer_id) is None:
            raise QGISProjectError(
                f"Couche privée absente après relecture : {spec.layer_id}"
            )
        if verification.layerTreeRoot().findLayer(spec.layer_id) is not None:
            raise QGISProjectError(
                f"Couche privée visible après relecture : {spec.layer_id}"
            )
    drag_and_drop = api["Qgis"].AttributeFormLayout.DragAndDrop
    for key in ("desordres_point", "desordres_line", "desordres_polygon"):
        layer_id = next(spec.layer_id for spec in LAYER_SPECS if spec.key == key)
        if verification.mapLayer(layer_id).editFormConfig().layout() != drag_and_drop:
            raise QGISProjectError(
                f"Formulaire Drag-and-Drop absent après relecture : {layer_id}"
            )
        _verify_no_single_item_groups(api, verification.mapLayer(layer_id))
    child_id = next(
        spec.layer_id for spec in LAYER_SPECS
        if spec.key == "desordre_localisations"
    )
    child = verification.mapLayer(child_id)
    if child.editFormConfig().layout() != drag_and_drop:
        raise QGISProjectError(
            "Formulaire enfant Drag-and-Drop absent après relecture"
        )
    _verify_no_single_item_groups(api, child)
    for field_name in ("pr_debut", "pr_fin"):
        index = child.fields().indexFromName(field_name)
        if index < 0 or not child.editFormConfig().readOnly(index):
            raise QGISProjectError(
                f"PR modifiable après relecture : {field_name}"
            )
    for field_name in ("borne_debut_id", "borne_fin_id"):
        index = child.fields().indexFromName(field_name)
        setup = child.editorWidgetSetup(index) if index >= 0 else None
        if setup is None or setup.type() != "ValueRelation":
            raise QGISProjectError(
                f"Borne modifiable en texte libre après relecture : {field_name}"
            )
        if setup.config().get("Value") != "libelle_affichage":
            raise QGISProjectError(
                f"Libellé métier absent du widget de borne : {field_name}"
            )
    for field_name in ("position_debut_relative", "position_fin_relative"):
        index = child.fields().indexFromName(field_name)
        setup = child.editorWidgetSetup(index) if index >= 0 else None
        if setup is None or setup.type() != "ValueMap":
            raise QGISProjectError(
                f"Widget de position invalide après relecture : {field_name}"
            )
        if setup.config() != POSITION_VALUE_MAP:
            raise QGISProjectError(
                f"Vocabulaire Amont/Aval altéré après relecture : {field_name}"
            )
    point = verification.mapLayer("sirs_desordres_points")
    for spec in POINT_COORDINATE_FIELDS:
        index = point.fields().indexFromName(spec.name)
        if index < 0 or point.editFormConfig().readOnly(index):
            raise QGISProjectError(
                f"Coordonnée éditable absente après relecture : {spec.name}"
            )
    synchronization_index = point.fields().indexFromName(
        "synchronisation_formulaire"
    )
    if (
        synchronization_index < 0
        or not point.editFormConfig().readOnly(synchronization_index)
        or point.expressionField(synchronization_index)
        != repr(FORM_SYNCHRONIZATION_MESSAGE)
    ):
        raise QGISProjectError(
            "Consigne de synchronisation absente après relecture"
        )
    line = verification.mapLayer("sirs_desordres_lignes")
    for spec in LINE_COORDINATE_FIELDS:
        index = line.fields().indexFromName(spec.name)
        if index < 0 or not line.editFormConfig().readOnly(index):
            raise QGISProjectError(
                f"Coordonnée de ligne absente après relecture : {spec.name}"
            )


def _verify_written_project(api: dict[str, Any], output: Path) -> None:
    """Relit le QGZ puis détruit explicitement son projet et ses couches."""

    verification = api["QgsProject"]()
    error: Exception | None = None
    try:
        _inspect_written_project(api, verification, output)
    except Exception as exc:
        # Ne pas conserver une traceback contenant des wrappers SIP jusqu'à
        # l'arrêt éventuel de QgsApplication dans l'appelant.
        error = exc.with_traceback(None)
    finally:
        _clear_qgis_project(verification)
        verification = None
        gc.collect()
    if error is not None:
        raise error


def _verify_no_single_item_groups(api: dict[str, Any], layer: Any) -> None:
    """Refuse les groupes artificiels d'un champ ou d'une relation."""

    container_type = api["QgsAttributeEditorContainer"]

    def visit(parent: Any) -> None:
        for child in parent.children():
            if not isinstance(child, container_type):
                continue
            count = len(child.children())
            if count < 2:
                raise QGISProjectError(
                    f"Groupe de formulaire artificiel ({child.name()}) "
                    f"dans {layer.id()}"
                )
            visit(child)

    visit(layer.editFormConfig().invisibleRootContainer())


def generate_qgis_project(
    config: PostgreSQLConfig,
    output: Path = DEFAULT_QGIS_PROJECT_PATH,
    *,
    authcfg: str | None = None,
) -> QGISProjectResult:
    """Construit, écrit puis relit un projet QGZ à partir de PostgreSQL."""

    output = Path(output).expanduser().resolve()
    if output.suffix.casefold() != ".qgz":
        raise QGISProjectError("La sortie du projet QGIS doit porter l'extension .qgz")
    api = _load_pyqgis()
    connection = qgis_connection_from_config(config, authcfg=authcfg)

    owns_application = api["QgsApplication"].instance() is None
    application = None
    if owns_application:
        prefix = os.getenv("QGIS_PREFIX_PATH")
        if prefix:
            api["QgsApplication"].setPrefixPath(prefix, True)
        application = api["QgsApplication"]([], False)
        application.initQgis()

    project = None
    layers: dict[str, Any] | None = None
    groups: dict[tuple[str, ...], Any] | None = None
    generation_error: Exception | None = None
    try:
        project = api["QgsProject"]()
        project.setTitle("SIRS PostgreSQL — prototype repérage des désordres")
        project.setCrs(
            api["QgsCoordinateReferenceSystem"].fromEpsgId(TARGET_SRID)
        )
        with _temporary_pgpassword(_runtime_password(config)):
            layers = {
                spec.key: _create_layer(api, connection, spec)
                for spec in LAYER_SPECS
            }
            layers[OSM_LAYER_SPEC.key] = _create_osm_layer(api)
            if len({layer.id() for layer in layers.values()}) != len(layers):
                raise QGISProjectError("Les layer IDs QGIS ne sont pas uniques")

            groups = _create_groups(project)
            _register_layers(project, groups, layers)
            _create_relations(api, project, layers)
            _configure_lookup_layers(layers)
            _configure_localisation_form(
                api, layers["desordre_localisations"], layers
            )
            _configure_desordre_troncons_form(
                api, layers["desordre_troncons"], layers
            )
            localisation_relations = {
                spec.parent_layer_key: spec.relation_id
                for spec in RELATION_SPECS
                if spec.child_layer_key == "desordre_localisations"
            }
            troncon_relations = {
                spec.parent_layer_key: spec.relation_id
                for spec in RELATION_SPECS
                if spec.child_layer_key == "desordre_troncons"
            }
            for parent_key, relation_id in localisation_relations.items():
                coordinate_fields = (
                    POINT_COORDINATE_FIELDS if parent_key == "desordres_point"
                    else LINE_COORDINATE_FIELDS if parent_key == "desordres_line"
                    else ()
                )
                _configure_desordre_form(
                    api,
                    layers[parent_key],
                    relation_id,
                    troncon_relations[parent_key],
                    coordinate_fields=coordinate_fields,
                    coordinates_editable=(parent_key == "desordres_point"),
                )

            output.parent.mkdir(parents=True, exist_ok=True)
            if not project.write(str(output)):
                raise QGISProjectError(f"Écriture QGZ refusée : {output}")
            _verify_written_project(api, output)
    except Exception as exc:
        # Une traceback peut garder vivants project/layers et d'autres wrappers
        # SIP au-delà de exitQgis(). La décision d'erreur est conservée sans elle.
        generation_error = exc.with_traceback(None)
    finally:
        _clear_qgis_project(project, groups, layers)
        groups = None
        layers = None
        project = None
        gc.collect()
        if owns_application and application is not None:
            application.exitQgis()
            application = None
            gc.collect()

    if generation_error is not None:
        raise generation_error

    return QGISProjectResult(
        output=output,
        layer_ids=tuple(spec.layer_id for spec in ALL_LAYER_SPECS),
        relation_ids=tuple(spec.relation_id for spec in RELATION_SPECS),
        groups=tuple(path[-1] for path in GROUP_PATHS),
        connection=connection.safe_description,
    )
