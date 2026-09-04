import csv
import json
import tempfile
import unittest
from pathlib import Path
from uuid import UUID

from digues_app.migration.anomalies import (
    collect_anomalies,
    write_anomalies_csv,
    write_anomalies_json,
)
from digues_app.migration.coverage import (
    build_field_inventory,
    load_model_manifest,
    rule_for,
)


class ModelCoverageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_model_manifest()

    def coverage_rows(self, documents, *class_names):
        inventory = build_field_inventory(documents, self.manifest)
        return [
            {
                "class": class_name,
                "total": 1,
                "status": rule_for(class_name).status,
                "destination": rule_for(class_name).destination,
                "comment": rule_for(class_name).comment,
                "known": class_name in {
                    "SystemeEndiguement",
                    "Digue",
                    "Desordre",
                    "Observation",
                    "Photo",
                    "Prestation",
                },
                "model_defined": class_name in self.manifest["classes"],
                "unanalysed": (),
                "field_inventory": inventory[class_name],
                "model_manifest": {
                    "model_version": self.manifest["model_version"],
                    "source_ecore_sha256": self.manifest["source"]["ecore_sha256"],
                },
            }
            for class_name in class_names
        ]

    def field_anomalies(self, documents, *class_names):
        anomalies = collect_anomalies(
            documents,
            source_database="test",
            coverage_rows=self.coverage_rows(documents, *class_names),
        )
        return {
            (item.source_class, item.source_field): item
            for item in anomalies
            if item.category in {"UNMIGRATED_FIELD", "UNKNOWN_OBSERVED_FIELD"}
        }

    def test_model_fields_are_audited_when_observed_or_absent(self):
        documents = [
            {
                "_id": UUID(int=1).hex,
                "@class": "fr.sirs.core.model.SystemeEndiguement",
                "libelle": "Système",
                "valid": True,
                "populationProtegee": 12,
            }
        ]
        anomalies = self.field_anomalies(documents, "SystemeEndiguement")
        observed = anomalies[("SystemeEndiguement", "populationProtegee")]
        absent = anomalies[("SystemeEndiguement", "niveauProtection")]
        self.assertTrue(observed.details["model_defined"])
        self.assertTrue(observed.details["observed_in_corpus"])
        self.assertEqual(observed.details["occurrence_count"], 1)
        self.assertFalse(absent.details["observed_in_corpus"])
        self.assertEqual(absent.details["occurrence_count"], 0)
        self.assertEqual(absent.details["coverage_status"], "UNMIGRATED")
        self.assertNotIn(("SystemeEndiguement", "libelle"), anomalies)
        self.assertNotIn(("SystemeEndiguement", "author"), anomalies)

    def test_relation_deferred_and_unknown_fields_do_not_create_false_unmigrated(self):
        documents = [
            {
                "_id": UUID(int=2).hex,
                "@class": "fr.sirs.core.model.Digue",
                "systemeEndiguementId": UUID(int=1).hex,
                "libelle": "Digue",
                "valid": True,
            },
            {
                "_id": UUID(int=3).hex,
                "@class": "fr.sirs.core.model.Desordre",
                "prestationIds": [],
                "champPlugin": "extension",
                "valid": True,
            },
        ]
        anomalies = self.field_anomalies(documents, "Digue", "Desordre")
        self.assertNotIn(("Digue", "systemeEndiguementId"), anomalies)
        self.assertNotIn(("Desordre", "prestationIds"), anomalies)
        unknown = anomalies[("Desordre", "champPlugin")]
        self.assertEqual(unknown.category, "UNKNOWN_OBSERVED_FIELD")
        self.assertFalse(unknown.details["model_defined"])

    def test_inherited_desordre_field_is_audited(self):
        documents = [
            {
                "_id": UUID(int=4).hex,
                "@class": "fr.sirs.core.model.Desordre",
                "valid": True,
            }
        ]
        anomaly = self.field_anomalies(documents, "Desordre")[("Desordre", "articleIds")]
        self.assertTrue(anomaly.details["model_defined"])
        self.assertTrue(anomaly.details["inherited"])
        self.assertEqual(anomaly.details["declared_in"], "IDesordre")

    def test_contained_observation_and_photo_are_inventoried(self):
        documents = [
            {
                "_id": UUID(int=5).hex,
                "@class": "fr.sirs.core.model.Desordre",
                "valid": True,
                "observations": [
                    {
                        "id": UUID(int=6).hex,
                        "date": "2026-01-01",
                        "valid": True,
                        "photos": [
                            {
                                "id": UUID(int=7).hex,
                                "chemin": "photo.jpg",
                                "date": "2026-01-01",
                                "valid": True,
                            }
                        ],
                    }
                ],
            }
        ]
        inventory = build_field_inventory(documents, self.manifest)
        observation_date = next(
            item for item in inventory["Observation"] if item["source_field"] == "date"
        )
        photo_path = next(
            item for item in inventory["Photo"] if item["source_field"] == "chemin"
        )
        self.assertFalse(self.manifest["classes"]["Observation"]["couchdb_document"])
        self.assertFalse(self.manifest["classes"]["Photo"]["couchdb_document"])
        self.assertEqual(observation_date["occurrence_count"], 1)
        self.assertEqual(photo_path["occurrence_count"], 1)
        anomalies = self.field_anomalies(documents, "Observation", "Photo")
        self.assertIn(("Observation", "suite"), anomalies)
        self.assertIn(("Photo", "photographeId"), anomalies)

    def test_fully_deferred_class_has_only_one_class_level_anomaly(self):
        documents = [
            {
                "_id": UUID(int=8).hex,
                "@class": "fr.sirs.core.model.Prestation",
                "valid": True,
            }
        ]
        anomalies = collect_anomalies(
            documents,
            source_database="test",
            coverage_rows=self.coverage_rows(documents, "Prestation"),
        )
        self.assertEqual(
            [item.category for item in anomalies if item.source_class == "Prestation"],
            ["DEFERRED_FEATURE"],
        )

    def test_registered_extension_absent_from_manifest_is_one_class_anomaly(self):
        documents = [
            {
                "_id": UUID(int=11).hex,
                "@class": "fr.sirs.core.model.ArbreVegetation",
                "designation": "Arbre",
                "valid": True,
            }
        ]
        row = self.coverage_rows(documents, "ArbreVegetation")[0]
        row["known"] = True
        anomalies = collect_anomalies(
            documents,
            source_database="test",
            coverage_rows=[row],
        )
        coverage = [
            item
            for item in anomalies
            if item.category
            in {"UNKNOWN_CLASS", "UNKNOWN_OBSERVED_FIELD", "UNMIGRATED_FIELD"}
        ]
        self.assertEqual(len(coverage), 1)
        self.assertEqual(coverage[0].category, "UNKNOWN_CLASS")

    def test_field_inventory_is_deterministic(self):
        documents = [
            {
                "_id": UUID(int=9).hex,
                "@class": "fr.sirs.core.model.SystemeEndiguement",
                "valid": True,
            }
        ]
        first_inventory = build_field_inventory(documents, self.manifest)
        second_inventory = build_field_inventory(documents, self.manifest)
        self.assertEqual(first_inventory, second_inventory)
        rows = self.coverage_rows(documents, "SystemeEndiguement")
        first_anomalies = collect_anomalies(
            documents, source_database="test", coverage_rows=rows
        )
        second_anomalies = collect_anomalies(
            documents, source_database="test", coverage_rows=rows
        )
        self.assertEqual(first_anomalies, second_anomalies)

    def test_field_metadata_remains_compatible_with_json_and_csv(self):
        documents = [
            {
                "_id": UUID(int=10).hex,
                "@class": "fr.sirs.core.model.SystemeEndiguement",
                "populationProtegee": 3,
                "valid": True,
            }
        ]
        anomaly = self.field_anomalies(documents, "SystemeEndiguement")[
            ("SystemeEndiguement", "populationProtegee")
        ]
        with tempfile.TemporaryDirectory() as directory:
            json_path = Path(directory) / "anomalies.json"
            csv_path = Path(directory) / "anomalies.csv"
            write_anomalies_json(json_path, [anomaly])
            write_anomalies_csv(csv_path, [anomaly])
            json_row = json.loads(json_path.read_text(encoding="utf-8"))[0]
            with csv_path.open(encoding="utf-8", newline="") as stream:
                csv_row = next(csv.DictReader(stream))
        self.assertEqual(json_row["source_field"], "populationProtegee")
        self.assertEqual(json_row["details"]["label"], "Population protégée")
        self.assertEqual(csv_row["source_field"], "populationProtegee")
        self.assertIn("Population protégée", csv_row["details"])
