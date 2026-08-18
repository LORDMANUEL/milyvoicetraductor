import errno
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from mily_ai.models import (
    HuggingFacePackInstaller,
    ModelCatalog,
    classify_model_exception,
)


class ModelManagerTests(unittest.TestCase):
    def fake_snapshot(self, repo_id, revision, local_dir, allow_patterns=None):
        target = Path(local_dir)
        target.mkdir(parents=True, exist_ok=True)
        (target / "config.json").write_text(
            f'{{"repo":"{repo_id}","revision":"{revision}"}}', encoding="utf-8"
        )
        return str(target)

    def test_install_is_atomic_and_marks_pack_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalog = ModelCatalog(Path(tmp) / "models")
            installer = HuggingFacePackInstaller(catalog)
            fake_hub = types.SimpleNamespace(snapshot_download=self.fake_snapshot)
            with patch.dict(sys.modules, {"huggingface_hub": fake_hub}):
                pack = installer.install("business-qwen")
            self.assertTrue(pack.active)
            self.assertTrue((pack.path / "pack.json").is_file())
            self.assertFalse(
                (catalog.models_dir / ".staging" / "business-qwen-1.0.0").exists()
            )
            self.assertTrue(installer.verify(pack.id, pack.version))
            (pack.path / "components" / "asr" / "config.json").write_text(
                "corrupt", encoding="utf-8"
            )
            self.assertFalse(installer.verify(pack.id, pack.version))

    def test_rollback_returns_previous_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalog = ModelCatalog(Path(tmp) / "models")
            installer = HuggingFacePackInstaller(catalog)
            fake_hub = types.SimpleNamespace(snapshot_download=self.fake_snapshot)
            with patch.dict(sys.modules, {"huggingface_hub": fake_hub}):
                installer.install("business-qwen")
                installer.install("lite-nllb")
            self.assertEqual(catalog.active_pack().id, "lite-nllb")
            restored = installer.rollback()
            self.assertEqual(restored.id, "business-qwen")
            self.assertTrue(restored.active)

    def test_disk_full_has_specific_public_code(self):
        error = classify_model_exception(OSError(errno.ENOSPC, "disk full"))
        self.assertEqual(error.code, "MODEL_NO_SPACE")

    def test_permission_error_has_specific_public_code(self):
        error = classify_model_exception(PermissionError("denied"))
        self.assertEqual(error.code, "MODEL_PERMISSION_ERROR")

    def test_connection_error_has_specific_public_code(self):
        error = classify_model_exception(ConnectionError("offline"))
        self.assertEqual(error.code, "MODEL_NO_NETWORK")


if __name__ == "__main__":
    unittest.main()
