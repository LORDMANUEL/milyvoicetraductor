import errno
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import mily_ai.models as models_module
from mily_ai.models import (
    HuggingFacePackInstaller,
    ModelCatalog,
    ModelOperationError,
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

    def test_reinstall_repairs_an_installed_pack_with_corrupted_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalog = ModelCatalog(Path(tmp) / "models")
            installer = HuggingFacePackInstaller(catalog)
            fake_hub = types.SimpleNamespace(snapshot_download=self.fake_snapshot)
            with patch.dict(sys.modules, {"huggingface_hub": fake_hub}):
                installed = installer.install("business-qwen")
                corrupted = installed.path / "components" / "asr" / "config.json"
                corrupted.write_text("corrupt", encoding="utf-8")
                self.assertFalse(installer.verify(installed.id, installed.version))

                repaired = installer.install("business-qwen")

            self.assertTrue(repaired.active)
            self.assertTrue(installer.verify(repaired.id, repaired.version))
            self.assertNotEqual(corrupted.read_text(encoding="utf-8"), "corrupt")
            self.assertFalse(
                (catalog.models_dir / ".staging" / "business-qwen-1.0.0").exists()
            )

    def test_model_mutations_use_a_nonblocking_cross_process_lock(self):
        self.assertTrue(
            hasattr(models_module, "_model_operation_lock"),
            "Las mutaciones de modelos necesitan un lock de archivo compartido entre Desktop/API/CLI.",
        )
        lock = getattr(models_module, "_model_operation_lock")
        with tempfile.TemporaryDirectory() as tmp:
            models_dir = Path(tmp) / "models"
            with lock(models_dir):
                with self.assertRaises(ModelOperationError) as caught:
                    with lock(models_dir):
                        pass
        self.assertEqual(caught.exception.code, "MODEL_OPERATION_BUSY")

    def test_install_reports_download_optimize_verify_and_ready_phases(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalog = ModelCatalog(Path(tmp) / "models")
            installer = HuggingFacePackInstaller(catalog)
            observed: list[tuple[str, str | None]] = []

            def read_phase() -> tuple[str, str | None]:
                payload = json.loads(catalog.operation_path.read_text(encoding="utf-8"))
                return str(payload.get("phase")), payload.get("component")

            def snapshot(repo_id, revision, local_dir, allow_patterns=None):
                observed.append(read_phase())
                return self.fake_snapshot(repo_id, revision, local_dir, allow_patterns)

            def prepare(component, target):
                observed.append(read_phase())

            fake_hub = types.SimpleNamespace(snapshot_download=snapshot)
            with patch.dict(sys.modules, {"huggingface_hub": fake_hub}), patch(
                "mily_ai.models._prepare_component", side_effect=prepare
            ):
                installer.install("realtime-m2m100")

            final = json.loads(catalog.operation_path.read_text(encoding="utf-8"))
            self.assertIn(("download", "asr"), observed)
            self.assertIn(("download", "translation"), observed)
            self.assertIn(("optimize", "translation"), observed)
            self.assertEqual(final["state"], "ready")
            self.assertEqual(final["phase"], "ready")
            self.assertEqual(final["packId"], "realtime-m2m100")

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
