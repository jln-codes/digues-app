import json
import tempfile
import unittest
from pathlib import Path

from sirs_postgre.model_manifest import (
    DEFAULT_ECORE_PATH,
    DEFAULT_LABELS_PATH,
    build_manifest,
    sha256_file,
    write_manifest,
)


CONTROL_CLASSES = {
    "SystemeEndiguement",
    "Digue",
    "TronconDigue",
    "Desordre",
    "Observation",
    "Photo",
}


def field_by_name(fields, name):
    return next(field for field in fields if field["name"] == name)


class SIRSModelManifestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = build_manifest()

    def test_reads_versioned_ecore_snapshot(self):
        self.assertTrue(DEFAULT_ECORE_PATH.is_file())
        self.assertEqual(self.manifest["source"]["ecore"], DEFAULT_ECORE_PATH.as_posix())
        self.assertEqual(
            self.manifest["source"]["labels"], DEFAULT_LABELS_PATH.as_posix()
        )

    def test_control_classes_are_extracted(self):
        self.assertTrue(CONTROL_CLASSES.issubset(self.manifest["classes"]))

    def test_extracts_simple_attribute_with_label(self):
        fields = self.manifest["classes"]["SystemeEndiguement"]["declared_fields"]
        field = field_by_name(fields, "populationProtegee")
        self.assertEqual(field["kind"], "ATTRIBUTE")
        self.assertEqual(field["type"], "EInt")
        self.assertEqual(field["label"], "Population protégée")
        self.assertEqual(field["declared_in"], "SystemeEndiguement")
        self.assertFalse(field["inherited"])

    def test_extracts_reference_target(self):
        fields = self.manifest["classes"]["SystemeEndiguement"]["declared_fields"]
        field = field_by_name(fields, "gestionnaireDecretId")
        self.assertEqual(field["kind"], "REFERENCE")
        self.assertEqual(field["type"], "Organisme")
        self.assertEqual(field["label"], "Collectivité compétente")

    def test_resolves_simple_super_type(self):
        digue = self.manifest["classes"]["Digue"]
        self.assertEqual(digue["super_types"], ["TronconLitAssociable"])

    def test_resolves_multiple_super_types(self):
        desordre = self.manifest["classes"]["Desordre"]
        self.assertEqual(
            desordre["super_types"], ["Objet", "IDesordre", "AvecPrestations"]
        )
        self.assertGreater(len(desordre["effective_fields"]), len(desordre["declared_fields"]))

    def test_inherited_fields_are_effective_but_not_declared(self):
        desordre = self.manifest["classes"]["Desordre"]
        declared_names = {field["name"] for field in desordre["declared_fields"]}
        effective = field_by_name(desordre["effective_fields"], "positionDebut")
        self.assertNotIn("positionDebut", declared_names)
        self.assertEqual(effective["declared_in"], "Positionable")
        self.assertTrue(effective["inherited"])

    def test_unbounded_upper_bound_is_many(self):
        fields = self.manifest["classes"]["TronconDigue"]["declared_fields"]
        field = field_by_name(fields, "borneIds")
        self.assertEqual(field["upper_bound"], -1)
        self.assertEqual(field["upper_bound_raw"], "-1")
        self.assertTrue(field["many"])

    def test_effective_fields_have_no_duplicates(self):
        for class_name, entry in self.manifest["classes"].items():
            names = [field["name"] for field in entry["effective_fields"]]
            with self.subTest(class_name=class_name):
                self.assertEqual(len(names), len(set(names)))

    def test_generation_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.json"
            second = Path(directory) / "second.json"
            write_manifest(first)
            write_manifest(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_ecore_sha256_is_recorded(self):
        self.assertEqual(
            self.manifest["source"]["ecore_sha256"],
            sha256_file(DEFAULT_ECORE_PATH),
        )

    def test_label_metadata_is_not_structural_field(self):
        systeme = self.manifest["classes"]["SystemeEndiguement"]
        declared_names = {field["name"] for field in systeme["declared_fields"]}
        self.assertNotIn("class", declared_names)
        self.assertNotIn("classPlural", declared_names)
        self.assertNotIn("classAbrege", declared_names)
        self.assertEqual(systeme["class_labels"]["class"], "Systeme d'Endiguement")

    def test_written_manifest_is_valid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "manifest.json"
            write_manifest(output)
            decoded = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(decoded["model_version"], "2.55")


if __name__ == "__main__":
    unittest.main()
