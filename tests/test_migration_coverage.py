import tempfile
import unittest
from pathlib import Path

from sirs_postgre.migration.coverage import diagnose_documents


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
        self.assertGreaterEqual(result.unanalysed_field_pairs, 2)

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
