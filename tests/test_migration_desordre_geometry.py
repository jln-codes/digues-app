import unittest
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

from digues_app.migration.core import INSERT_STATEMENTS
from digues_app.target import PostgreSQLConfig


class DesordreGeometryPostGISIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import psycopg

            load_dotenv(
                Path(__file__).resolve().parents[1] / "config.env",
                override=False,
            )
            cls.connection = psycopg.connect(
                **PostgreSQLConfig.from_env().connect_kwargs(autocommit=False)
            )
            cls.cursor = cls.connection.cursor()
            cls.systeme_id = uuid4()
            cls.digue_id = uuid4()
            cls.troncon_id = uuid4()
            cls.cursor.execute(
                "INSERT INTO public.systemes (id, libelle, valid) "
                "VALUES (%s, 'Test géométrie désordre', true)",
                (cls.systeme_id,),
            )
            cls.cursor.execute(
                "INSERT INTO public.digues "
                "(id, systeme_endiguement_id, libelle, valid) "
                "VALUES (%s, %s, 'Test géométrie désordre', true)",
                (cls.digue_id, cls.systeme_id),
            )
            cls.cursor.execute(
                "INSERT INTO public.troncons "
                "(id, digue_id, libelle, geometry, valid) VALUES "
                "(%s, %s, 'T', "
                "ST_GeomFromText('LINESTRING(0 0, 10 0, 10 10)', 3950), true)",
                (cls.troncon_id, cls.digue_id),
            )
        except Exception as exc:
            connection = getattr(cls, "connection", None)
            if connection is not None:
                connection.rollback()
                connection.close()
            raise unittest.SkipTest(f"PostGIS local indisponible : {exc}")

    @classmethod
    def tearDownClass(cls):
        connection = getattr(cls, "connection", None)
        if connection is not None:
            connection.rollback()
            connection.close()

    def _migrate_geometry(
        self,
        wkt,
        *,
        eligible=True,
        enabled=True,
        tolerance=0.0001,
        troncon_id="default",
    ):
        desordre_id = uuid4()
        selected_troncon_id = (
            self.troncon_id if troncon_id == "default" else troncon_id
        )
        self.cursor.execute(
            INSERT_STATEMENTS["desordres"],
            (
                wkt,
                desordre_id,
                None,
                None,
                None,
                None,
                None,
                enabled,
                eligible,
                tolerance,
                tolerance,
                True,
                selected_troncon_id,
            ),
        )
        self.cursor.execute(
            "SELECT GeometryType(geometry), ST_AsText(geometry) "
            "FROM public.desordres WHERE id = %s",
            (desordre_id,),
        )
        return self.cursor.fetchone()

    def test_equal_positions_remain_a_point_without_reprojection(self):
        kind, wkt = self._migrate_geometry("POINT (5 0)", eligible=False)
        self.assertEqual((kind, wkt), ("POINT", "POINT(5 0)"))

    def test_exact_endpoints_use_canonical_troncon_subline(self):
        kind, wkt = self._migrate_geometry("LINESTRING (5 0, 10 5)")
        self.assertEqual(kind, "LINESTRING")
        self.assertEqual(wkt, "LINESTRING(5 0,10 0,10 5)")

    def test_endpoints_inside_default_tolerance_are_reprojected(self):
        _, wkt = self._migrate_geometry(
            "LINESTRING (5 0.00009, 9.99991 5)"
        )
        self.assertEqual(wkt, "LINESTRING(5 0,10 0,10 5)")

    def test_endpoint_beyond_tolerance_keeps_ab_segment(self):
        source = "LINESTRING(5 0.00011,9.99989 5)"
        _, wkt = self._migrate_geometry(source)
        self.assertEqual(wkt, source)

    def test_disabled_reprojection_keeps_ab_segment(self):
        source = "LINESTRING(5 0,10 5)"
        _, wkt = self._migrate_geometry(source, enabled=False)
        self.assertEqual(wkt, source)

    def test_custom_tolerance_controls_reprojection(self):
        source = "LINESTRING(5 0.001,9.999 5)"
        _, strict_wkt = self._migrate_geometry(source, tolerance=0.0001)
        _, relaxed_wkt = self._migrate_geometry(source, tolerance=0.002)
        self.assertEqual(strict_wkt, source)
        self.assertEqual(relaxed_wkt, "LINESTRING(5 0,10 0,10 5)")

    def test_reverse_positions_preserve_a_to_b_orientation(self):
        _, wkt = self._migrate_geometry("LINESTRING(10 5,5 0)")
        self.assertEqual(wkt, "LINESTRING(10 5,10 0,5 0)")

    def test_missing_or_invalid_linear_id_keeps_ab_segment(self):
        source = "LINESTRING(5 0,10 5)"
        _, missing_wkt = self._migrate_geometry(source, troncon_id=None)
        _, invalid_wkt = self._migrate_geometry(source, troncon_id=uuid4())
        self.assertEqual(missing_wkt, source)
        self.assertEqual(invalid_wkt, source)

    def test_couchdb_fallback_is_not_submitted_to_reprojection(self):
        source = "LINESTRING(5 0,6 2,8 3,10 5)"
        _, wkt = self._migrate_geometry(source, eligible=False)
        self.assertEqual(wkt, source)


if __name__ == "__main__":
    unittest.main()
