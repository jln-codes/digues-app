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
        return ("3.4.2", "1.3")

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
                "systemes",
                "digues",
                "troncons",
                "ref_categories_desordre",
                "ref_types_desordre",
                "ref_urgences",
                "desordres",
                "link_desordres_troncons",
                "observations",
                "photos",
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
        self.assertTrue(
            set(created).isdisjoint(
                {
                    "systeme_endiguement",
                    "digue",
                    "troncon",
                    "desordre",
                    "link_desordre_troncon",
                    "observation",
                    "photo",
                }
            )
        )

    def test_business_identifiers_are_uuid_without_serial_types(self):
        for table in (
            "systemes",
            "digues",
            "troncons",
            "desordres",
            "link_desordres_troncons",
            "observations",
            "photos",
        ):
            with self.subTest(table=table):
                self.assertIn("id uuid primary key", normalized(TABLE_DEFINITIONS[table]))
        ddl = normalized(" ".join(SCHEMA_DDL))
        self.assertNotIn("serial", ddl)

    def test_simple_uuid_primary_keys_default_to_generated_uuid(self):
        for table in (
            "systemes",
            "digues",
            "troncons",
            "desordres",
            "link_desordres_troncons",
            "observations",
            "photos",
        ):
            with self.subTest(table=table):
                self.assertIn(
                    "id uuid primary key default gen_random_uuid()",
                    normalized(TABLE_DEFINITIONS[table]),
                )

    def test_foreign_key_columns_are_uuid(self):
        expected_uuid_columns = {
            "digues": ("systeme_endiguement_id",),
            "troncons": ("digue_id",),
            "link_desordres_troncons": ("desordre_id", "troncon_id"),
            "observations": ("desordre_id",),
            "photos": ("observation_id",),
        }
        for table, columns in expected_uuid_columns.items():
            statement = normalized(TABLE_DEFINITIONS[table])
            for column in columns:
                with self.subTest(table=table, column=column):
                    self.assertIn(f"{column} uuid", statement)

    def test_reference_primary_and_foreign_keys_are_text(self):
        for table in (
            "ref_categories_desordre",
            "ref_types_desordre",
            "ref_urgences",
        ):
            with self.subTest(table=table):
                self.assertIn("id text primary key", normalized(TABLE_DEFINITIONS[table]))
                self.assertNotIn("gen_random_uuid", normalized(TABLE_DEFINITIONS[table]))
        self.assertIn(
            "categorie_id text not null",
            normalized(TABLE_DEFINITIONS["ref_types_desordre"]),
        )
        self.assertIn(
            "type_desordre_id text null",
            normalized(TABLE_DEFINITIONS["desordres"]),
        )
        self.assertIn(
            "urgence_id text null",
            normalized(TABLE_DEFINITIONS["observations"]),
        )

    def test_foreign_keys_follow_the_requested_relationships(self):
        expected_references = {
            "ref_types_desordre": (
                "foreign key (categorie_id) "
                "references public.ref_categories_desordre (id)"
            ),
            "digues": (
                "foreign key (systeme_endiguement_id) "
                "references public.systemes (id)"
            ),
            "troncons": "foreign key (digue_id) references public.digues (id)",
            "link_desordres_troncons": (
                "foreign key (desordre_id) references public.desordres (id)",
                "foreign key (troncon_id) references public.troncons (id)",
            ),
            "observations": (
                "foreign key (desordre_id) references public.desordres (id)",
                "foreign key (urgence_id) references public.ref_urgences (id)",
            ),
            "desordres": (
                "foreign key (type_desordre_id) "
                "references public.ref_types_desordre (id)"
            ),
            "photos": (
                "foreign key (observation_id) references public.observations (id)"
            ),
        }
        for table, references in expected_references.items():
            if isinstance(references, str):
                references = (references,)
            statement = normalized(TABLE_DEFINITIONS[table])
            for reference in references:
                with self.subTest(table=table, reference=reference):
                    self.assertIn(reference, statement)

    def test_constraints_follow_plural_table_names(self):
        expected_constraints = {
            "ref_types_desordre": "ref_types_desordre_categorie_fk",
            "digues": "digues_systemes_fk",
            "troncons": "troncons_digues_fk",
            "link_desordres_troncons": (
                "link_desordres_troncons_desordres_fk",
                "link_desordres_troncons_troncons_fk",
                "link_desordres_troncons_unique",
            ),
            "desordres": "desordres_type_desordre_fk",
            "observations": (
                "observations_desordres_fk",
                "observations_urgence_fk",
            ),
            "photos": "photos_observations_fk",
        }
        for table, constraints in expected_constraints.items():
            if isinstance(constraints, str):
                constraints = (constraints,)
            statement = normalized(TABLE_DEFINITIONS[table])
            for constraint in constraints:
                with self.subTest(table=table, constraint=constraint):
                    self.assertIn(f"constraint {constraint}", statement)

    def test_link_table_has_generated_primary_key_and_unique_business_pair(self):
        statement = normalized(TABLE_DEFINITIONS["link_desordres_troncons"])
        self.assertIn(
            "id uuid primary key default gen_random_uuid()",
            statement,
        )
        self.assertIn(
            "constraint link_desordres_troncons_unique "
            "unique (desordre_id, troncon_id)",
            statement,
        )
        self.assertNotIn("primary key (desordre_id, troncon_id)", statement)

    def test_geometries_keep_srid_and_desordre_is_generic(self):
        troncon = normalized(TABLE_DEFINITIONS["troncons"])
        desordre = normalized(TABLE_DEFINITIONS["desordres"])
        self.assertIn("geometry geometry(linestring, 3950)", troncon)
        self.assertIn("geometry geometry(geometry, 3950)", desordre)
        self.assertNotIn("geometry geometry(linestring, 3950)", desordre)

    def test_observation_designation_is_nullable_text(self):
        observation = normalized(TABLE_DEFINITIONS["observations"])
        self.assertIn("designation text null", observation)
        for excluded_field in (
            "observateurid",
            "suiteapporterid",
            "lastupdateauthor",
        ):
            self.assertNotIn(excluded_field, observation)

    def test_desordres_does_not_store_category(self):
        desordres = normalized(TABLE_DEFINITIONS["desordres"])
        self.assertNotIn("categorie_desordre_id", desordres)

    def test_initialization_uses_one_non_autocommit_connection(self):
        connection = FakeSchemaConnection()
        calls = []

        def connector(**kwargs):
            calls.append(kwargs)
            return connection

        status = initialize_schema(PostgreSQLConfig(), connector=connector)
        self.assertIs(calls[0]["autocommit"], False)
        self.assertEqual(status.tables, EXPECTED_TABLES)
        self.assertEqual(status.pgcrypto_version, "1.3")
        executed_ddl = [query for query, _params in connection.cursor_instance.executed]
        for statement in SCHEMA_DDL:
            self.assertIn(statement, executed_ddl)


if __name__ == "__main__":
    unittest.main()
