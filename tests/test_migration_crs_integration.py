import unittest
from pathlib import Path

from dotenv import load_dotenv

from digues_app.migration.crs import CRSInfo, geometry_sql
from digues_app.target import PostgreSQLConfig


class CRSPostGISIntegrationTest(unittest.TestCase):
    def test_real_reprojection_changes_coordinates_and_roundtrips(self):
        try:
            import psycopg
            load_dotenv(
                Path(__file__).resolve().parents[1] / "config.env",
                override=False,
            )
            config = PostgreSQLConfig.from_env()
            connection = psycopg.connect(**config.connect_kwargs(autocommit=True))
        except Exception as exc:
            self.skipTest(f"PostGIS local indisponible : {exc}")
        expression = geometry_sql(CRSInfo(source_srid=4326))
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    WITH projected AS (SELECT {expression} AS geometry)
                    SELECT ST_SRID(geometry), ST_X(geometry), ST_Y(geometry),
                           ST_X(ST_Transform(geometry, 4326)),
                           ST_Y(ST_Transform(geometry, 4326))
                    FROM projected
                    """,
                    ("POINT (2.5 50.5)",),
                )
                srid, x, y, longitude, latitude = cursor.fetchone()
        self.assertEqual(srid, 3950)
        self.assertGreater(x, 1_000_000)
        self.assertGreater(y, 9_000_000)
        self.assertAlmostEqual(longitude, 2.5, places=6)
        self.assertAlmostEqual(latitude, 50.5, places=6)


if __name__ == "__main__":
    unittest.main()
