import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from digues_app.migration.source_overrides import (
    SOURCE_OVERRIDES_PATH_ENV,
    SourceOverridesConfigurationError,
    get_source_overrides,
    load_source_overrides,
)


class SourceOverridesTest(unittest.TestCase):
    def write_fixture(self, directory: str) -> tuple[Path, str, str]:
        amenagement_id = UUID(int=201).hex
        vegetation_id = UUID(int=202).hex
        path = Path(directory) / "source-overrides.json"
        path.write_text(
            json.dumps(
                {
                    "sources": {
                        "Synthetic_Source": {
                            "amenagement_type_by_id": {
                                amenagement_id: "SYNTHETIC_TYPE"
                            },
                            "vegetation_geometry_source_by_id": {
                                vegetation_id: "explicitGeometry"
                            },
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        return path, amenagement_id, vegetation_id

    def test_missing_optional_file_returns_empty_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "absent.json"
            self.assertFalse(load_source_overrides(missing))
            self.assertFalse(
                get_source_overrides(
                    "synthetic_source", path=missing
                ).amenagement_type_by_id
            )

    def test_configured_file_loads_synthetic_overrides_case_insensitively(self):
        with tempfile.TemporaryDirectory() as directory:
            path, amenagement_id, vegetation_id = self.write_fixture(directory)
            with patch.dict(
                "os.environ", {SOURCE_OVERRIDES_PATH_ENV: str(path)}, clear=False
            ):
                overrides = get_source_overrides("SYNTHETIC_SOURCE")
            self.assertEqual(
                overrides.amenagement_type_by_id[amenagement_id], "SYNTHETIC_TYPE"
            )
            self.assertEqual(
                overrides.vegetation_geometry_source_by_id[vegetation_id],
                "explicitGeometry",
            )

    def test_present_invalid_file_is_rejected_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text('{"sources": []}', encoding="utf-8")
            with self.assertRaises(SourceOverridesConfigurationError):
                load_source_overrides(path)


if __name__ == "__main__":
    unittest.main()
