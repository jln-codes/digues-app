from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import unittest
from uuid import UUID, uuid4

from dotenv import load_dotenv

from sirs_postgre.target import PostgreSQLConfig

from sirs_postgre.migration.desordre_reperage import (
    _distance_and_position,
    prepare_desordre_reperage_migration,
)
from sirs_postgre.migration.anomalies import collect_anomalies
from sirs_postgre.migration.reperage import (
    BorneReperageRow,
    LinkSystemeReperageBorneRow,
    PreparedReperageMigration,
    SystemeReperageRow,
)


TRONCON_A = UUID("00000000-0000-0000-0000-000000000001")
TRONCON_B = UUID("00000000-0000-0000-0000-000000000002")
SYSTEME_A = UUID("00000000-0000-0000-0000-000000000011")
SYSTEME_B = UUID("00000000-0000-0000-0000-000000000012")
BORNE_A = UUID("00000000-0000-0000-0000-000000000021")
BORNE_B = UUID("00000000-0000-0000-0000-000000000022")
DESORDRE = UUID("00000000-0000-0000-0000-000000000031")


def reperage_fixture():
    return PreparedReperageMigration(
        systemes=(
            SystemeReperageRow(SYSTEME_A, TRONCON_A, "A", None, True),
            SystemeReperageRow(SYSTEME_B, TRONCON_B, "B", None, True),
        ),
        bornes=(
            BorneReperageRow(BORNE_A, "A0", None, "POINT (0 0)", False, None, None, True),
            BorneReperageRow(BORNE_B, "A1", None, "POINT (100 0)", False, None, None, True),
        ),
        troncons_bornes=(),
        systemes_bornes=(
            LinkSystemeReperageBorneRow(
                UUID("00000000-0000-0000-0000-000000000041"),
                SYSTEME_A,
                BORNE_A,
                Decimal("0"),
                0,
                True,
            ),
            LinkSystemeReperageBorneRow(
                UUID("00000000-0000-0000-0000-000000000042"),
                SYSTEME_A,
                BORNE_B,
                Decimal("100"),
                1,
                True,
            ),
        ),
        systemes_defaut=(),
        inconsistencies=(),
        warnings=(),
    )


def complete_document(**overrides):
    document = {
        "_id": str(DESORDRE),
        "valid": False,
        "linearId": str(TRONCON_A),
        "foreignParentId": str(TRONCON_A),
        "systemeRepId": str(SYSTEME_A),
        "borneDebutId": str(BORNE_A),
        "borneFinId": str(BORNE_B),
        "borne_debut_distance": 12.5,
        "borne_fin_distance": 7,
        "borne_debut_aval": True,
        "borne_fin_aval": False,
        "prDebut": 12.5,
        "prFin": 93,
        "positionDebut": "POINT (12.5 0)",
        "positionFin": "POINT (93 0)",
        "geometryMode": "LINEAR",
        "editedGeoCoordinate": True,
    }
    document.update(overrides)
    return document


class DesordreReperagePreparationTest(unittest.TestCase):
    def prepare(self, document):
        return prepare_desordre_reperage_migration(
            [document],
            desordre_ids={DESORDRE},
            troncon_ids={TRONCON_A, TRONCON_B},
            reperage=reperage_fixture(),
        )

    def test_complete_chain_preserves_source_without_inferring_authority(self):
        prepared = self.prepare(complete_document())
        self.assertEqual(prepared.source_complete_count, 1)
        self.assertEqual(len(prepared.localisations), 1)
        row = prepared.localisations[0]
        self.assertEqual(row.id.version, 5)
        self.assertEqual(row.troncon_id, TRONCON_A)
        self.assertEqual(row.systeme_reperage_id, SYSTEME_A)
        self.assertEqual(row.offset_debut_m, -12.5)
        self.assertEqual(row.offset_fin_m, 7)
        self.assertEqual(row.pr_debut_source, Decimal("12.5"))
        self.assertEqual(row.position_debut_source_wkt, "POINT (12.5 0)")
        self.assertEqual(row.mode_saisie_source, "IMPORT")
        self.assertEqual(row.politique_autorite, "MANUELLE")
        self.assertFalse(row.valid)
        self.assertTrue(row.trace_source["editedGeoCoordinate"])
        self.assertEqual(row.trace_source["geometryMode"], "LINEAR")

    def test_document_without_positionable_trace_creates_no_location(self):
        prepared = self.prepare({"_id": str(DESORDRE), "valid": True})
        self.assertEqual(prepared.localisations, ())
        self.assertEqual(prepared.source_without_reperage_count, 1)

    def test_partial_chain_is_kept_as_trace_with_nullable_references(self):
        prepared = self.prepare(
            {
                "_id": str(DESORDRE),
                "valid": False,
                "linearId": str(TRONCON_A),
                "positionDebut": "POINT (10 0)",
                "positionFin": "POINT (10 0)",
            }
        )
        row = prepared.localisations[0]
        self.assertEqual(row.qualite, "INCOMPLETE")
        self.assertEqual(row.troncon_id, TRONCON_A)
        self.assertIsNone(row.systeme_reperage_id)
        self.assertEqual(row.trace_source["linearId"], str(TRONCON_A))
        self.assertFalse(row.valid)

    def test_system_from_another_troncon_is_not_materialized(self):
        row = self.prepare(
            complete_document(systemeRepId=str(SYSTEME_B))
        ).localisations[0]
        self.assertEqual(row.qualite, "CONFLIT_SYSTEME")
        self.assertIsNone(row.systeme_reperage_id)
        self.assertIsNone(row.borne_debut_id)
        self.assertEqual(row.trace_source["systemeRepId"], str(SYSTEME_B))

    def test_missing_borne_is_not_replaced_by_proximity(self):
        missing = UUID("00000000-0000-0000-0000-000000000099")
        row = self.prepare(
            complete_document(borneDebutId=str(missing))
        ).localisations[0]
        self.assertEqual(row.qualite, "REFERENCE_ABSENTE")
        self.assertIsNone(row.borne_debut_id)
        self.assertIsNone(row.offset_debut_m)
        self.assertEqual(row.trace_source["borneDebutId"], str(missing))

    def test_missing_troncon_remains_a_missing_reference_not_a_system_guess(self):
        missing = UUID("00000000-0000-0000-0000-000000000098")
        row = self.prepare(
            complete_document(linearId=str(missing))
        ).localisations[0]
        self.assertEqual(row.qualite, "REFERENCE_ABSENTE")
        self.assertIsNone(row.troncon_id)
        self.assertIsNone(row.systeme_reperage_id)
        self.assertEqual(row.trace_source["linearId"], str(missing))

    def test_signed_offset_has_separate_qgis_distance_and_position(self):
        self.assertEqual(_distance_and_position(-35), (35, "AVANT_BORNE"))
        self.assertEqual(_distance_and_position(0), (0.0, "SUR_BORNE"))
        self.assertEqual(_distance_and_position(35), (35, "APRES_BORNE"))
        self.assertEqual(_distance_and_position(None), (None, None))

    def test_partial_reference_produces_a_data_anomaly(self):
        document = complete_document(systemeRepId=str(uuid4()))
        prepared = self.prepare(document)
        anomalies = collect_anomalies(
            [document],
            source_database="test",
            coverage_rows=(),
            prepared_core=SimpleNamespace(
                desordre_reperage=prepared,
                vegetation=SimpleNamespace(vegetation=()),
                photos=(),
            ),
        )
        anomaly = next(
            item
            for item in anomalies
            if item.category == "REPERAGE_REFERENCE_MISSING"
        )
        self.assertEqual(anomaly.source_document_id, str(DESORDRE))
        self.assertEqual(anomaly.target_table, "desordre_localisations_reperage")


class DesordreReperagePostGISIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import psycopg
            from psycopg.rows import dict_row

            load_dotenv(
                Path(__file__).resolve().parents[1] / "config.env",
                override=False,
            )
            cls.psycopg = psycopg
            cls.connection = psycopg.connect(
                **PostgreSQLConfig.from_env().connect_kwargs(autocommit=False),
                row_factory=dict_row,
            )
            cls.cursor = cls.connection.cursor()
            cls.cursor.execute(
                "SELECT to_regclass('public.desordre_localisations_reperage') AS table_name"
            )
            if cls.cursor.fetchone()["table_name"] is None:
                raise unittest.SkipTest("Prototype de repérage absent ; exécuter init-schema.")

            cls.systeme_endiguement_id = uuid4()
            cls.digue_id = uuid4()
            cls.troncon_a = uuid4()
            cls.troncon_b = uuid4()
            cls.systeme_a = uuid4()
            cls.systeme_b = uuid4()
            cls.borne_a = uuid4()
            cls.borne_b = uuid4()
            cls.cursor.execute(
                "INSERT INTO public.systemes (id, libelle, valid) VALUES (%s, 'Test lot 3', true)",
                (cls.systeme_endiguement_id,),
            )
            cls.cursor.execute(
                "INSERT INTO public.digues (id, systeme_endiguement_id, libelle, valid) VALUES (%s, %s, 'Test lot 3', true)",
                (cls.digue_id, cls.systeme_endiguement_id),
            )
            cls.cursor.execute(
                """
                INSERT INTO public.troncons (id, digue_id, libelle, geometry, valid)
                VALUES
                    (%s, %s, 'T A', ST_GeomFromText('LINESTRING(0 0, 100 0)', 3950), true),
                    (%s, %s, 'T B', ST_GeomFromText('LINESTRING(0 10, 100 10)', 3950), true)
                """,
                (cls.troncon_a, cls.digue_id, cls.troncon_b, cls.digue_id),
            )
            cls.cursor.execute(
                "INSERT INTO public.systemes_reperage (id, troncon_id, libelle, valid) VALUES (%s, %s, 'S A', true), (%s, %s, 'S B', true)",
                (cls.systeme_a, cls.troncon_a, cls.systeme_b, cls.troncon_b),
            )
            cls.cursor.execute(
                "INSERT INTO public.bornes_reperage (id, libelle, geometry, valid) VALUES (%s, 'B A', ST_SetSRID(ST_Point(0, 0), 3950), true), (%s, 'B B', ST_SetSRID(ST_Point(0, 10), 3950), true)",
                (cls.borne_a, cls.borne_b),
            )
            cls.cursor.execute(
                "INSERT INTO public.link_troncons_bornes (troncon_id, borne_id) VALUES (%s, %s), (%s, %s)",
                (cls.troncon_a, cls.borne_a, cls.troncon_b, cls.borne_b),
            )
            cls.cursor.execute(
                "INSERT INTO public.link_systemes_reperage_bornes (id, systeme_reperage_id, borne_id, valeur_pr, ordre_source, valid) VALUES (%s, %s, %s, 0, 0, true), (%s, %s, %s, 1000, 0, true)",
                (uuid4(), cls.systeme_a, cls.borne_a, uuid4(), cls.systeme_b, cls.borne_b),
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

    def add_disorder(self, *, geometry="POINT(20 0)", links=("a",)):
        desordre_id = uuid4()
        self.cursor.execute(
            "INSERT INTO public.desordres (id, designation, geometry, valid) VALUES (%s, 'Test lot 3', ST_GeomFromText(%s, 3950), true)",
            (desordre_id, geometry),
        )
        for link in links:
            troncon = self.troncon_a if link == "a" else self.troncon_b
            self.cursor.execute(
                "INSERT INTO public.link_desordres_troncons (desordre_id, troncon_id) VALUES (%s, %s)",
                (desordre_id, troncon),
            )
        return desordre_id

    def add_location(self, desordre_id, *, second=False, valid=True):
        troncon = self.troncon_b if second else self.troncon_a
        systeme = self.systeme_b if second else self.systeme_a
        borne = self.borne_b if second else self.borne_a
        location_id = uuid4()
        self.cursor.execute(
            """
            INSERT INTO public.desordre_localisations_reperage (
                id, desordre_id, troncon_id, systeme_reperage_id,
                borne_debut_id, distance_debut_m, position_debut_relative,
                pr_debut_source, position_debut_source,
                mode_saisie_source, politique_autorite, qualite, valid
            ) VALUES (
                %s, %s, %s, %s, %s, 20, 'APRES_BORNE',
                20, ST_SetSRID(ST_Point(20, 0), 3950),
                'IMPORT', 'MANUELLE', 'OK', %s
            )
            """,
            (location_id, desordre_id, troncon, systeme, borne, valid),
        )
        return location_id

    def assert_fk_failure(self, statement, params):
        self.cursor.execute("SAVEPOINT expected_fk_failure")
        try:
            with self.assertRaises(self.psycopg.errors.ForeignKeyViolation):
                self.cursor.execute(statement, params)
        finally:
            self.cursor.execute("ROLLBACK TO SAVEPOINT expected_fk_failure")

    def test_zero_one_and_two_locations_are_structurally_supported(self):
        empty = self.add_disorder()
        one = self.add_disorder()
        self.add_location(one)
        two = self.add_disorder(links=("a", "b"))
        self.add_location(two)
        self.add_location(two, second=True)
        self.cursor.execute(
            "SELECT desordre_id, count(*) AS count FROM public.desordre_localisations_reperage WHERE desordre_id IN (%s, %s, %s) GROUP BY desordre_id",
            (empty, one, two),
        )
        counts = {row["desordre_id"]: row["count"] for row in self.cursor.fetchall()}
        self.assertNotIn(empty, counts)
        self.assertEqual(counts[one], 1)
        self.assertEqual(counts[two], 2)

    def test_generated_offset_trace_valid_and_geometry_are_preserved(self):
        desordre = self.add_disorder(geometry="LINESTRING(5 0, 25 0)")
        location = self.add_location(desordre, valid=False)
        self.cursor.execute(
            """
            SELECT l.offset_debut_m, l.pr_debut_source,
                   ST_AsText(l.position_debut_source) AS source_position,
                   l.valid, ST_AsText(d.geometry) AS geometry
            FROM public.desordre_localisations_reperage AS l
            JOIN public.desordres AS d ON d.id = l.desordre_id
            WHERE l.id = %s
            """,
            (location,),
        )
        row = self.cursor.fetchone()
        self.assertEqual(row["offset_debut_m"], 20)
        self.assertEqual(row["pr_debut_source"], 20)
        self.assertEqual(row["source_position"], "POINT(20 0)")
        self.assertFalse(row["valid"])
        self.assertEqual(row["geometry"], "LINESTRING(5 0,25 0)")

    def test_inconsistent_system_borne_and_troncon_are_rejected(self):
        desordre = self.add_disorder(links=("a", "b"))
        statement = """
            INSERT INTO public.desordre_localisations_reperage (
                desordre_id, troncon_id, systeme_reperage_id,
                borne_debut_id, distance_debut_m, position_debut_relative,
                mode_saisie_source, politique_autorite, qualite, valid
            ) VALUES (%s, %s, %s, %s, 1, 'APRES_BORNE', 'IMPORT', 'MANUELLE', 'OK', true)
        """
        self.assert_fk_failure(
            statement,
            (desordre, self.troncon_a, self.systeme_a, self.borne_b),
        )
        self.assert_fk_failure(
            statement,
            (desordre, self.troncon_a, self.systeme_b, self.borne_b),
        )

    def test_parent_delete_is_restricted(self):
        desordre = self.add_disorder()
        self.add_location(desordre)
        self.assert_fk_failure(
            "DELETE FROM public.desordres WHERE id = %s",
            (desordre,),
        )

    def test_lot2_round_trip_remains_unchanged(self):
        self.cursor.execute(
            "SELECT statut, offset_borne_m, ST_X(point_projete) AS x FROM public.xy_vers_reperage(%s, %s, ST_SetSRID(ST_Point(20, 3), 3950))",
            (self.troncon_a, self.systeme_a),
        )
        direct = self.cursor.fetchone()
        self.assertEqual(direct["statut"], "OK")
        self.cursor.execute(
            "SELECT statut, ST_X(point_xy) AS x FROM public.borne_offset_vers_xy(%s, %s, %s, %s)",
            (self.troncon_a, self.systeme_a, self.borne_a, direct["offset_borne_m"]),
        )
        inverse = self.cursor.fetchone()
        self.assertEqual(inverse["statut"], "OK")
        self.assertAlmostEqual(inverse["x"], direct["x"], places=8)


if __name__ == "__main__":
    unittest.main()
