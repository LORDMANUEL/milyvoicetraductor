import errno
import json
import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

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

    @staticmethod
    def external_manifest():
        return {
            "schemaVersion": 2,
            "id": "partner-fast-en-es",
            "version": "1.0.0",
            "title": "Partner Fast EN-ES",
            "recommendedRamGb": 2,
            "commercialUse": True,
            "licenseNote": "Licencia comercial aprobada.",
            "tier": "lite",
            "routes": ["en-es"],
            "ramMb": 700,
            "vramMb": 0,
            "sharedGpuMb": 0,
            "engine": "local-ct2-lite",
            "supportedBackends": ["cpu"],
            "externalAllowed": True,
            "components": {
                "asr": {"provider": "faster-whisper"},
                "translation": {
                    "provider": "marian-ct2",
                    "sourceLanguage": "en",
                    "targetLanguage": "es",
                },
            },
        }

    def test_external_pack_is_imported_verified_and_not_auto_activated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "partner.mmpack"
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
                bundle.writestr(
                    "manifest.json",
                    json.dumps(self.external_manifest(), ensure_ascii=False),
                )
                bundle.writestr("components/asr/model.bin", b"asr")
                bundle.writestr("components/translation/model.bin", b"mt")
                bundle.writestr("LICENSE", "commercial")
            catalog = ModelCatalog(root / "models")
            installer = HuggingFacePackInstaller(catalog)
            pack = installer.import_pack(archive)
            self.assertFalse(pack.active)
            self.assertIsNone(catalog.active_pack())
            self.assertTrue(installer.verify(pack.id, pack.version))
            definition = catalog.definition(pack.id)
            self.assertEqual(definition["engine"], "local-ct2-lite")
            self.assertEqual(definition["ramMb"], 700)
            self.assertTrue((pack.path / "manifest.json").is_file())

    def test_external_zip_bomb_metadata_is_rejected_before_extract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "oversized.mmpack"
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_STORED) as bundle:
                bundle.writestr(
                    "manifest.json",
                    json.dumps(self.external_manifest(), ensure_ascii=False),
                )
                bundle.writestr("model.bin", b"x")
            catalog = ModelCatalog(root / "models")
            installer = HuggingFacePackInstaller(catalog)
            with patch("mily_ai.models._external_archive_size_allowed", return_value=False):
                with self.assertRaises(ModelOperationError) as captured:
                    installer.import_pack(archive)
            self.assertEqual(captured.exception.code, "MODEL_EXTERNAL_UNSAFE")

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
