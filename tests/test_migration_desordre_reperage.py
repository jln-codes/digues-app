from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import unittest
from uuid import UUID, uuid4

from dotenv import load_dotenv

from sirs_postgre.target import PostgreSQLConfig

from sirs_postgre.migration.desordre_reperage import (
    ENGINE_VALIDATION_BATCH_SIZE,
    DesordreLocalisationReperageRow,
    PreparedDesordreReperageMigration,
    _distance_and_position,
    _engine_qualities_batch,
    _engine_quality,
    insert_prepared_desordre_reperage,
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
                True,
            ),
            LinkSystemeReperageBorneRow(
                UUID("00000000-0000-0000-0000-000000000042"),
                SYSTEME_A,
                BORNE_B,
                Decimal("100"),
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


class LegacyEngineCursor:
    def __init__(self, result):
        self.result = result
        self.execute_count = 0

    def execute(self, _statement, _params):
        self.execute_count += 1

    def fetchone(self):
        return self.result


class BatchEngineCursor:
    PARAMS_PER_ROW = 12

    def __init__(self, results_by_id):
        self.results_by_id = results_by_id
        self.execute_calls = []
        self.current_results = []
        self.inserted_batches = []

    def execute(self, statement, params):
        self.execute_calls.append((statement, params))
        ids = [
            params[index + 1]
            for index in range(0, len(params), self.PARAMS_PER_ROW)
        ]
        self.current_results = []
        for row_id in ids:
            result = self.results_by_id[row_id]
            if result is None:
                self.current_results.append((row_id, False, *([None] * 18)))
            else:
                self.current_results.append((row_id, True, *result))

    def fetchall(self):
        return list(self.current_results)

    def executemany(self, statement, rows):
        self.inserted_batches.append((statement, list(rows)))


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


class DesordreReperageBatchValidationTest(unittest.TestCase):
    def setUp(self):
        prepared = prepare_desordre_reperage_migration(
            [complete_document()],
            desordre_ids={DESORDRE},
            troncon_ids={TRONCON_A, TRONCON_B},
            reperage=reperage_fixture(),
        )
        self.row = prepared.localisations[0]

    def engine_result(self, *, status_index=None, status=None, offset_delta=0):
        result = [
            "OK",
            "OK",
            self.row.borne_debut_id,
            self.row.offset_debut_m + offset_delta,
            self.row.pr_debut_source,
            "OK",
            "OK",
            self.row.borne_fin_id,
            self.row.offset_fin_m,
            self.row.pr_fin_source,
            "OK",
            "OK",
            self.row.pr_debut_source,
            0.0,
            "OK",
            "OK",
            self.row.pr_fin_source,
            0.0,
        ]
        if status_index is not None:
            result[status_index] = status
        return tuple(result)

    def test_batch_matches_historical_quality_and_diagnostics(self):
        cases = {
            "OK": self.engine_result(),
            "CONFLIT_SYSTEME": self.engine_result(
                status_index=0,
                status="CONFLIT_SYSTEME",
            ),
            "REFERENCE_ABSENTE": self.engine_result(
                status_index=5,
                status="REFERENCE_ABSENTE",
            ),
            "AMBIGU": self.engine_result(status_index=10, status="AMBIGU"),
            "INCOHERENT": self.engine_result(offset_delta=1.0),
        }
        for expected_quality, result in cases.items():
            with self.subTest(quality=expected_quality):
                legacy_cursor = LegacyEngineCursor(result)
                historical = _engine_quality(legacy_cursor, self.row, None)
                batch_cursor = BatchEngineCursor({self.row.id: result})
                batched = _engine_qualities_batch(
                    batch_cursor,
                    [self.row],
                    None,
                )[self.row.id]

                self.assertEqual(historical, batched)
                self.assertEqual(batched[0], expected_quality)
                self.assertEqual(legacy_cursor.execute_count, 1)
                self.assertEqual(len(batch_cursor.execute_calls), 1)

    def test_non_controlled_row_keeps_quality_and_diagnostic_without_sql(self):
        diagnostic = {"preparation": ["REFERENCE_ABSENTE:borneDebutId"]}
        row = replace(
            self.row,
            qualite="REFERENCE_ABSENTE",
            diagnostic_conversion=diagnostic,
        )
        legacy_cursor = LegacyEngineCursor(None)
        historical = _engine_quality(legacy_cursor, row, None)
        batch_cursor = BatchEngineCursor({})

        batched = _engine_qualities_batch(batch_cursor, [row], None)[row.id]

        self.assertEqual(historical, ("REFERENCE_ABSENTE", diagnostic))
        self.assertEqual(batched, historical)
        self.assertEqual(legacy_cursor.execute_count, 0)
        self.assertEqual(batch_cursor.execute_calls, [])

    def test_non_controlled_row_is_excluded_from_a_mixed_batch(self):
        diagnostic = {"preparation": ["INCOMPLETE:prDebut"]}
        non_controlled = replace(
            self.row,
            id=UUID(int=500),
            qualite="INCOMPLETE",
            diagnostic_conversion=diagnostic,
        )
        controlled = replace(self.row, id=UUID(int=501))
        result = self.engine_result()
        cursor = BatchEngineCursor({controlled.id: result})

        qualities = _engine_qualities_batch(
            cursor,
            [non_controlled, controlled],
            None,
        )

        self.assertEqual(qualities[non_controlled.id], ("INCOMPLETE", diagnostic))
        self.assertEqual(len(cursor.execute_calls), 1)
        params = cursor.execute_calls[0][1]
        self.assertIn(controlled.id, params)
        self.assertNotIn(non_controlled.id, params)

    def test_missing_engine_result_matches_historical_diagnostic(self):
        historical = _engine_quality(LegacyEngineCursor(None), self.row, None)
        cursor = BatchEngineCursor({self.row.id: None})

        batched = _engine_qualities_batch(cursor, [self.row], None)[self.row.id]

        self.assertEqual(historical, batched)
        self.assertEqual(
            batched,
            ("INCOHERENT", {"cause": "MOTEUR_SANS_RESULTAT"}),
        )

    def test_insert_uses_one_validation_query_for_many_rows(self):
        rows = tuple(
            replace(
                self.row,
                id=UUID(int=100 + index),
                desordre_id=UUID(int=1_000 + index),
            )
            for index in range(25)
        )
        result = self.engine_result()
        cursor = BatchEngineCursor({row.id: result for row in rows})
        prepared = PreparedDesordreReperageMigration(
            localisations=rows,
            source_complete_count=len(rows),
            source_partial_count=0,
            source_without_reperage_count=0,
            warnings=(),
        )

        insert_prepared_desordre_reperage(cursor, prepared)

        self.assertEqual(len(cursor.execute_calls), 1)
        statement, params = cursor.execute_calls[0]
        self.assertIn("WITH input_rows", statement)
        self.assertEqual(statement.count("JOIN LATERAL"), 4)
        self.assertEqual(len(params), 12 * len(rows))
        self.assertEqual(len(cursor.inserted_batches), 1)
        self.assertEqual(len(cursor.inserted_batches[0][1]), len(rows))

    def test_validation_query_count_is_constant_below_large_batch_limit(self):
        self.assertGreater(ENGINE_VALIDATION_BATCH_SIZE, 100)
        result = self.engine_result()
        counts = []
        for row_count in (1, 100):
            rows = [
                replace(self.row, id=UUID(int=10_000 + index))
                for index in range(row_count)
            ]
            cursor = BatchEngineCursor({row.id: result for row in rows})
            _engine_qualities_batch(cursor, rows, None)
            counts.append(len(cursor.execute_calls))

        self.assertEqual(counts, [1, 1])


class DesordreReperagePostGISIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import psycopg
            from psycopg.rows import dict_row, tuple_row

            load_dotenv(
                Path(__file__).resolve().parents[1] / "config.env",
                override=False,
            )
            cls.psycopg = psycopg
            cls.tuple_row = staticmethod(tuple_row)
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
            cls.borne_a_fin = uuid4()
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
                "INSERT INTO public.bornes_reperage (id, libelle, geometry, valid) VALUES (%s, 'B A', ST_SetSRID(ST_Point(0, 0), 3950), true), (%s, 'B A fin', ST_SetSRID(ST_Point(100, 0), 3950), true), (%s, 'B B', ST_SetSRID(ST_Point(0, 10), 3950), true)",
                (cls.borne_a, cls.borne_a_fin, cls.borne_b),
            )
            cls.cursor.execute(
                "INSERT INTO public.link_troncons_bornes (troncon_id, borne_id) VALUES (%s, %s), (%s, %s), (%s, %s)",
                (cls.troncon_a, cls.borne_a, cls.troncon_a, cls.borne_a_fin, cls.troncon_b, cls.borne_b),
            )
            cls.cursor.execute(
                "INSERT INTO public.link_systemes_reperage_bornes (id, systeme_reperage_id, borne_id, valeur_pr, valid) VALUES (%s, %s, %s, 0, true), (%s, %s, %s, 100, true), (%s, %s, %s, 1000, true)",
                (uuid4(), cls.systeme_a, cls.borne_a, uuid4(), cls.systeme_a, cls.borne_a_fin, uuid4(), cls.systeme_b, cls.borne_b),
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

    def test_batch_engine_query_matches_real_legacy_queries(self):
        def location(offset):
            return DesordreLocalisationReperageRow(
                id=uuid4(),
                desordre_id=uuid4(),
                troncon_id=self.troncon_a,
                systeme_reperage_id=self.systeme_a,
                borne_debut_id=self.borne_a,
                offset_debut_m=float(offset),
                borne_fin_id=self.borne_a,
                offset_fin_m=float(offset + 5),
                pr_debut_source=Decimal(offset),
                pr_fin_source=Decimal(offset + 5),
                position_debut_source_wkt=f"POINT({offset} 0)",
                position_fin_source_wkt=f"POINT({offset + 5} 0)",
                mode_saisie_source="IMPORT",
                politique_autorite="MANUELLE",
                qualite="A_CONTROLER",
                valid=True,
                source_document_id=str(uuid4()),
                trace_source={},
                diagnostic_conversion={"preparation": []},
            )

        rows = (location(20), location(40))
        with self.connection.cursor(row_factory=self.tuple_row) as cursor:
            historical = {
                row.id: _engine_quality(cursor, row, None) for row in rows
            }
            batched = _engine_qualities_batch(cursor, rows, None)

        self.assertEqual(batched, historical)


if __name__ == "__main__":
    unittest.main()
