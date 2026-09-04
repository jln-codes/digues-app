"""Generation du dataset synthetique public de demonstration.

Le generateur suppose une base PostgreSQL/PostGIS deja initialisee avec le
schema courant. Il ne lit aucune donnee metier existante pour construire les
geometries : le plan est porte par des constantes et PostGIS effectue seulement
les transformations et mesures.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal
from uuid import UUID, uuid5

from digues_app.target import PostgreSQLConfig
from digues_app.target.schema import EXPECTED_TABLES


DEMO_SEED = "digues-demo-v1"
DEMO_NAMESPACE = UUID("00e4b4e1-838f-5fbb-ae8d-e2ba816246dd")
WGS84_BBOX = (2.22636945, 50.33654743, 2.96139128, 50.68936846)


class DemoSeedError(RuntimeError):
    """Le dataset de demonstration ne peut pas etre genere ou valide."""


@dataclass(frozen=True)
class DemoSeedReport:
    seed: str
    counts: Mapping[str, int]
    geometry_counts: Mapping[str, int]
    system_lengths_m: Mapping[str, float]
    ranges: Mapping[str, tuple[float | None, float | None]]


@dataclass(frozen=True)
class DigueSpec:
    slug: str
    label: str


@dataclass(frozen=True)
class SystemeSpec:
    slug: str
    label: str
    origin_lon: float
    origin_lat: float
    digues: tuple[DigueSpec, ...]


@dataclass(frozen=True)
class TronconSpec:
    slug: str
    system_slug: str
    digue_slug: str
    label: str
    points_m: tuple[tuple[float, float], ...]


GeometryKind = Literal[
    "POINT_LIBRE",
    "POINT_PROJETE",
    "LINESTRING_LIBRE",
    "LINESTRING_PROJETE",
    "POLYGON_LIBRE",
]


@dataclass(frozen=True)
class DesordreSpec:
    slug: str
    system_slug: str
    troncon_slug: str
    kind: GeometryKind
    label: str
    type_id: str
    fraction: float
    lateral_m: float = 0.0
    length_m: float | None = None
    area_m2: float | None = None


REFERENCE_CATEGORIES = (
    ("demo:digues-demo-v1:categorie-surface", "Demo - surface"),
    ("demo:digues-demo-v1:categorie-structure", "Demo - structure"),
    ("demo:digues-demo-v1:categorie-hydraulique", "Demo - hydraulique"),
)

REFERENCE_TYPES = (
    (
        "demo:digues-demo-v1:type-erosion",
        "demo:digues-demo-v1:categorie-surface",
        "Demo - erosion superficielle",
    ),
    (
        "demo:digues-demo-v1:type-fissure",
        "demo:digues-demo-v1:categorie-structure",
        "Demo - fissure locale",
    ),
    (
        "demo:digues-demo-v1:type-affaissement",
        "demo:digues-demo-v1:categorie-structure",
        "Demo - affaissement ponctuel",
    ),
    (
        "demo:digues-demo-v1:type-suintement",
        "demo:digues-demo-v1:categorie-hydraulique",
        "Demo - suintement",
    ),
    (
        "demo:digues-demo-v1:type-zone-degradee",
        "demo:digues-demo-v1:categorie-surface",
        "Demo - zone degradee",
    ),
)

REFERENCE_URGENCES = (
    ("demo:digues-demo-v1:urgence-surveillance", "Demo - surveillance"),
    ("demo:digues-demo-v1:urgence-programmee", "Demo - intervention programmee"),
    ("demo:digues-demo-v1:urgence-rapide", "Demo - intervention rapide"),
)

SYSTEMES = (
    SystemeSpec(
        slug="carbonade",
        label="SE Carbonade",
        origin_lon=2.392,
        origin_lat=50.548,
        digues=(
            DigueSpec("carbonade-nord", "Digue Carbonade Nord"),
            DigueSpec("carbonade-sud", "Digue Carbonade Sud"),
        ),
    ),
    SystemeSpec(
        slug="welsh",
        label="SE Welsh",
        origin_lon=2.615,
        origin_lat=50.472,
        digues=(DigueSpec("welsh-principal", "Digue Welsh principale"),),
    ),
    SystemeSpec(
        slug="potjevleesch",
        label="SE Potjevleesch",
        origin_lon=2.803,
        origin_lat=50.607,
        digues=(DigueSpec("potjevleesch-est", "Digue Potjevleesch Est"),),
    ),
)

TRONCONS = (
    TronconSpec(
        "carbonade-t01",
        "carbonade",
        "carbonade-nord",
        "Troncon Carbonade 01",
        ((0, 0), (500, 80), (720, 20)),
    ),
    TronconSpec(
        "carbonade-t02",
        "carbonade",
        "carbonade-nord",
        "Troncon Carbonade 02",
        ((720, 20), (1250, -40), (1500, 70)),
    ),
    TronconSpec(
        "carbonade-t03",
        "carbonade",
        "carbonade-nord",
        "Troncon Carbonade 03",
        ((1500, 70), (2050, 20), (2300, -60)),
    ),
    TronconSpec(
        "carbonade-t04",
        "carbonade",
        "carbonade-sud",
        "Troncon Carbonade 04",
        ((120, -260), (680, -320), (940, -260)),
    ),
    TronconSpec(
        "carbonade-t05",
        "carbonade",
        "carbonade-sud",
        "Troncon Carbonade 05",
        ((940, -260), (1360, -190), (1670, -260)),
    ),
    TronconSpec(
        "welsh-t01",
        "welsh",
        "welsh-principal",
        "Troncon Welsh 01",
        ((0, 0), (430, 45), (560, 20)),
    ),
    TronconSpec(
        "welsh-t02",
        "welsh",
        "welsh-principal",
        "Troncon Welsh 02",
        ((560, 20), (900, -30), (1040, 35)),
    ),
    TronconSpec(
        "potjevleesch-t01",
        "potjevleesch",
        "potjevleesch-est",
        "Troncon Potjevleesch 01",
        ((0, 0), (260, 25), (510, -20)),
    ),
)

DESORDRES = (
    DesordreSpec(
        "desordre-001",
        "carbonade",
        "carbonade-t01",
        "POINT_LIBRE",
        "Demo point libre 001",
        "demo:digues-demo-v1:type-affaissement",
        0.20,
        2,
    ),
    DesordreSpec(
        "desordre-002",
        "carbonade",
        "carbonade-t02",
        "POINT_LIBRE",
        "Demo point libre 002",
        "demo:digues-demo-v1:type-suintement",
        0.42,
        -4,
    ),
    DesordreSpec(
        "desordre-003",
        "carbonade",
        "carbonade-t04",
        "POINT_LIBRE",
        "Demo point libre 003",
        "demo:digues-demo-v1:type-erosion",
        0.65,
        7,
    ),
    DesordreSpec(
        "desordre-004",
        "welsh",
        "welsh-t01",
        "POINT_LIBRE",
        "Demo point libre 004",
        "demo:digues-demo-v1:type-fissure",
        0.33,
        -11,
    ),
    DesordreSpec(
        "desordre-005",
        "potjevleesch",
        "potjevleesch-t01",
        "POINT_LIBRE",
        "Demo point libre 005",
        "demo:digues-demo-v1:type-suintement",
        0.72,
        16,
    ),
    DesordreSpec(
        "desordre-006",
        "carbonade",
        "carbonade-t03",
        "POINT_PROJETE",
        "Demo point projete 006",
        "demo:digues-demo-v1:type-erosion",
        0.18,
    ),
    DesordreSpec(
        "desordre-007",
        "carbonade",
        "carbonade-t05",
        "POINT_PROJETE",
        "Demo point projete 007",
        "demo:digues-demo-v1:type-affaissement",
        0.47,
    ),
    DesordreSpec(
        "desordre-008",
        "welsh",
        "welsh-t02",
        "POINT_PROJETE",
        "Demo point projete 008",
        "demo:digues-demo-v1:type-suintement",
        0.24,
    ),
    DesordreSpec(
        "desordre-009",
        "potjevleesch",
        "potjevleesch-t01",
        "POINT_PROJETE",
        "Demo point projete 009",
        "demo:digues-demo-v1:type-fissure",
        0.41,
    ),
    DesordreSpec(
        "desordre-010",
        "carbonade",
        "carbonade-t01",
        "POINT_PROJETE",
        "Demo point projete 010",
        "demo:digues-demo-v1:type-affaissement",
        0.77,
    ),
    DesordreSpec(
        "desordre-011",
        "carbonade",
        "carbonade-t02",
        "LINESTRING_LIBRE",
        "Demo ligne libre 011",
        "demo:digues-demo-v1:type-fissure",
        0.28,
        5,
        6,
    ),
    DesordreSpec(
        "desordre-012",
        "carbonade",
        "carbonade-t04",
        "LINESTRING_LIBRE",
        "Demo ligne libre 012",
        "demo:digues-demo-v1:type-erosion",
        0.52,
        -8,
        9,
    ),
    DesordreSpec(
        "desordre-013",
        "welsh",
        "welsh-t01",
        "LINESTRING_LIBRE",
        "Demo ligne libre 013",
        "demo:digues-demo-v1:type-suintement",
        0.61,
        12,
        14,
    ),
    DesordreSpec(
        "desordre-014",
        "potjevleesch",
        "potjevleesch-t01",
        "LINESTRING_LIBRE",
        "Demo ligne libre 014",
        "demo:digues-demo-v1:type-zone-degradee",
        0.18,
        -15,
        21,
    ),
    DesordreSpec(
        "desordre-015",
        "carbonade",
        "carbonade-t03",
        "LINESTRING_PROJETE",
        "Demo ligne projetee 015",
        "demo:digues-demo-v1:type-erosion",
        0.36,
        length_m=8,
    ),
    DesordreSpec(
        "desordre-016",
        "carbonade",
        "carbonade-t05",
        "LINESTRING_PROJETE",
        "Demo ligne projetee 016",
        "demo:digues-demo-v1:type-fissure",
        0.62,
        length_m=12,
    ),
    DesordreSpec(
        "desordre-017",
        "welsh",
        "welsh-t02",
        "LINESTRING_PROJETE",
        "Demo ligne projetee 017",
        "demo:digues-demo-v1:type-suintement",
        0.48,
        length_m=20,
    ),
    DesordreSpec(
        "desordre-018",
        "carbonade",
        "carbonade-t01",
        "LINESTRING_PROJETE",
        "Demo ligne projetee 018",
        "demo:digues-demo-v1:type-zone-degradee",
        0.55,
        length_m=28,
    ),
    DesordreSpec(
        "desordre-019",
        "carbonade",
        "carbonade-t02",
        "POLYGON_LIBRE",
        "Demo polygone libre 019",
        "demo:digues-demo-v1:type-zone-degradee",
        0.72,
        6,
        area_m2=3,
    ),
    DesordreSpec(
        "desordre-020",
        "welsh",
        "welsh-t01",
        "POLYGON_LIBRE",
        "Demo polygone libre 020",
        "demo:digues-demo-v1:type-zone-degradee",
        0.20,
        -10,
        area_m2=8,
    ),
    DesordreSpec(
        "desordre-021",
        "potjevleesch",
        "potjevleesch-t01",
        "POLYGON_LIBRE",
        "Demo polygone libre 021",
        "demo:digues-demo-v1:type-zone-degradee",
        0.55,
        14,
        area_m2=18,
    ),
)


def stable_uuid(kind: str, slug: str, *, seed: str = DEMO_SEED) -> UUID:
    return uuid5(DEMO_NAMESPACE, f"{seed}:{kind}:{slug}")


def _systeme_by_slug() -> dict[str, SystemeSpec]:
    return {systeme.slug: systeme for systeme in SYSTEMES}


def _all_ids() -> dict[str, tuple[UUID, ...]]:
    digues = tuple(
        stable_uuid("digue", digue.slug)
        for systeme in SYSTEMES
        for digue in systeme.digues
    )
    troncons = tuple(stable_uuid("troncon", troncon.slug) for troncon in TRONCONS)
    bornes = tuple(
        stable_uuid("borne", f"{troncon.slug}-{suffix}")
        for troncon in TRONCONS
        for suffix in ("debut", "fin")
    )
    return {
        "systemes": tuple(stable_uuid("systeme", item.slug) for item in SYSTEMES),
        "digues": digues,
        "troncons": troncons,
        "systemes_reperage": tuple(
            stable_uuid("systeme-reperage", troncon.slug) for troncon in TRONCONS
        ),
        "bornes_reperage": bornes,
        "link_systemes_reperage_bornes": tuple(
            stable_uuid("systeme-reperage-borne", f"{troncon.slug}-{suffix}")
            for troncon in TRONCONS
            for suffix in ("debut", "fin")
        ),
        "link_desordres_troncons": tuple(
            stable_uuid("link-desordre-troncon", item.slug) for item in DESORDRES
        ),
        "desordres": tuple(stable_uuid("desordre", item.slug) for item in DESORDRES),
        "desordre_localisations_reperage": tuple(
            stable_uuid("desordre-localisation", item.slug)
            for item in DESORDRES
            if item.kind in {
                "POINT_LIBRE",
                "POINT_PROJETE",
                "LINESTRING_LIBRE",
                "LINESTRING_PROJETE",
            }
        ),
        "observations": tuple(_observation_id(item, index) for item in DESORDRES for index in _observation_indexes(item)),
        "photos": tuple(
            _photo_id(item, obs_index, photo_index)
            for item in DESORDRES
            for obs_index in _observation_indexes(item)
            for photo_index in _photo_indexes(item, obs_index)
        ),
    }


def _observation_indexes(desordre: DesordreSpec) -> range:
    number = int(desordre.slug.rsplit("-", 1)[1])
    return range(1, 2 + (number % 2))


def _photo_indexes(desordre: DesordreSpec, observation_index: int) -> range:
    number = int(desordre.slug.rsplit("-", 1)[1])
    return range(1, 2 + ((number + observation_index) % 2))


def _observation_id(desordre: DesordreSpec, index: int) -> UUID:
    return stable_uuid("observation", f"{desordre.slug}-obs-{index:03d}")


def _photo_id(desordre: DesordreSpec, observation_index: int, photo_index: int) -> UUID:
    return stable_uuid(
        "photo",
        f"{desordre.slug}-obs-{observation_index:03d}-photo-{photo_index:02d}",
    )


def _delete_any(
    cursor: Any,
    table: str,
    ids: Sequence[UUID] | Sequence[str],
    *,
    id_type: Literal["uuid", "text"] = "uuid",
) -> None:
    if ids:
        array_type = "uuid[]" if id_type == "uuid" else "text[]"
        cursor.execute(
            # Table names are internal constants selected by the reset order.
            f"DELETE FROM public.{table} WHERE id = ANY(%s::{array_type})",  # noqa: S608
            (list(ids),),
        )


def reset_demo_dataset(cursor: Any) -> None:
    """Supprime uniquement les lignes portant les identifiants deterministes."""

    ids = _all_ids()
    _delete_any(cursor, "photos", ids["photos"])
    _delete_any(cursor, "observations", ids["observations"])
    cursor.execute(
        "DELETE FROM public.desordre_localisations_reperage "
        "WHERE desordre_id = ANY(%s::uuid[]) OR id = ANY(%s::uuid[])",
        (
            list(ids["desordres"]),
            list(ids["desordre_localisations_reperage"]),
        ),
    )
    _delete_any(cursor, "link_desordres_troncons", ids["link_desordres_troncons"])
    _delete_any(cursor, "desordres", ids["desordres"])
    cursor.execute(
        "UPDATE public.troncons SET systeme_reperage_defaut_id = NULL "
        "WHERE id = ANY(%s::uuid[])",
        (list(ids["troncons"]),),
    )
    _delete_any(
        cursor,
        "link_systemes_reperage_bornes",
        ids["link_systemes_reperage_bornes"],
    )
    cursor.execute(
        "DELETE FROM public.link_troncons_bornes "
        "WHERE troncon_id = ANY(%s::uuid[]) AND borne_id = ANY(%s::uuid[])",
        (list(ids["troncons"]), list(ids["bornes_reperage"])),
    )
    _delete_any(cursor, "bornes_reperage", ids["bornes_reperage"])
    _delete_any(cursor, "systemes_reperage", ids["systemes_reperage"])
    _delete_any(cursor, "troncons", ids["troncons"])
    _delete_any(cursor, "digues", ids["digues"])
    _delete_any(cursor, "systemes", ids["systemes"])
    _delete_any(
        cursor,
        "ref_types_desordre",
        [row[0] for row in REFERENCE_TYPES],
        id_type="text",
    )
    _delete_any(
        cursor,
        "ref_categories_desordre",
        [row[0] for row in REFERENCE_CATEGORIES],
        id_type="text",
    )
    _delete_any(
        cursor,
        "ref_urgences",
        [row[0] for row in REFERENCE_URGENCES],
        id_type="text",
    )


def _empty_report(cursor: Any) -> DemoSeedReport:
    ids = _all_ids()
    counts = {
        "ref_categories_desordre": _count_rows(
            cursor,
            "ref_categories_desordre",
            [row[0] for row in REFERENCE_CATEGORIES],
            id_type="text",
        ),
        "ref_types_desordre": _count_rows(
            cursor,
            "ref_types_desordre",
            [row[0] for row in REFERENCE_TYPES],
            id_type="text",
        ),
        "ref_urgences": _count_rows(
            cursor,
            "ref_urgences",
            [row[0] for row in REFERENCE_URGENCES],
            id_type="text",
        ),
        "systemes": _count_rows(cursor, "systemes", ids["systemes"]),
        "digues": _count_rows(cursor, "digues", ids["digues"]),
        "troncons": _count_rows(cursor, "troncons", ids["troncons"]),
        "systemes_reperage": _count_rows(
            cursor, "systemes_reperage", ids["systemes_reperage"]
        ),
        "bornes_reperage": _count_rows(cursor, "bornes_reperage", ids["bornes_reperage"]),
        "link_systemes_reperage_bornes": _count_rows(
            cursor,
            "link_systemes_reperage_bornes",
            ids["link_systemes_reperage_bornes"],
        ),
        "link_desordres_troncons": _count_rows(
            cursor, "link_desordres_troncons", ids["link_desordres_troncons"]
        ),
        "desordres": _count_rows(cursor, "desordres", ids["desordres"]),
        "desordre_localisations_reperage": _count_rows(
            cursor,
            "desordre_localisations_reperage",
            ids["desordre_localisations_reperage"],
        ),
        "observations": _count_rows(cursor, "observations", ids["observations"]),
        "photos": _count_rows(cursor, "photos", ids["photos"]),
    }
    cursor.execute(
        "SELECT COUNT(*) FROM public.link_troncons_bornes "
        "WHERE troncon_id = ANY(%s::uuid[]) AND borne_id = ANY(%s::uuid[])",
        (list(ids["troncons"]), list(ids["bornes_reperage"])),
    )
    counts["link_troncons_bornes"] = int(cursor.fetchone()[0])
    remaining = {table: count for table, count in counts.items() if count}
    if remaining:
        raise DemoSeedError(f"Reset demo incomplet : {remaining}")
    return DemoSeedReport(
        seed=DEMO_SEED,
        counts=counts,
        geometry_counts={},
        system_lengths_m={},
        ranges={},
    )


def _ensure_schema_compatible(cursor: Any) -> None:
    cursor.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = ANY(%s)",
        (list(EXPECTED_TABLES),),
    )
    present = {row[0] for row in cursor.fetchall()}
    required_tables = {
        "systemes",
        "digues",
        "troncons",
        "systemes_reperage",
        "bornes_reperage",
        "link_troncons_bornes",
        "link_systemes_reperage_bornes",
        "ref_categories_desordre",
        "ref_types_desordre",
        "ref_urgences",
        "desordres",
        "link_desordres_troncons",
        "observations",
        "photos",
        "desordre_localisations_reperage",
    }
    missing = sorted(required_tables - present)
    if missing:
        raise DemoSeedError("Schema SIRS incomplet : " + ", ".join(missing))

    cursor.execute(
        "SELECT f_table_name, type, srid FROM public.geometry_columns "
        "WHERE f_table_schema = 'public' "
        "AND f_table_name = ANY(%s) AND f_geometry_column = 'geometry'",
        (["troncons", "bornes_reperage", "desordres"],),
    )
    geometries = {row[0]: (str(row[1]).upper(), int(row[2])) for row in cursor.fetchall()}
    expected = {
        "troncons": ("LINESTRING", 3950),
        "bornes_reperage": ("POINT", 3950),
        "desordres": ("GEOMETRY", 3950),
    }
    for table, expected_geometry in expected.items():
        if geometries.get(table) != expected_geometry:
            raise DemoSeedError(
                f"Colonne geometrie incompatible pour {table}: "
                f"{geometries.get(table)!r}, attendu {expected_geometry!r}"
            )

    cursor.execute(
        "SELECT "
        "to_regprocedure('public.borne_offset_vers_xy(uuid,uuid,uuid,double precision)'), "
        "to_regprocedure('public.xy_vers_reperage(uuid,uuid,geometry)'), "
        "to_regprocedure('public.synchroniser_desordre_reperage(uuid,uuid)')"
    )
    if any(value is None for value in cursor.fetchone()):
        raise DemoSeedError("Fonctions de reperage SIRS absentes ou incompatibles.")


def _insert_references(cursor: Any) -> None:
    cursor.executemany(
        "INSERT INTO public.ref_categories_desordre (id, libelle, valid) "
        "VALUES (%s, %s, true)",
        REFERENCE_CATEGORIES,
    )
    cursor.executemany(
        "INSERT INTO public.ref_types_desordre (id, categorie_id, libelle, valid) "
        "VALUES (%s, %s, %s, true)",
        REFERENCE_TYPES,
    )
    cursor.executemany(
        "INSERT INTO public.ref_urgences (id, libelle, valid) VALUES (%s, %s, true)",
        REFERENCE_URGENCES,
    )


def _line_from_offsets_sql(point_count: int) -> str:
    points = ", ".join("ST_Translate(origin.geometry, %s, %s)" for _ in range(point_count))
    return f"ST_MakeLine(ARRAY[{points}])::geometry(LineString, 3950)"


def _insert_hierarchy(cursor: Any) -> None:
    systemes_by_slug = _systeme_by_slug()
    cursor.executemany(
        "INSERT INTO public.systemes (id, libelle, valid) VALUES (%s, %s, true)",
        [(stable_uuid("systeme", item.slug), item.label) for item in SYSTEMES],
    )
    cursor.executemany(
        "INSERT INTO public.digues (id, systeme_endiguement_id, libelle, valid) "
        "VALUES (%s, %s, %s, true)",
        [
            (
                stable_uuid("digue", digue.slug),
                stable_uuid("systeme", systeme.slug),
                digue.label,
            )
            for systeme in SYSTEMES
            for digue in systeme.digues
        ],
    )
    for troncon in TRONCONS:
        systeme = systemes_by_slug[troncon.system_slug]
        cursor.execute(
            "WITH origin AS ("
            "SELECT ST_Transform(ST_SetSRID(ST_Point(%s, %s), 4326), 3950) "
            "AS geometry"
            ") "
            "INSERT INTO public.troncons (id, digue_id, libelle, geometry, valid) "
            f"SELECT %s, %s, %s, {_line_from_offsets_sql(len(troncon.points_m))}, true "
            "FROM origin",
            (
                systeme.origin_lon,
                systeme.origin_lat,
                stable_uuid("troncon", troncon.slug),
                stable_uuid("digue", troncon.digue_slug),
                troncon.label,
                *(value for point in troncon.points_m for value in point),
            ),
        )


def _insert_reperage(cursor: Any) -> None:
    for troncon in TRONCONS:
        troncon_id = stable_uuid("troncon", troncon.slug)
        systeme_reperage_id = stable_uuid("systeme-reperage", troncon.slug)
        borne_debut_id = stable_uuid("borne", f"{troncon.slug}-debut")
        borne_fin_id = stable_uuid("borne", f"{troncon.slug}-fin")
        cursor.execute(
            "INSERT INTO public.systemes_reperage "
            "(id, troncon_id, libelle, commentaire, valid) "
            "VALUES (%s, %s, %s, %s, true)",
            (
                systeme_reperage_id,
                troncon_id,
                f"Reperage demo {troncon.label}",
                f"{DEMO_SEED} - bornes synthetiques",
            ),
        )
        cursor.execute(
            "INSERT INTO public.bornes_reperage "
            "(id, libelle, commentaire, geometry, fictive, valid) "
            "SELECT %s, %s, %s, ST_StartPoint(t.geometry)::geometry(Point, 3950), "
            "true, true FROM public.troncons AS t WHERE t.id = %s",
            (
                borne_debut_id,
                f"{troncon.label} debut",
                DEMO_SEED,
                troncon_id,
            ),
        )
        cursor.execute(
            "INSERT INTO public.bornes_reperage "
            "(id, libelle, commentaire, geometry, fictive, valid) "
            "SELECT %s, %s, %s, ST_EndPoint(t.geometry)::geometry(Point, 3950), "
            "true, true FROM public.troncons AS t WHERE t.id = %s",
            (borne_fin_id, f"{troncon.label} fin", DEMO_SEED, troncon_id),
        )
        cursor.executemany(
            "INSERT INTO public.link_troncons_bornes (troncon_id, borne_id) "
            "VALUES (%s, %s)",
            ((troncon_id, borne_debut_id), (troncon_id, borne_fin_id)),
        )
        cursor.execute(
            "INSERT INTO public.link_systemes_reperage_bornes "
            "(id, systeme_reperage_id, borne_id, valeur_pr, valid) "
            "VALUES (%s, %s, %s, 0, true)",
            (
                stable_uuid("systeme-reperage-borne", f"{troncon.slug}-debut"),
                systeme_reperage_id,
                borne_debut_id,
            ),
        )
        cursor.execute(
            "INSERT INTO public.link_systemes_reperage_bornes "
            "(id, systeme_reperage_id, borne_id, valeur_pr, valid) "
            "SELECT %s, %s, %s, round(ST_Length(t.geometry)::numeric, 3), true "
            "FROM public.troncons AS t WHERE t.id = %s",
            (
                stable_uuid("systeme-reperage-borne", f"{troncon.slug}-fin"),
                systeme_reperage_id,
                borne_fin_id,
                troncon_id,
            ),
        )
        cursor.execute(
            "UPDATE public.troncons SET systeme_reperage_defaut_id = %s "
            "WHERE id = %s",
            (systeme_reperage_id, troncon_id),
        )


def _projected_point_sql() -> str:
    return (
        "ST_LineInterpolatePoint(t.geometry, %s)"
        "::geometry(Point, 3950)"
    )


def _free_point_sql() -> str:
    return (
        "ST_Translate(ST_LineInterpolatePoint(t.geometry, %s), 0, %s)"
        "::geometry(Point, 3950)"
    )


def _projected_line_sql() -> str:
    return (
        "ST_LineSubstring("
        "t.geometry, %s, least(0.999999, %s + (%s / ST_Length(t.geometry)))"
        ")::geometry(LineString, 3950)"
    )


def _free_line_sql() -> str:
    return (
        "ST_Translate("
        "ST_LineSubstring("
        "t.geometry, %s, least(0.999999, %s + (%s / ST_Length(t.geometry)))"
        "), 0, %s)::geometry(LineString, 3950)"
    )


def _polygon_sql() -> str:
    return (
        "ST_MakeEnvelope("
        "ST_X(center.geometry) - %s / 2, ST_Y(center.geometry) - %s / 2, "
        "ST_X(center.geometry) + %s / 2, ST_Y(center.geometry) + %s / 2, "
        "3950)::geometry(Polygon, 3950)"
    )


def _insert_desordre_geometry(cursor: Any, desordre: DesordreSpec) -> None:
    desordre_id = stable_uuid("desordre", desordre.slug)
    troncon_id = stable_uuid("troncon", desordre.troncon_slug)
    if desordre.kind == "POINT_PROJETE":
        geometry_sql = _projected_point_sql()
        parameters: tuple[Any, ...] = (desordre.fraction,)
    elif desordre.kind == "POINT_LIBRE":
        geometry_sql = _free_point_sql()
        parameters = (desordre.fraction, desordre.lateral_m)
    elif desordre.kind == "LINESTRING_PROJETE":
        geometry_sql = _projected_line_sql()
        parameters = (desordre.fraction, desordre.fraction, desordre.length_m)
    elif desordre.kind == "LINESTRING_LIBRE":
        geometry_sql = _free_line_sql()
        parameters = (
            desordre.fraction,
            desordre.fraction,
            desordre.length_m,
            desordre.lateral_m,
        )
    elif desordre.kind == "POLYGON_LIBRE":
        if desordre.area_m2 is None:
            raise DemoSeedError(f"Aire absente pour {desordre.slug}")
        width = max(1.5, round(desordre.area_m2 ** 0.5, 6))
        height = desordre.area_m2 / width
        geometry_sql = (
            "WITH center AS ("
            "SELECT ST_Translate(ST_LineInterpolatePoint(t.geometry, %s), 0, %s) "
            "AS geometry FROM public.troncons AS t WHERE t.id = %s"
            ") "
            "INSERT INTO public.desordres "
            "(id, type_desordre_id, designation, commentaire, date_debut, date_fin, "
            "geometry, valid) "
            f"SELECT %s, %s, %s, %s, %s, NULL, {_polygon_sql()}, true FROM center"
        )
        cursor.execute(
            geometry_sql,
            (
                desordre.fraction,
                desordre.lateral_m,
                troncon_id,
                desordre_id,
                desordre.type_id,
                desordre.label,
                f"{DEMO_SEED} {desordre.kind}",
                _start_date_for_desordre(desordre),
                width,
                height,
                width,
                height,
            ),
        )
        return
    else:
        raise DemoSeedError(f"Type de geometrie demo inconnu : {desordre.kind}")

    cursor.execute(
        "INSERT INTO public.desordres "
        "(id, type_desordre_id, designation, commentaire, date_debut, date_fin, "
        "geometry, valid) "
        f"SELECT %s, %s, %s, %s, %s, NULL, {geometry_sql}, true "
        "FROM public.troncons AS t WHERE t.id = %s",
        (
            desordre_id,
            desordre.type_id,
            desordre.label,
            f"{DEMO_SEED} {desordre.kind}",
            _start_date_for_desordre(desordre),
            *parameters,
            troncon_id,
        ),
    )


def _start_date_for_desordre(desordre: DesordreSpec) -> date:
    number = int(desordre.slug.rsplit("-", 1)[1])
    return date(2026, 1, 10) + timedelta(days=number * 3)


def _insert_desordres(cursor: Any) -> None:
    for desordre in DESORDRES:
        _insert_desordre_geometry(cursor, desordre)
        cursor.execute(
            "INSERT INTO public.link_desordres_troncons "
            "(id, desordre_id, troncon_id) VALUES (%s, %s, %s)",
            (
                stable_uuid("link-desordre-troncon", desordre.slug),
                stable_uuid("desordre", desordre.slug),
                stable_uuid("troncon", desordre.troncon_slug),
            ),
        )
        if desordre.kind in ("POINT_PROJETE", "LINESTRING_PROJETE"):
            _apply_projected_reperage(cursor, desordre)
        elif desordre.kind in ("POINT_LIBRE", "LINESTRING_LIBRE"):
            cursor.execute(
                "UPDATE public.desordre_localisations_reperage SET id = %s "
                "WHERE desordre_id = %s",
                (
                    stable_uuid("desordre-localisation", desordre.slug),
                    stable_uuid("desordre", desordre.slug),
                ),
            )


def _apply_projected_reperage(cursor: Any, desordre: DesordreSpec) -> None:
    troncon_id = stable_uuid("troncon", desordre.troncon_slug)
    systeme_reperage_id = stable_uuid("systeme-reperage", desordre.troncon_slug)
    borne_debut_id = stable_uuid("borne", f"{desordre.troncon_slug}-debut")
    desordre_id = stable_uuid("desordre", desordre.slug)
    cursor.execute(
        "SELECT ST_Length(geometry) FROM public.troncons WHERE id = %s",
        (troncon_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise DemoSeedError(f"Troncon absent pour le reperage : {desordre.troncon_slug}")
    troncon_length = float(row[0])
    start_distance = max(0.0, desordre.fraction * troncon_length)
    end_distance = None
    if desordre.kind == "LINESTRING_PROJETE":
        end_distance = min(troncon_length, start_distance + float(desordre.length_m or 0))
    cursor.execute(
        "UPDATE public.desordre_localisations_reperage SET "
        "id = %s, troncon_id = %s, systeme_reperage_id = %s, "
        "borne_debut_id = %s, distance_debut_m = %s, "
        "position_debut_relative = 'APRES_BORNE', "
        "borne_fin_id = %s, distance_fin_m = %s, position_fin_relative = %s, "
        "valid = true "
        "WHERE desordre_id = %s",
        (
            stable_uuid("desordre-localisation", desordre.slug),
            troncon_id,
            systeme_reperage_id,
            borne_debut_id,
            start_distance,
            borne_debut_id if end_distance is not None else None,
            end_distance,
            "APRES_BORNE" if end_distance is not None else None,
            desordre_id,
        ),
    )


def _insert_observations_and_photos(cursor: Any) -> None:
    urgency_ids = [row[0] for row in REFERENCE_URGENCES]
    evolutions = (
        "Constat demo initial",
        "Evolution demo stable",
        "Controle demo programme",
    )
    for desordre in DESORDRES:
        desordre_number = int(desordre.slug.rsplit("-", 1)[1])
        for observation_index in _observation_indexes(desordre):
            observation_id = _observation_id(desordre, observation_index)
            observation_date = date(2026, 4, 1) + timedelta(
                days=desordre_number * 2 + observation_index * 11
            )
            cursor.execute(
                "INSERT INTO public.observations "
                "(id, desordre_id, urgence_id, designation, date, evolution, valid) "
                "VALUES (%s, %s, %s, %s, %s, %s, true)",
                (
                    observation_id,
                    stable_uuid("desordre", desordre.slug),
                    urgency_ids[(desordre_number + observation_index) % len(urgency_ids)],
                    f"Observation demo {desordre_number:03d}-{observation_index:03d}",
                    observation_date,
                    evolutions[(desordre_number + observation_index) % len(evolutions)],
                ),
            )
            for photo_index in _photo_indexes(desordre, observation_index):
                cursor.execute(
                    "INSERT INTO public.photos "
                    "(id, observation_id, chemin_source, date, designation, valid) "
                    "VALUES (%s, %s, %s, %s, %s, true)",
                    (
                        _photo_id(desordre, observation_index, photo_index),
                        observation_id,
                        (
                            f"demo/photos/{desordre.system_slug}/{desordre.slug}/"
                            f"obs-{observation_index:03d}/photo-{photo_index:02d}.jpg"
                        ),
                        observation_date + timedelta(days=photo_index - 1),
                        f"Photo demo {desordre_number:03d}-{observation_index:03d}-{photo_index:02d}",
                    ),
                )


def _insert_demo_dataset(cursor: Any) -> None:
    _insert_references(cursor)
    _insert_hierarchy(cursor)
    _insert_reperage(cursor)
    _insert_desordres(cursor)
    _insert_observations_and_photos(cursor)


def seed_demo_cursor(
    cursor: Any,
    *,
    reset: bool = True,
    reset_only: bool = False,
) -> DemoSeedReport:
    _ensure_schema_compatible(cursor)
    if reset:
        reset_demo_dataset(cursor)
    if reset_only:
        return _empty_report(cursor)
    _insert_demo_dataset(cursor)
    return validate_demo_dataset(cursor)


def _expected_counts() -> dict[str, int]:
    counts = {
        "ref_categories_desordre": len(REFERENCE_CATEGORIES),
        "ref_types_desordre": len(REFERENCE_TYPES),
        "ref_urgences": len(REFERENCE_URGENCES),
        "systemes": len(SYSTEMES),
        "digues": sum(len(systeme.digues) for systeme in SYSTEMES),
        "troncons": len(TRONCONS),
        "systemes_reperage": len(TRONCONS),
        "bornes_reperage": len(TRONCONS) * 2,
        "link_troncons_bornes": len(TRONCONS) * 2,
        "link_systemes_reperage_bornes": len(TRONCONS) * 2,
        "desordres": len(DESORDRES),
        "link_desordres_troncons": len(DESORDRES),
        "desordre_localisations_reperage": sum(
            item.kind
            in {"POINT_LIBRE", "POINT_PROJETE", "LINESTRING_LIBRE", "LINESTRING_PROJETE"}
            for item in DESORDRES
        ),
        "observations": sum(len(_observation_indexes(item)) for item in DESORDRES),
        "photos": sum(
            len(_photo_indexes(item, obs_index))
            for item in DESORDRES
            for obs_index in _observation_indexes(item)
        ),
    }
    return counts


def _count_rows(
    cursor: Any,
    table: str,
    ids: Sequence[UUID] | Sequence[str],
    *,
    id_type: Literal["uuid", "text"] = "uuid",
) -> int:
    array_type = "uuid[]" if id_type == "uuid" else "text[]"
    cursor.execute(
        # Table names are internal constants selected by the validator.
        f"SELECT COUNT(*) FROM public.{table} WHERE id = ANY(%s::{array_type})",  # noqa: S608
        (list(ids),),
    )
    return int(cursor.fetchone()[0])


def _range(cursor: Any, query: str, params: Sequence[Any]) -> tuple[float | None, float | None]:
    cursor.execute(query, params)
    row = cursor.fetchone()
    return (
        None if row[0] is None else float(row[0]),
        None if row[1] is None else float(row[1]),
    )


def validate_demo_dataset(cursor: Any) -> DemoSeedReport:
    """Valide le dataset insere et retourne les mesures utiles au reporting."""

    ids = _all_ids()
    expected_counts = _expected_counts()
    actual_counts = {
        "ref_categories_desordre": _count_rows(
            cursor,
            "ref_categories_desordre",
            [row[0] for row in REFERENCE_CATEGORIES],
            id_type="text",
        ),
        "ref_types_desordre": _count_rows(
            cursor,
            "ref_types_desordre",
            [row[0] for row in REFERENCE_TYPES],
            id_type="text",
        ),
        "ref_urgences": _count_rows(
            cursor,
            "ref_urgences",
            [row[0] for row in REFERENCE_URGENCES],
            id_type="text",
        ),
        "systemes": _count_rows(cursor, "systemes", ids["systemes"]),
        "digues": _count_rows(cursor, "digues", ids["digues"]),
        "troncons": _count_rows(cursor, "troncons", ids["troncons"]),
        "systemes_reperage": _count_rows(
            cursor, "systemes_reperage", ids["systemes_reperage"]
        ),
        "bornes_reperage": _count_rows(cursor, "bornes_reperage", ids["bornes_reperage"]),
        "link_systemes_reperage_bornes": _count_rows(
            cursor,
            "link_systemes_reperage_bornes",
            ids["link_systemes_reperage_bornes"],
        ),
        "link_desordres_troncons": _count_rows(
            cursor, "link_desordres_troncons", ids["link_desordres_troncons"]
        ),
        "desordres": _count_rows(cursor, "desordres", ids["desordres"]),
        "desordre_localisations_reperage": _count_rows(
            cursor,
            "desordre_localisations_reperage",
            ids["desordre_localisations_reperage"],
        ),
        "observations": _count_rows(cursor, "observations", ids["observations"]),
        "photos": _count_rows(cursor, "photos", ids["photos"]),
    }
    cursor.execute(
        "SELECT COUNT(*) FROM public.link_troncons_bornes "
        "WHERE troncon_id = ANY(%s::uuid[]) AND borne_id = ANY(%s::uuid[])",
        (list(ids["troncons"]), list(ids["bornes_reperage"])),
    )
    actual_counts["link_troncons_bornes"] = int(cursor.fetchone()[0])
    count_errors = [
        f"{table}: attendu {expected_counts[table]}, obtenu {actual_counts[table]}"
        for table in sorted(expected_counts)
        if expected_counts[table] != actual_counts[table]
    ]
    if count_errors:
        raise DemoSeedError("Comptes demo incoherents : " + "; ".join(count_errors))

    _assert_zero(
        cursor,
        "hierarchie demo incoherente",
        """
        SELECT COUNT(*)
        FROM public.troncons AS t
        JOIN public.digues AS d ON d.id = t.digue_id
        JOIN public.systemes AS s ON s.id = d.systeme_endiguement_id
        WHERE t.id = ANY(%s::uuid[]) AND s.id <> ALL(%s::uuid[])
        """,
        (list(ids["troncons"]), list(ids["systemes"])),
    )
    _assert_zero(
        cursor,
        "geometries demo hors bbox WGS84",
        """
        WITH bbox AS (
            SELECT ST_MakeEnvelope(%s, %s, %s, %s, 4326) AS geometry
        ), demo_geometries AS (
            SELECT ST_Transform(geometry, 4326) AS geometry
            FROM public.troncons WHERE id = ANY(%s::uuid[])
            UNION ALL
            SELECT ST_Transform(geometry, 4326)
            FROM public.bornes_reperage WHERE id = ANY(%s::uuid[])
            UNION ALL
            SELECT ST_Transform(geometry, 4326)
            FROM public.desordres WHERE id = ANY(%s::uuid[])
        )
        SELECT COUNT(*)
        FROM demo_geometries, bbox
        WHERE NOT ST_Covers(bbox.geometry, demo_geometries.geometry)
        """,
        (*WGS84_BBOX, list(ids["troncons"]), list(ids["bornes_reperage"]), list(ids["desordres"])),
    )
    _assert_zero(
        cursor,
        "SRID demo invalide",
        """
        SELECT COUNT(*) FROM (
            SELECT ST_SRID(geometry) AS srid FROM public.troncons WHERE id = ANY(%s::uuid[])
            UNION ALL
            SELECT ST_SRID(geometry) FROM public.bornes_reperage WHERE id = ANY(%s::uuid[])
            UNION ALL
            SELECT ST_SRID(geometry) FROM public.desordres WHERE id = ANY(%s::uuid[])
        ) AS srids WHERE srid <> 3950
        """,
        (list(ids["troncons"]), list(ids["bornes_reperage"]), list(ids["desordres"])),
    )
    _assert_zero(
        cursor,
        "types geometriques demo invalides",
        """
        SELECT COUNT(*) FROM public.desordres
        WHERE id = ANY(%s::uuid[])
          AND GeometryType(geometry) NOT IN ('POINT', 'LINESTRING', 'POLYGON')
        """,
        (list(ids["desordres"]),),
    )

    system_lengths = _system_lengths(cursor)
    if not 3000 <= system_lengths["SE Carbonade"] <= 4200:
        raise DemoSeedError(f"Longueur Carbonade inattendue : {system_lengths['SE Carbonade']:.2f} m")
    if not 900 <= system_lengths["SE Welsh"] <= 1200:
        raise DemoSeedError(f"Longueur Welsh inattendue : {system_lengths['SE Welsh']:.2f} m")
    if not 450 <= system_lengths["SE Potjevleesch"] <= 600:
        raise DemoSeedError(
            f"Longueur Potjevleesch inattendue : {system_lengths['SE Potjevleesch']:.2f} m"
        )

    _validate_desordre_geometry_rules(cursor)
    _validate_observations_and_photos(cursor)
    _validate_reperage(cursor)

    cursor.execute(
        "SELECT GeometryType(geometry), COUNT(*) FROM public.desordres "
        "WHERE id = ANY(%s::uuid[]) GROUP BY GeometryType(geometry)",
        (list(ids["desordres"]),),
    )
    geometry_counts = {str(kind): int(count) for kind, count in cursor.fetchall()}

    ranges = {
        "point_libre_distance_m": _kind_distance_range(cursor, "POINT_LIBRE"),
        "point_projete_distance_m": _kind_distance_range(cursor, "POINT_PROJETE"),
        "line_libre_distance_m": _kind_distance_range(cursor, "LINESTRING_LIBRE"),
        "line_libre_length_m": _kind_length_range(cursor, "LINESTRING_LIBRE"),
        "line_projete_distance_m": _kind_distance_range(cursor, "LINESTRING_PROJETE"),
        "line_projete_length_m": _kind_length_range(cursor, "LINESTRING_PROJETE"),
        "polygon_distance_m": _kind_distance_range(cursor, "POLYGON_LIBRE"),
        "polygon_area_m2": _kind_area_range(cursor, "POLYGON_LIBRE"),
    }

    return DemoSeedReport(
        seed=DEMO_SEED,
        counts=actual_counts,
        geometry_counts=geometry_counts,
        system_lengths_m=system_lengths,
        ranges=ranges,
    )


def _assert_zero(
    cursor: Any,
    label: str,
    query: str,
    params: Sequence[Any],
) -> None:
    cursor.execute(query, params)
    violations = int(cursor.fetchone()[0])
    if violations:
        raise DemoSeedError(f"{label}: {violations} violation(s)")


def _system_lengths(cursor: Any) -> dict[str, float]:
    cursor.execute(
        """
        SELECT s.libelle, SUM(ST_Length(t.geometry)) AS longueur_m
        FROM public.systemes AS s
        JOIN public.digues AS d ON d.systeme_endiguement_id = s.id
        JOIN public.troncons AS t ON t.digue_id = d.id
        WHERE s.id = ANY(%s::uuid[])
        GROUP BY s.id, s.libelle
        """,
        (list(_all_ids()["systemes"]),),
    )
    return {str(label): float(length) for label, length in cursor.fetchall()}


def _kind_ids(kind: GeometryKind) -> tuple[UUID, ...]:
    return tuple(stable_uuid("desordre", item.slug) for item in DESORDRES if item.kind == kind)


def _kind_distance_range(cursor: Any, kind: GeometryKind) -> tuple[float | None, float | None]:
    return _range(
        cursor,
        """
        SELECT min(ST_Distance(d.geometry, t.geometry)),
               max(ST_Distance(d.geometry, t.geometry))
        FROM public.desordres AS d
        JOIN public.link_desordres_troncons AS l ON l.desordre_id = d.id
        JOIN public.troncons AS t ON t.id = l.troncon_id
        WHERE d.id = ANY(%s::uuid[])
        """,
        (list(_kind_ids(kind)),),
    )


def _kind_length_range(cursor: Any, kind: GeometryKind) -> tuple[float | None, float | None]:
    return _range(
        cursor,
        "SELECT min(ST_Length(geometry)), max(ST_Length(geometry)) "
        "FROM public.desordres WHERE id = ANY(%s::uuid[])",
        (list(_kind_ids(kind)),),
    )


def _kind_area_range(cursor: Any, kind: GeometryKind) -> tuple[float | None, float | None]:
    return _range(
        cursor,
        "SELECT min(ST_Area(geometry)), max(ST_Area(geometry)) "
        "FROM public.desordres WHERE id = ANY(%s::uuid[])",
        (list(_kind_ids(kind)),),
    )


def _validate_desordre_geometry_rules(cursor: Any) -> None:
    _assert_zero(
        cursor,
        "points projetes non confondus au troncon",
        """
        SELECT COUNT(*)
        FROM public.desordres AS d
        JOIN public.link_desordres_troncons AS l ON l.desordre_id = d.id
        JOIN public.troncons AS t ON t.id = l.troncon_id
        WHERE d.id = ANY(%s::uuid[]) AND ST_Distance(d.geometry, t.geometry) > 1e-8
        """,
        (list(_kind_ids("POINT_PROJETE")),),
    )
    _assert_zero(
        cursor,
        "points libres hors plage",
        """
        SELECT COUNT(*)
        FROM public.desordres AS d
        JOIN public.link_desordres_troncons AS l ON l.desordre_id = d.id
        JOIN public.troncons AS t ON t.id = l.troncon_id
        WHERE d.id = ANY(%s::uuid[])
          AND (ST_Distance(d.geometry, t.geometry) <= 1e-8
               OR ST_Distance(d.geometry, t.geometry) > 20)
        """,
        (list(_kind_ids("POINT_LIBRE")),),
    )
    _assert_zero(
        cursor,
        "lignes projetees hors plage ou non confondues",
        """
        SELECT COUNT(*)
        FROM public.desordres AS d
        JOIN public.link_desordres_troncons AS l ON l.desordre_id = d.id
        JOIN public.troncons AS t ON t.id = l.troncon_id
        WHERE d.id = ANY(%s::uuid[])
          AND (ST_Length(d.geometry) < 5 OR ST_Length(d.geometry) > 30
               OR ST_Distance(d.geometry, t.geometry) > 1e-8)
        """,
        (list(_kind_ids("LINESTRING_PROJETE")),),
    )
    _assert_zero(
        cursor,
        "lignes libres hors plage",
        """
        SELECT COUNT(*)
        FROM public.desordres AS d
        JOIN public.link_desordres_troncons AS l ON l.desordre_id = d.id
        JOIN public.troncons AS t ON t.id = l.troncon_id
        WHERE d.id = ANY(%s::uuid[])
          AND (ST_Length(d.geometry) < 5 OR ST_Length(d.geometry) > 30
               OR ST_Distance(d.geometry, t.geometry) <= 1e-8
               OR ST_Distance(d.geometry, t.geometry) > 20)
        """,
        (list(_kind_ids("LINESTRING_LIBRE")),),
    )
    _assert_zero(
        cursor,
        "polygones demo invalides",
        """
        SELECT COUNT(*)
        FROM public.desordres AS d
        JOIN public.link_desordres_troncons AS l ON l.desordre_id = d.id
        JOIN public.troncons AS t ON t.id = l.troncon_id
        WHERE d.id = ANY(%s::uuid[])
          AND (NOT ST_IsValid(d.geometry)
               OR ST_Area(d.geometry) < 2 OR ST_Area(d.geometry) > 20
               OR ST_Distance(d.geometry, t.geometry) > 20)
        """,
        (list(_kind_ids("POLYGON_LIBRE")),),
    )


def _validate_observations_and_photos(cursor: Any) -> None:
    _assert_zero(
        cursor,
        "observations demo sans parent desordre exclusif",
        """
        SELECT COUNT(*)
        FROM public.observations
        WHERE id = ANY(%s::uuid[])
          AND (
            desordre_id IS NULL
            OR num_nonnulls(
                desordre_id, troncon_id, ouvrage_hydraulique_id,
                equipement_mesure_id, cheminement_id, mobilier_id,
                reseau_technique_id, amenagement_hydraulique_id, vegetation_id
            ) <> 1
          )
        """,
        (list(_all_ids()["observations"]),),
    )
    _assert_zero(
        cursor,
        "nombre d'observations demo invalide",
        """
        SELECT COUNT(*)
        FROM (
            SELECT d.id, COUNT(o.id) AS count
            FROM public.desordres AS d
            LEFT JOIN public.observations AS o ON o.desordre_id = d.id
            WHERE d.id = ANY(%s::uuid[])
            GROUP BY d.id
        ) AS grouped
        WHERE count < 1 OR count > 2
        """,
        (list(_all_ids()["desordres"]),),
    )
    _assert_zero(
        cursor,
        "nombre de photos demo invalide",
        """
        SELECT COUNT(*)
        FROM (
            SELECT o.id, COUNT(p.id) AS count
            FROM public.observations AS o
            LEFT JOIN public.photos AS p ON p.observation_id = o.id
            WHERE o.id = ANY(%s::uuid[])
            GROUP BY o.id
        ) AS grouped
        WHERE count < 1 OR count > 2
        """,
        (list(_all_ids()["observations"]),),
    )
    _assert_zero(
        cursor,
        "chemins photos demo non deterministes",
        """
        SELECT COUNT(*)
        FROM public.photos
        WHERE id = ANY(%s::uuid[]) AND chemin_source NOT LIKE 'demo/photos/%%'
        """,
        (list(_all_ids()["photos"]),),
    )


def _validate_reperage(cursor: Any) -> None:
    _assert_zero(
        cursor,
        "reperage demo sur type non supporte",
        """
        SELECT COUNT(*)
        FROM public.desordre_localisations_reperage AS l
        JOIN public.desordres AS d ON d.id = l.desordre_id
        WHERE l.id = ANY(%s::uuid[]) AND GeometryType(d.geometry) NOT IN ('POINT', 'LINESTRING')
        """,
        (list(_all_ids()["desordre_localisations_reperage"]),),
    )
    _assert_zero(
        cursor,
        "polygones demo avec reperage",
        """
        SELECT COUNT(*)
        FROM public.desordre_localisations_reperage
        WHERE desordre_id = ANY(%s::uuid[])
        """,
        (list(_kind_ids("POLYGON_LIBRE")),),
    )
    _assert_zero(
        cursor,
        "reperage demo incoherent",
        """
        SELECT COUNT(*)
        FROM public.desordre_localisations_reperage AS l
        LEFT JOIN public.link_desordres_troncons AS dt
          ON dt.desordre_id = l.desordre_id AND dt.troncon_id = l.troncon_id
        LEFT JOIN public.systemes_reperage AS sr
          ON sr.id = l.systeme_reperage_id AND sr.troncon_id = l.troncon_id
        LEFT JOIN public.link_systemes_reperage_bornes AS bd
          ON bd.systeme_reperage_id = l.systeme_reperage_id
         AND bd.borne_id = l.borne_debut_id
        LEFT JOIN public.link_systemes_reperage_bornes AS bf
          ON bf.systeme_reperage_id = l.systeme_reperage_id
         AND bf.borne_id = l.borne_fin_id
        WHERE l.id = ANY(%s::uuid[])
          AND (dt.id IS NULL OR sr.id IS NULL OR bd.id IS NULL
               OR (l.borne_fin_id IS NOT NULL AND bf.id IS NULL))
        """,
        (list(_all_ids()["desordre_localisations_reperage"]),),
    )


def seed_demo_dataset(
    config: PostgreSQLConfig | None = None,
    *,
    reset: bool = True,
    reset_only: bool = False,
    connector: Callable[..., Any] | None = None,
) -> DemoSeedReport:
    selected = config or PostgreSQLConfig.from_env()
    connect = connector or _default_connector()
    try:
        with connect(**selected.connect_kwargs(autocommit=False)) as connection:
            with connection.cursor() as cursor:
                return seed_demo_cursor(cursor, reset=reset, reset_only=reset_only)
    except Exception as exc:
        if isinstance(exc, DemoSeedError):
            raise
        raise DemoSeedError(
            selected.redact_secrets(f"Generation du dataset demo impossible : {exc}")
        ) from exc


def _default_connector() -> Callable[..., Any]:
    try:
        import psycopg
    except ImportError as exc:
        raise DemoSeedError(
            "Le pilote psycopg n'est pas installe ; executez `python -m pip install -e .`"
        ) from exc
    return psycopg.connect


def geometry_kind_counts() -> Counter[str]:
    return Counter(item.kind for item in DESORDRES)


def expected_counts() -> Mapping[str, int]:
    return dict(_expected_counts())


def demo_ids() -> Mapping[str, tuple[UUID, ...]]:
    return dict(_all_ids())
