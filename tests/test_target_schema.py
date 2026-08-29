import re
import unittest

from sirs_postgre.target.database import PostgreSQLConfig, initialize_schema
from sirs_postgre.target.schema import EXPECTED_TABLES, SCHEMA_DDL, TABLE_DEFINITIONS


def normalized(statement):
    return " ".join(statement.split()).lower()


class FakeSchemaCursor:
    def __init__(self):
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        self.executed.append((str(query), params))

    def fetchone(self):
        return ("3.4.2",)

    def fetchall(self):
        return [(table,) for table in EXPECTED_TABLES]


class FakeSchemaConnection:
    def __init__(self):
        self.cursor_instance = FakeSchemaCursor()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.cursor_instance


class TargetSchemaTest(unittest.TestCase):
    def test_defines_exactly_the_requested_tables(self):
        self.assertEqual(
            EXPECTED_TABLES,
            (
                "systeme_endiguement",
                "digue",
                "troncon",
                "desordre",
                "link_desordre_troncon",
                "observation",
                "photo",
            ),
        )
        created = [
            match
            for statement in SCHEMA_DDL
            for match in re.findall(
                r"create table if not exists public\.([a-z_]+)",
                normalized(statement),
            )
        ]
        self.assertEqual(created, list(EXPECTED_TABLES))

    def test_business_identifiers_are_uuid_without_serial_types(self):
        for table in (
            "systeme_endiguement",
            "digue",
            "troncon",
            "desordre",
            "observation",
            "photo",
        ):
            with self.subTest(table=table):
                self.assertIn("id uuid primary key", normalized(TABLE_DEFINITIONS[table]))
        ddl = normalized(" ".join(SCHEMA_DDL))
        self.assertNotIn("serial", ddl)

    def test_foreign_key_columns_are_uuid(self):
        expected_uuid_columns = {
            "digue": ("systeme_endiguement_id",),
            "troncon": ("digue_id",),
            "link_desordre_troncon": ("desordre_id", "troncon_id"),
            "observation": ("desordre_id",),
            "photo": ("observation_id",),
        }
        for table, columns in expected_uuid_columns.items():
            statement = normalized(TABLE_DEFINITIONS[table])
            for column in columns:
                with self.subTest(table=table, column=column):
                    self.assertIn(f"{column} uuid", statement)

    def test_foreign_keys_follow_the_requested_relationships(self):
        expected_references = {
            "digue": (
                "foreign key (systeme_endiguement_id) "
                "references public.systeme_endiguement (id)"
            ),
            "troncon": "foreign key (digue_id) references public.digue (id)",
            "link_desordre_troncon": (
                "foreign key (desordre_id) references public.desordre (id)",
                "foreign key (troncon_id) references public.troncon (id)",
            ),
            "observation": (
                "foreign key (desordre_id) references public.desordre (id)"
            ),
            "photo": (
                "foreign key (observation_id) references public.observation (id)"
            ),
        }
        for table, references in expected_references.items():
            if isinstance(references, str):
                references = (references,)
            statement = normalized(TABLE_DEFINITIONS[table])
            for reference in references:
                with self.subTest(table=table, reference=reference):
                    self.assertIn(reference, statement)

    def test_link_table_has_composite_primary_key(self):
        statement = normalized(TABLE_DEFINITIONS["link_desordre_troncon"])
        self.assertIn("primary key (desordre_id, troncon_id)", statement)

    def test_geometries_keep_srid_and_desordre_is_generic(self):
        troncon = normalized(TABLE_DEFINITIONS["troncon"])
        desordre = normalized(TABLE_DEFINITIONS["desordre"])
        self.assertIn("geometry geometry(linestring, 3950)", troncon)
        self.assertIn("geometry geometry(geometry, 3950)", desordre)
        self.assertNotIn("geometry geometry(linestring, 3950)", desordre)

    def test_initialization_uses_one_non_autocommit_connection(self):
        connection = FakeSchemaConnection()
        calls = []

        def connector(**kwargs):
            calls.append(kwargs)
            return connection

        status = initialize_schema(PostgreSQLConfig(), connector=connector)
        self.assertIs(calls[0]["autocommit"], False)
        self.assertEqual(status.tables, EXPECTED_TABLES)
        executed_ddl = [query for query, _params in connection.cursor_instance.executed]
        for statement in SCHEMA_DDL:
            self.assertIn(statement, executed_ddl)


if __name__ == "__main__":
    unittest.main()
