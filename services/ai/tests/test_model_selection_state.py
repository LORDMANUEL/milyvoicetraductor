import json
import tempfile
import unittest
from pathlib import Path

from mily_ai.models import HuggingFacePackInstaller, ModelCatalog


class ModelSelectionStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.catalog = ModelCatalog(self.root)
        self.installer = HuggingFacePackInstaller(self.catalog)
        for pack_id, version in (("lite", "1"), ("quality", "2")):
            pack = self.catalog.packs_dir / pack_id / version
            pack.mkdir(parents=True, exist_ok=True)
            (pack / "pack.json").write_text(
                json.dumps({"id": pack_id, "version": version, "files": {}}),
                encoding="utf-8",
            )

    def tearDown(self):
        self.temp.cleanup()

    def test_activate_selection_persists_the_measured_backend(self):
        self.installer.activate_selection("lite", "1", "cpu")
        self.assertEqual(self.catalog._state()["active"], "lite@1")
        self.assertEqual(self.catalog.active_backend(), "cpu")

        self.installer.activate_selection("lite", "1", "cuda")
        self.assertEqual(self.catalog._state()["active"], "lite@1")
        self.assertEqual(self.catalog.active_backend(), "cuda")

    def test_old_state_without_backend_migrates_to_auto(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self.catalog.state_path.write_text(
            json.dumps({"schemaVersion": 2, "active": "lite@1", "previous": None}),
            encoding="utf-8",
        )
        self.assertEqual(self.catalog.active_backend(), "auto")

    def test_rollback_restores_pack_and_backend_together(self):
        self.installer.activate_selection("lite", "1", "cpu")
        self.installer.activate_selection("quality", "2", "cuda")

        restored = self.installer.rollback()

        self.assertEqual((restored.id, restored.version), ("lite", "1"))
        self.assertEqual(self.catalog.active_backend(), "cpu")
        state = self.catalog._state()
        self.assertEqual(state["previous"], "quality@2")
        self.assertEqual(state["previousBackend"], "cuda")

    def test_unknown_backend_is_normalized_to_auto(self):
        self.installer.activate_selection("lite", "1", "invented")
        self.assertEqual(self.catalog.active_backend(), "auto")


if __name__ == "__main__":
    unittest.main()
