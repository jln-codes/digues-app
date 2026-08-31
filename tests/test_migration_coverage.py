import tempfile
import unittest
from pathlib import Path

from sirs_postgre.migration.coverage import diagnose_documents, rule_for


class CoverageDiagnosticTest(unittest.TestCase):
    def test_unknown_class_and_field_are_reported_and_markdown_is_written(self):
        documents = [
            {
                "_id": "00000000000000000000000000000001",
                "@class": "fr.sirs.core.model.SystemeEndiguement",
                "libelle": "Système",
                "valid": True,
                "nouveauChamp": "à analyser",
            },
            {
                "_id": "00000000000000000000000000000002",
                "@class": "org.example.ClasseFuture",
                "champFutur": 1,
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audits" / "bilan.md"
            result = diagnose_documents(documents, output_path=path)
            self.assertTrue(path.is_file())
            self.assertTrue(result.anomalies_json_path.is_file())
            self.assertTrue(result.anomalies_csv_path.is_file())
            report = path.read_text(encoding="utf-8")
        self.assertEqual(result.total_documents, 2)
        self.assertEqual(result.total_classes, 2)
        self.assertEqual(result.status_class_counts["MIGREE"], 1)
        self.assertEqual(result.status_class_counts["NON_MIGREE"], 1)
        self.assertEqual(result.non_migrated_business_objects, 1)
        self.assertIn("ClasseFuture", report)
        self.assertIn("NON_MIGREE", report)
        self.assertIn("nouveauChamp", report)
        self.assertIn("Champs non analysés/non migrés", report)
        self.assertIn("Registre détaillé des anomalies", report)
        self.assertIn("Anomalies de données actives (`DATA`)", report)
        self.assertIn("Anomalies de couverture actives (`COVERAGE`)", report)
        self.assertIn("Décisions de migration actives (`MIGRATION_DECISION`)", report)
        self.assertGreaterEqual(result.unanalysed_field_pairs, 2)

    def test_known_deferred_and_technical_classes_are_explicitly_classified(self):
        for class_name in (
            "Prestation",
            "GlobalPrestation",
            "TalusDigue",
            "RapportEtude",
            "Organisme",
            "Contact",
        ):
            self.assertEqual(rule_for(class_name).status, "NON_MIGREE")
        for class_name in (
            "PositionDocument",
            "BookMark",
            "SQLQuery",
            "ModeleRapport",
            "Utilisateur",
        ):
            self.assertEqual(rule_for(class_name).status, "TECHNIQUE_IGNORE")

    def test_reperage_core_and_desordre_prototype_are_covered(self):
        self.assertEqual(rule_for("BorneDigue").status, "MIGREE")
        systeme = rule_for("SystemeReperage")
        self.assertEqual(systeme.status, "MIGREE")
        self.assertIn("systemeReperageBornes", systeme.consumed_fields)
        association = rule_for("SystemeReperageBorne")
        self.assertEqual(association.status, "MIGREE")
        self.assertIn("valeurPR", association.consumed_fields)
        troncon = rule_for("TronconDigue")
        self.assertIn("borneIds", troncon.consumed_fields)
        self.assertIn("systemeRepDefautId", troncon.consumed_fields)
        for field in (
            "systemeRepId",
            "borneDebutId",
            "borneFinId",
            "borne_debut_distance",
            "borne_fin_distance",
            "prDebut",
            "prFin",
        ):
            self.assertIn(field, rule_for("Desordre").consumed_fields)
            self.assertNotIn(field, rule_for("Desordre").ignored_fields)
            self.assertIn(
                field,
                rule_for("OuvrageFranchissement").ignored_fields,
            )

    def test_technical_access_is_migrated_without_required_parent_or_inference(self):
        rule = rule_for("CheminAccesDependance")
        self.assertEqual(rule.status, "MIGREE")
        self.assertIn("cheminements", rule.destination)
        self.assertIn("geometry", rule.consumed_fields)
        self.assertIn("accès technique", rule.comment.lower())
        self.assertNotIn("parent aménagement", rule.comment)

    def test_cheminement_prestation_relations_remain_explicitly_deferred(self):
        for class_name in ("OuvrageFranchissement", "VoieAcces", "VoieDigue"):
            rule = rule_for(class_name)
            self.assertIn("cheminements", rule.destination)
            self.assertNotIn("prestationIds", rule.consumed_fields)
            self.assertIn("prestations différées", rule.comment)

    def test_prestations_are_deferred_and_a_truly_new_class_stays_unknown(self):
        documents = [
            {
                "_id": f"id-{class_name}",
                "@class": f"fr.sirs.core.model.{class_name}",
            }
            for class_name in ("Prestation", "GlobalPrestation", "FutureClass")
        ]
        with tempfile.TemporaryDirectory() as directory:
            result = diagnose_documents(
                documents,
                output_path=Path(directory) / "bilan.md",
                source_database="test_source",
            )
        by_class = {
            anomaly.source_class: anomaly
            for anomaly in result.anomaly_register.active
        }
        for class_name in ("Prestation", "GlobalPrestation"):
            self.assertEqual(by_class[class_name].category, "DEFERRED_FEATURE")
            self.assertEqual(by_class[class_name].severity, "WARNING")
            self.assertEqual(
                by_class[class_name].correction_location, "NOT_APPLICABLE"
            )
        self.assertEqual(by_class["FutureClass"].category, "UNKNOWN_CLASS")
        self.assertEqual(by_class["FutureClass"].severity, "ERROR")

    def test_unknown_reference_is_distinguished_from_unknown_business_class(self):
        with tempfile.TemporaryDirectory() as directory:
            result = diagnose_documents(
                [
                    {
                        "_id": "RefFuture:1",
                        "@class": "fr.sirs.core.model.RefFuture",
                        "libelle": "Valeur",
                        "valid": True,
                    }
                ],
                output_path=Path(directory) / "bilan.md",
            )
        self.assertEqual(result.status_class_counts["REFERENTIEL_IGNORE"], 1)
        self.assertEqual(result.status_class_counts["NON_MIGREE"], 0)


if __name__ == "__main__":
    unittest.main()
