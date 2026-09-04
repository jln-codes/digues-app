import unittest
from pathlib import Path

from dotenv import load_dotenv

from digues_app.demo.seed import (
    DEMO_SEED,
    DESORDRES,
    SYSTEMES,
    TRONCONS,
    WGS84_BBOX,
    demo_ids,
    expected_counts,
    geometry_kind_counts,
    seed_demo_cursor,
    stable_uuid,
)
from digues_app.target import PostgreSQLConfig
from digues_app.target.schema import SCHEMA_DDL


class DemoSeedPlanTest(unittest.TestCase):
    def test_plan_counts_are_stable_and_in_requested_range(self):
        counts = expected_counts()
        self.assertEqual(DEMO_SEED, "digues-demo-v1")
        self.assertEqual(counts["systemes"], 3)
        self.assertEqual(counts["digues"], 4)
        self.assertEqual(counts["troncons"], 8)
        self.assertEqual(counts["desordres"], 21)
        self.assertEqual(counts["observations"], 32)
        self.assertEqual(counts["photos"], 53)
        self.assertEqual(counts["systemes_reperage"], len(TRONCONS))
        self.assertEqual(counts["bornes_reperage"], len(TRONCONS) * 2)

        kinds = geometry_kind_counts()
        self.assertEqual(kinds["POINT_LIBRE"], 5)
        self.assertEqual(kinds["POINT_PROJETE"], 5)
        self.assertEqual(kinds["LINESTRING_LIBRE"], 4)
        self.assertEqual(kinds["LINESTRING_PROJETE"], 4)
        self.assertEqual(kinds["POLYGON_LIBRE"], 3)

    def test_identifiers_and_origins_are_deterministic(self):
        self.assertEqual(
            stable_uuid("systeme", "carbonade"),
            stable_uuid("systeme", "carbonade"),
        )
        all_ids = [
            identifier
            for identifiers in demo_ids().values()
            for identifier in identifiers
        ]
        self.assertEqual(len(all_ids), len(set(all_ids)))

        xmin, ymin, xmax, ymax = WGS84_BBOX
        for systeme in SYSTEMES:
            with self.subTest(systeme=systeme.slug):
                self.assertGreater(systeme.origin_lon, xmin)
                self.assertLess(systeme.origin_lon, xmax)
                self.assertGreater(systeme.origin_lat, ymin)
                self.assertLess(systeme.origin_lat, ymax)

    def test_desordres_refer_to_known_troncons_and_systems(self):
        troncon_slugs = {troncon.slug for troncon in TRONCONS}
        system_slugs = {systeme.slug for systeme in SYSTEMES}
        for desordre in DESORDRES:
            with self.subTest(desordre=desordre.slug):
                self.assertIn(desordre.troncon_slug, troncon_slugs)
                self.assertIn(desordre.system_slug, system_slugs)


class DemoSeedPostGISTest(unittest.TestCase):
    def test_current_schema_accepts_and_validates_demo_seed(self):
        try:
            import psycopg

            load_dotenv(Path(__file__).resolve().parents[1] / "config.env", override=False)
            connection = psycopg.connect(
                **PostgreSQLConfig.from_env().connect_kwargs(autocommit=False)
            )
        except Exception as exc:
            raise unittest.SkipTest(f"PostGIS local indisponible : {exc}")

        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT "
                        "(SELECT extversion FROM pg_extension WHERE extname = 'postgis'), "
                        "(SELECT extversion FROM pg_extension WHERE extname = 'pgcrypto')"
                    )
                    postgis, pgcrypto = cursor.fetchone()
                    if postgis is None or pgcrypto is None:
                        raise unittest.SkipTest("Extensions PostGIS/pgcrypto absentes")
                    for statement in SCHEMA_DDL:
                        cursor.execute(statement)

                    report = seed_demo_cursor(cursor)
                    self.assertEqual(report.counts["systemes"], 3)
                    self.assertEqual(report.geometry_counts["POINT"], 10)
                    self.assertEqual(report.geometry_counts["LINESTRING"], 8)
                    self.assertEqual(report.geometry_counts["POLYGON"], 3)
                    self.assertGreater(report.system_lengths_m["SE Carbonade"], 3000)
                    self.assertLess(report.system_lengths_m["SE Carbonade"], 4200)

                    reset_report = seed_demo_cursor(cursor, reset_only=True)
                    self.assertTrue(all(count == 0 for count in reset_report.counts.values()))
                connection.rollback()
        except unittest.SkipTest:
            connection.rollback()
            raise
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
