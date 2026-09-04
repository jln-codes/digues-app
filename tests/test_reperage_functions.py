import unittest
import uuid
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

from digues_app.target import PostgreSQLConfig
from digues_app.target.reperage import (
    FUNCTION_DEFINITIONS,
    REPERAGE_FUNCTION_DDL,
    STATUS_CONTRACT,
)
from digues_app.target.schema import SCHEMA_DDL


POSTGIS_SEARCH_PATH_SUFFIX_PLACEHOLDER = "__SIRS_POSTGIS_SEARCH_PATH_SUFFIX__"


class ReperageFunctionSchemaTest(unittest.TestCase):
    def test_functions_are_part_of_schema_ddl(self):
        self.assertEqual(
            set(FUNCTION_DEFINITIONS),
            {
                "_reperage_pr_depuis_abscisse",
                "xy_vers_reperage",
                "borne_offset_vers_xy",
                "pr_vers_xy",
            },
        )
        for statement in REPERAGE_FUNCTION_DDL:
            self.assertIn(
                statement.replace(POSTGIS_SEARCH_PATH_SUFFIX_PLACEHOLDER, ""),
                SCHEMA_DDL,
            )

    def test_public_engine_is_explicit_and_read_only(self):
        sql = "\n".join(REPERAGE_FUNCTION_DDL).lower()
        self.assertNotIn("systeme_reperage_defaut_id", sql)
        self.assertNotIn("create trigger", sql)
        self.assertNotIn(" insert ", sql)
        self.assertNotIn(" update ", sql)
        self.assertNotIn(" delete ", sql)
        self.assertEqual(sql.count("stable"), 4)
        for function_name in (
            "xy_vers_reperage",
            "borne_offset_vers_xy",
            "pr_vers_xy",
        ):
            definition = FUNCTION_DEFINITIONS[function_name]
            self.assertIn("p_troncon_id UUID", definition)
            self.assertIn("p_systeme_reperage_id UUID", definition)

    def test_status_contract_is_text_and_complete(self):
        self.assertEqual(
            set(STATUS_CONTRACT),
            {
                "OK",
                "REFERENCE_ABSENTE",
                "CONFLIT_SYSTEME",
                "HORS_DOMAINE",
                "SYSTEME_INCOMPLET",
                "AMBIGU",
                "GEOMETRIE_INVALIDE",
            },
        )


class ReperageFunctionPostGISIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import psycopg
            from psycopg.rows import dict_row

            load_dotenv(
                Path(__file__).resolve().parents[1] / "config.env",
                override=False,
            )
            config = PostgreSQLConfig.from_env()
            cls.connection = psycopg.connect(
                **config.connect_kwargs(autocommit=False), row_factory=dict_row
            )
            cls.cursor = cls.connection.cursor()
            cls.cursor.execute(
                """
                SELECT
                    to_regprocedure(
                        'public.xy_vers_reperage(uuid,uuid,geometry)'
                    ) IS NOT NULL AS xy,
                    to_regprocedure(
                        'public.borne_offset_vers_xy(uuid,uuid,uuid,double precision)'
                    ) IS NOT NULL AS borne,
                    to_regprocedure(
                        'public.pr_vers_xy(uuid,uuid,numeric)'
                    ) IS NOT NULL AS pr
                """
            )
            if not all(cls.cursor.fetchone().values()):
                raise unittest.SkipTest(
                    "Fonctions de repérage absentes ; exécuter init-schema."
                )
            cls.systeme_id = uuid.uuid4()
            cls.digue_id = uuid.uuid4()
            cls.troncon_id = uuid.uuid4()
            cls.autre_troncon_id = uuid.uuid4()
            cls.cursor.execute(
                "INSERT INTO public.systemes (id, libelle, valid) VALUES (%s, %s, true)",
                (cls.systeme_id, "Tests repérage"),
            )
            cls.cursor.execute(
                """
                INSERT INTO public.digues
                    (id, systeme_endiguement_id, libelle, valid)
                VALUES (%s, %s, %s, true)
                """,
                (cls.digue_id, cls.systeme_id, "Digue tests repérage"),
            )
            cls.cursor.execute(
                """
                INSERT INTO public.troncons
                    (id, digue_id, libelle, geometry, valid)
                VALUES
                    (%s, %s, %s,
                     ST_GeomFromText('LINESTRING(0 0, 1000 0)', 3950), true),
                    (%s, %s, %s,
                     ST_GeomFromText('LINESTRING(0 100, 1000 100)', 3950), true)
                """,
                (
                    cls.troncon_id,
                    cls.digue_id,
                    "Tronçon tests repérage",
                    cls.autre_troncon_id,
                    cls.digue_id,
                    "Autre tronçon tests repérage",
                ),
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

    @classmethod
    def add_reference_system(cls, references, troncon_id=None, valid=True):
        """Crée un système et ses bornes : (abscisse, PR[, écart Y])."""
        system_id = uuid.uuid4()
        target_troncon = troncon_id or cls.troncon_id
        cls.cursor.execute(
            """
            INSERT INTO public.systemes_reperage
                (id, troncon_id, libelle, valid)
            VALUES (%s, %s, %s, %s)
            """,
            (system_id, target_troncon, "Système synthétique", valid),
        )
        borne_ids = []
        y_axis = 100.0 if target_troncon == cls.autre_troncon_id else 0.0
        for order, reference in enumerate(references):
            abscissa, pr = reference[:2]
            off_axis = reference[2] if len(reference) == 3 else 0.0
            borne_id = uuid.uuid4()
            borne_ids.append(borne_id)
            cls.cursor.execute(
                """
                INSERT INTO public.bornes_reperage
                    (id, libelle, geometry, valid)
                VALUES (
                    %s, %s, ST_SetSRID(ST_Point(%s, %s), 3950), true
                )
                """,
                (borne_id, f"Borne {order}", abscissa, y_axis + off_axis),
            )
            cls.cursor.execute(
                """
                INSERT INTO public.link_troncons_bornes (troncon_id, borne_id)
                VALUES (%s, %s)
                """,
                (target_troncon, borne_id),
            )
            cls.cursor.execute(
                """
                INSERT INTO public.link_systemes_reperage_bornes
                    (id, systeme_reperage_id, borne_id,
                     valeur_pr, valid)
                VALUES (%s, %s, %s, %s, true)
                """,
                (uuid.uuid4(), system_id, borne_id, Decimal(str(pr))),
            )
        return system_id, borne_ids

    def xy(self, system_id, x, y=0.0, troncon_id=None):
        self.cursor.execute(
            """
            SELECT *, ST_X(point_source) AS source_x,
                      ST_Y(point_source) AS source_y,
                      ST_X(point_projete) AS projected_x,
                      ST_Y(point_projete) AS projected_y
            FROM public.xy_vers_reperage(
                %s, %s, ST_SetSRID(ST_Point(%s, %s), 3950)
            )
            """,
            (troncon_id or self.troncon_id, system_id, x, y),
        )
        return self.cursor.fetchone()

    def from_borne(self, system_id, borne_id, offset, troncon_id=None):
        self.cursor.execute(
            """
            SELECT *, ST_X(point_xy) AS x, ST_Y(point_xy) AS y
            FROM public.borne_offset_vers_xy(%s, %s, %s, %s)
            """,
            (troncon_id or self.troncon_id, system_id, borne_id, offset),
        )
        return self.cursor.fetchone()

    def from_pr(self, system_id, pr, troncon_id=None):
        self.cursor.execute(
            """
            SELECT *, ST_X(point_xy) AS x, ST_Y(point_xy) AS y
            FROM public.pr_vers_xy(%s, %s, %s)
            """,
            (troncon_id or self.troncon_id, system_id, Decimal(str(pr))),
        )
        return self.cursor.fetchone()

    def assert_float(self, actual, expected, places=7):
        self.assertAlmostEqual(float(actual), float(expected), places=places)

    def test_a_simple_system_and_round_trips(self):
        system_id, bornes = self.add_reference_system([(0, 0), (1000, 1000)])
        linear = self.xy(system_id, 420)
        self.assertEqual((linear["statut"], linear["statut_pr"]), ("OK", "OK"))
        self.assert_float(linear["abscisse_m"], 420)
        self.assert_float(linear["pr"], 420)

        point = self.from_pr(system_id, 420)
        self.assertEqual(point["statut"], "OK")
        self.assert_float(point["x"], 420)
        self.assert_float(point["abscisse_m"], 420)

        projected = self.from_borne(
            system_id, linear["borne_id"], linear["offset_borne_m"]
        )
        self.assertEqual(projected["statut"], "OK")
        self.assert_float(projected["x"], linear["projected_x"])
        back = self.xy(system_id, point["x"])
        self.assert_float(back["pr"], 420)
        self.assertIn(linear["borne_id"], bornes)

    def test_b_non_zero_pr_origin(self):
        system_id, _ = self.add_reference_system([(0, 12500), (1000, 13500)])
        result = self.xy(system_id, 420)
        self.assertEqual(result["statut_pr"], "OK")
        self.assert_float(result["pr"], 12920)

    def test_c_scale_is_not_geometric_abscissa(self):
        system_id, _ = self.add_reference_system([(0, 12500), (800, 13200)])
        result = self.xy(system_id, 400)
        self.assertEqual(result["statut_pr"], "OK")
        self.assert_float(result["pr"], 12850)
        self.assertNotEqual(float(result["pr"]), result["abscisse_m"])
        reverse = self.from_pr(system_id, 12850)
        self.assertEqual(reverse["statut"], "OK")
        self.assert_float(reverse["abscisse_m"], 400)

    def test_d_decreasing_pr(self):
        system_id, _ = self.add_reference_system([(0, 1000), (1000, 0)])
        result = self.xy(system_id, 420)
        self.assert_float(result["pr"], 580)
        reverse = self.from_pr(system_id, 580)
        self.assertEqual(reverse["statut"], "OK")
        self.assert_float(reverse["x"], 420)

    def test_e_three_bornes_use_the_physical_segment(self):
        system_id, _ = self.add_reference_system(
            [(0, 0), (400, 500), (1000, 1500)]
        )
        self.assert_float(self.xy(system_id, 200)["pr"], 250)
        self.assert_float(self.xy(system_id, 700)["pr"], 1000)
        self.assert_float(self.from_pr(system_id, 250)["x"], 200)
        self.assert_float(self.from_pr(system_id, 1000)["x"], 700)

    def test_f_and_g_interior_and_off_axis_bornes_are_projected(self):
        system_id, bornes = self.add_reference_system(
            [(0, 0), (400, 400, 12), (1000, 1000)]
        )
        result = self.from_borne(system_id, bornes[1], 50)
        self.assertEqual(result["statut"], "OK")
        self.assert_float(result["abscisse_borne_m"], 400)
        self.assert_float(result["abscisse_m"], 450)
        self.assert_float(result["x"], 450)

    def test_h_off_axis_xy_preserves_source_and_uses_projection(self):
        system_id, _ = self.add_reference_system([(0, 0), (1000, 1000)])
        result = self.xy(system_id, 420, 12)
        self.assertEqual(result["statut"], "OK")
        self.assert_float(result["source_x"], 420)
        self.assert_float(result["source_y"], 12)
        self.assert_float(result["projected_x"], 420)
        self.assert_float(result["projected_y"], 0)
        self.assert_float(result["distance_axe_m"], 12)
        self.assert_float(result["pr"], 420)

    def test_i_and_j_out_of_domain_are_not_clamped(self):
        system_id, bornes = self.add_reference_system([(100, 0), (900, 800)])
        offset = self.from_borne(system_id, bornes[0], -101)
        self.assertEqual(offset["statut"], "HORS_DOMAINE")
        self.assertIsNone(offset["point_xy"])
        pr = self.from_pr(system_id, 801)
        self.assertEqual(pr["statut"], "HORS_DOMAINE")
        self.assertIsNone(pr["point_xy"])
        xy = self.xy(system_id, 50)
        self.assertEqual(xy["statut"], "OK")
        self.assertEqual(xy["statut_pr"], "HORS_DOMAINE")
        self.assertIsNotNone(xy["point_projete"])
        self.assertIsNone(xy["pr"])

    def test_k_duplicate_pr_is_ambiguous(self):
        system_id, _ = self.add_reference_system([(0, 10), (100, 10)])
        result = self.from_pr(system_id, 10)
        self.assertEqual(result["statut"], "AMBIGU")
        self.assertEqual(result["details"]["cause"], "PR_DUPLIQUES")

    def test_l_non_monotone_pr_is_ambiguous_only_for_inverse(self):
        system_id, _ = self.add_reference_system(
            [(0, 0), (100, 200), (200, 100)]
        )
        inverse = self.from_pr(system_id, 150)
        self.assertEqual(inverse["statut"], "AMBIGU")
        self.assertEqual(
            inverse["details"]["cause"], "RELATION_PR_NON_MONOTONE"
        )
        exact_inverse = self.from_pr(system_id, 200)
        self.assertEqual(exact_inverse["statut"], "AMBIGU")
        direct = self.xy(system_id, 50)
        self.assertEqual(direct["statut_pr"], "OK")
        self.assert_float(direct["pr"], 100)

    def test_m_equidistant_bornes_are_ambiguous(self):
        system_id, _ = self.add_reference_system([(0, 0), (100, 100)])
        result = self.xy(system_id, 50)
        self.assertEqual(result["statut"], "AMBIGU")
        self.assertIsNone(result["borne_id"])
        self.assertEqual(result["statut_pr"], "OK")
        self.assert_float(result["pr"], 50)

    def test_n_system_from_another_troncon_is_rejected(self):
        system_id, bornes = self.add_reference_system(
            [(0, 0), (1000, 1000)], troncon_id=self.autre_troncon_id
        )
        self.assertEqual(self.xy(system_id, 10)["statut"], "CONFLIT_SYSTEME")
        self.assertEqual(
            self.from_pr(system_id, 10)["statut"], "CONFLIT_SYSTEME"
        )
        self.assertEqual(
            self.from_borne(system_id, bornes[0], 10)["statut"],
            "CONFLIT_SYSTEME",
        )

    def test_o_one_borne_has_conversion_specific_contracts(self):
        system_id, bornes = self.add_reference_system([(400, 500)])
        offset = self.from_borne(system_id, bornes[0], 50)
        self.assertEqual(offset["statut"], "OK")
        self.assertEqual(offset["statut_pr"], "SYSTEME_INCOMPLET")
        self.assert_float(offset["x"], 450)

        exact_xy = self.xy(system_id, 400)
        self.assertEqual((exact_xy["statut"], exact_xy["statut_pr"]), ("OK", "OK"))
        self.assert_float(exact_xy["pr"], 500)
        other_xy = self.xy(system_id, 450)
        self.assertEqual(other_xy["statut"], "OK")
        self.assertEqual(other_xy["statut_pr"], "SYSTEME_INCOMPLET")

        exact_pr = self.from_pr(system_id, 500)
        self.assertEqual(exact_pr["statut"], "OK")
        self.assert_float(exact_pr["x"], 400)
        self.assertEqual(self.from_pr(system_id, 501)["statut"], "SYSTEME_INCOMPLET")

    def test_explicit_system_is_independent_from_default(self):
        default_a, _ = self.add_reference_system([(0, 0), (1000, 1000)])
        explicit_b, _ = self.add_reference_system([(0, 12000), (1000, 13000)])
        default_c, _ = self.add_reference_system([(0, 50), (1000, 60)])
        self.cursor.execute(
            "UPDATE public.troncons SET systeme_reperage_defaut_id = %s WHERE id = %s",
            (default_a, self.troncon_id),
        )
        before = self.xy(explicit_b, 420)
        self.cursor.execute(
            "UPDATE public.troncons SET systeme_reperage_defaut_id = %s WHERE id = %s",
            (default_c, self.troncon_id),
        )
        after = self.xy(explicit_b, 420)
        self.assertEqual(before["systeme_reperage_id"], explicit_b)
        self.assertEqual(after["systeme_reperage_id"], explicit_b)
        self.assertEqual(before["pr"], after["pr"])
        self.assert_float(after["pr"], 12420)

    def test_historical_valid_false_rows_remain_usable_and_are_reported(self):
        system_id, bornes = self.add_reference_system(
            [(0, 0), (1000, 1000)], valid=False
        )
        self.cursor.execute(
            "UPDATE public.bornes_reperage SET valid = false WHERE id = %s",
            (bornes[0],),
        )
        self.cursor.execute(
            """
            UPDATE public.link_systemes_reperage_bornes
            SET valid = false
            WHERE systeme_reperage_id = %s AND borne_id = %s
            """,
            (system_id, bornes[0]),
        )
        result = self.xy(system_id, 250)
        self.assertEqual((result["statut"], result["statut_pr"]), ("OK", "OK"))
        self.assertFalse(result["details"]["systeme_valid"])
        self.assertGreater(result["details"]["pr"]["references_valid_false"], 0)

    def test_missing_reference_and_invalid_input_geometry_have_statuses(self):
        system_id, _ = self.add_reference_system([(0, 0), (1000, 1000)])
        missing = self.xy(uuid.uuid4(), 10)
        self.assertEqual(missing["statut"], "REFERENCE_ABSENTE")
        self.cursor.execute(
            """
            SELECT statut
            FROM public.xy_vers_reperage(
                %s, %s, ST_SetSRID(ST_Point(10, 0), 4326)
            )
            """,
            (self.troncon_id, system_id),
        )
        self.assertEqual(self.cursor.fetchone()["statut"], "GEOMETRIE_INVALIDE")


if __name__ == "__main__":
    unittest.main()
