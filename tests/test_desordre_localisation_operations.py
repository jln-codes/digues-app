import unittest
import uuid
from pathlib import Path

from dotenv import load_dotenv

from sirs_postgre.target import PostgreSQLConfig


class DesordreLocalisationOperationsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import psycopg
            from psycopg.rows import dict_row

            load_dotenv(Path(__file__).resolve().parents[1] / "config.env", override=False)
            cls.connection = psycopg.connect(
                **PostgreSQLConfig.from_env().connect_kwargs(autocommit=False),
                row_factory=dict_row,
            )
            cls.cursor = cls.connection.cursor()
            cls.cursor.execute(
                "SELECT to_regprocedure('public.synchroniser_desordre_reperage(uuid,uuid)') IS NOT NULL AS available"
            )
            if not cls.cursor.fetchone()["available"]:
                raise unittest.SkipTest("Schéma de synchronisation absent")
            cls.systeme_endiguement = uuid.uuid4()
            cls.digue = uuid.uuid4()
            cls.troncon = uuid.uuid4()
            cls.troncon_superpose = uuid.uuid4()
            cls.systeme = uuid.uuid4()
            cls.systeme_superpose = uuid.uuid4()
            cls.borne_debut = uuid.uuid4()
            cls.borne_fin = uuid.uuid4()
            cls.borne_superpose_debut = uuid.uuid4()
            cls.borne_superpose_fin = uuid.uuid4()
            cls.cursor.execute(
                "INSERT INTO public.systemes (id, libelle, valid) VALUES (%s, 'Opérations', true)",
                (cls.systeme_endiguement,),
            )
            cls.cursor.execute(
                "INSERT INTO public.digues (id, systeme_endiguement_id, libelle, valid) VALUES (%s, %s, 'Digue', true)",
                (cls.digue, cls.systeme_endiguement),
            )
            cls.cursor.execute(
                """
                INSERT INTO public.troncons (id, digue_id, libelle, geometry, valid)
                VALUES
                    (%s, %s, 'Composite', ST_GeomFromText(
                        'LINESTRING(0 0,20 0,40 10,60 0,100 0)', 3950), true),
                    (%s, %s, 'Superposé', ST_GeomFromText(
                        'LINESTRING(0 0,20 0,40 10,60 0,100 0)', 3950), true)
                """,
                (cls.troncon, cls.digue, cls.troncon_superpose, cls.digue),
            )
            for systeme, troncon, debut, fin, pr0, pr1 in (
                (cls.systeme, cls.troncon, cls.borne_debut, cls.borne_fin, 1000, 0),
                (
                    cls.systeme_superpose,
                    cls.troncon_superpose,
                    cls.borne_superpose_debut,
                    cls.borne_superpose_fin,
                    5000,
                    6000,
                ),
            ):
                cls.cursor.execute(
                    "INSERT INTO public.systemes_reperage (id, troncon_id, libelle, valid) VALUES (%s, %s, 'Repérage', true)",
                    (systeme, troncon),
                )
                cls.cursor.execute(
                    """
                    INSERT INTO public.bornes_reperage (id, libelle, geometry, valid)
                    VALUES
                        (%s, 'A', ST_SetSRID(ST_Point(0, 0), 3950), true),
                        (%s, 'B', ST_SetSRID(ST_Point(100, 0), 3950), true)
                    """,
                    (debut, fin),
                )
                cls.cursor.execute(
                    "INSERT INTO public.link_troncons_bornes VALUES (%s, %s), (%s, %s)",
                    (troncon, debut, troncon, fin),
                )
                # Ordre volontairement opposé au rôle spatial.
                cls.cursor.execute(
                    """
                    INSERT INTO public.link_systemes_reperage_bornes
                        (id, systeme_reperage_id, borne_id, valeur_pr, valid)
                    VALUES (%s, %s, %s, %s, true),
                           (%s, %s, %s, %s, true)
                    """,
                    (uuid.uuid4(), systeme, debut, pr0, uuid.uuid4(), systeme, fin, pr1),
                )
                cls.cursor.execute(
                    "UPDATE public.troncons SET systeme_reperage_defaut_id = %s WHERE id = %s",
                    (systeme, troncon),
                )
        except unittest.SkipTest:
            raise
        except Exception as exc:
            raise unittest.SkipTest(f"PostGIS local indisponible : {exc}")

    @classmethod
    def tearDownClass(cls):
        connection = getattr(cls, "connection", None)
        if connection is not None:
            connection.rollback()
            connection.close()

    def add_desordre(self, wkt):
        desordre = uuid.uuid4()
        self.cursor.execute(
            "INSERT INTO public.desordres (id, designation, geometry, valid) VALUES (%s, 'Test', ST_GeomFromText(%s, 3950), true)",
            (desordre, wkt),
        )
        return desordre

    def setUp(self):
        self.cursor.execute("SAVEPOINT localisation_test")

    def tearDown(self):
        self.cursor.execute("ROLLBACK TO SAVEPOINT localisation_test")
        self.cursor.execute("RELEASE SAVEPOINT localisation_test")

    def link(self, desordre, troncon):
        self.cursor.execute(
            "INSERT INTO public.link_desordres_troncons (desordre_id, troncon_id) VALUES (%s, %s)",
            (desordre, troncon),
        )

    def localisation(self, desordre):
        self.cursor.execute(
            "SELECT * FROM public.desordre_localisations_reperage WHERE desordre_id = %s",
            (desordre,),
        )
        return self.cursor.fetchone()

    def geometry(self, desordre):
        self.cursor.execute(
            "SELECT ST_AsText(geometry) AS wkt, ST_NPoints(geometry) AS points FROM public.desordres WHERE id = %s",
            (desordre,),
        )
        return self.cursor.fetchone()

    def test_zero_one_many_then_one_recomputes_without_moving_point(self):
        desordre = self.add_desordre("POINT(10 7)")
        self.assertIsNone(self.localisation(desordre))
        self.link(desordre, self.troncon)
        self.assertIsNotNone(self.localisation(desordre))
        self.assertEqual(self.geometry(desordre)["wkt"], "POINT(10 7)")
        self.link(desordre, self.troncon_superpose)
        self.assertIsNone(self.localisation(desordre))
        self.cursor.execute(
            "DELETE FROM public.link_desordres_troncons WHERE desordre_id = %s AND troncon_id = %s",
            (desordre, self.troncon_superpose),
        )
        self.assertIsNotNone(self.localisation(desordre))
        self.assertEqual(self.geometry(desordre)["wkt"], "POINT(10 7)")

    def test_point_reperage_edit_repositions_on_axis_and_keeps_borne(self):
        desordre = self.add_desordre("POINT(10 7)")
        self.link(desordre, self.troncon)
        self.cursor.execute(
            """
            UPDATE public.desordre_localisations_reperage
            SET borne_debut_id = %s, distance_debut_m = 10,
                position_debut_relative = 'APRES_BORNE'
            WHERE desordre_id = %s
            """,
            (self.borne_debut, desordre),
        )
        localisation = self.localisation(desordre)
        self.assertEqual(localisation["borne_debut_id"], self.borne_debut)
        self.cursor.execute(
            "SELECT ST_Distance(d.geometry, t.geometry) AS distance FROM public.desordres d CROSS JOIN public.troncons t WHERE d.id = %s AND t.id = %s",
            (desordre, self.troncon),
        )
        self.assertAlmostEqual(self.cursor.fetchone()["distance"], 0.0)

    def test_point_xy_and_lonlat_edits_update_the_single_geometry(self):
        desordre = self.add_desordre("POINT(10 7)")
        self.link(desordre, self.troncon)
        self.cursor.execute(
            "UPDATE public.view_desordres_points_saisie SET coord_x_3950 = 12, coord_y_3950 = 9 WHERE id = %s",
            (desordre,),
        )
        self.assertEqual(self.geometry(desordre)["wkt"], "POINT(12 9)")
        self.cursor.execute(
            """
            UPDATE public.view_desordres_points_saisie
            SET longitude_4326 = 2.25, latitude_4326 = 48.75
            WHERE id = %s
            """,
            (desordre,),
        )
        self.cursor.execute(
            """
            SELECT ST_X(ST_Transform(geometry, 4326)) AS lon,
                   ST_Y(ST_Transform(geometry, 4326)) AS lat
            FROM public.desordres WHERE id = %s
            """,
            (desordre,),
        )
        result = self.cursor.fetchone()
        self.assertAlmostEqual(result["lon"], 2.25, places=8)
        self.assertAlmostEqual(result["lat"], 48.75, places=8)
        self.assertIsNotNone(self.localisation(desordre))

    def test_polygon_never_gets_an_editable_reperage(self):
        desordre = self.add_desordre("POLYGON((0 0,20 0,20 20,0 20,0 0))")
        self.link(desordre, self.troncon)
        self.assertIsNone(self.localisation(desordre))

    def test_free_line_edit_keeps_all_vertices_and_recomputes_only_ends(self):
        desordre = self.add_desordre("LINESTRING(5 4,20 8,45 15,70 4,95 3)")
        self.link(desordre, self.troncon)
        before = self.localisation(desordre)
        self.assertEqual(self.geometry(desordre)["points"], 5)
        self.cursor.execute(
            "UPDATE public.desordres SET geometry = ST_GeomFromText('LINESTRING(7 6,25 12,50 20,75 9,90 5)', 3950) WHERE id = %s",
            (desordre,),
        )
        self.assertEqual(self.geometry(desordre)["points"], 5)
        after = self.localisation(desordre)
        self.assertNotEqual(before["distance_debut_m"], after["distance_debut_m"])

    def test_line_reperage_edit_uses_substring_with_intermediate_vertices(self):
        desordre = self.add_desordre("LINESTRING(5 4,50 20,95 3)")
        self.link(desordre, self.troncon)
        self.cursor.execute(
            """
            UPDATE public.desordre_localisations_reperage
            SET borne_debut_id = %s, distance_debut_m = 10,
                position_debut_relative = 'APRES_BORNE',
                borne_fin_id = %s, distance_fin_m = 10,
                position_fin_relative = 'AVANT_BORNE'
            WHERE desordre_id = %s
            """,
            (self.borne_debut, self.borne_fin, desordre),
        )
        result = self.geometry(desordre)
        self.assertGreater(result["points"], 2)
        self.assertIn("40 10", result["wkt"])

    def test_overlapping_troncons_use_only_explicit_reference(self):
        self.cursor.execute(
            """
            SELECT a.pr AS pr_a, b.pr AS pr_b
            FROM public.xy_vers_reperage(
                %s, %s, ST_SetSRID(ST_Point(20, 0), 3950)
            ) AS a
            CROSS JOIN public.xy_vers_reperage(
                %s, %s, ST_SetSRID(ST_Point(20, 0), 3950)
            ) AS b
            """,
            (self.troncon, self.systeme, self.troncon_superpose, self.systeme_superpose),
        )
        result = self.cursor.fetchone()
        self.assertNotEqual(result["pr_a"], result["pr_b"])

    def test_inversion_keeps_object_geometry_and_recalculates_roles(self):
        desordre = self.add_desordre("POINT(10 7)")
        self.link(desordre, self.troncon)
        before_geometry = self.geometry(desordre)["wkt"]
        before = self.localisation(desordre)
        self.cursor.execute("SELECT public.inverser_troncon(%s)", (self.troncon,))
        after = self.localisation(desordre)
        self.assertEqual(self.geometry(desordre)["wkt"], before_geometry)
        self.assertEqual(after["borne_debut_id"], before["borne_debut_id"])
        self.assertNotEqual(
            after["position_debut_relative"], before["position_debut_relative"]
        )
        self.cursor.execute(
            "SELECT borne_id, role_spatial FROM public.view_systemes_reperage_bornes WHERE systeme_reperage_id = %s",
            (self.systeme,),
        )
        roles = {row["borne_id"]: row["role_spatial"] for row in self.cursor.fetchall()}
        self.assertEqual(roles[self.borne_debut], "FIN_TRONCON")
        self.assertEqual(roles[self.borne_fin], "DEBUT_TRONCON")


if __name__ == "__main__":
    unittest.main()
