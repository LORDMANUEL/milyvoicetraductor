import unittest
from pathlib import Path

from mily_ai.models import (
    ModelCatalog,
    ModelOperationError,
    validate_external_pack_manifest,
    validate_external_pack_member,
)


class ModelPackV2Tests(unittest.TestCase):
    def test_catalog_contains_a_real_lite_en_es_pack(self):
        catalog = ModelCatalog(Path("unused"))
        definitions = catalog.definitions()
        lite = next(item for item in definitions if item["id"] == "lite-en-es")
        self.assertEqual(lite["schemaVersion"], 2)
        self.assertEqual(lite["tier"], "lite")
        self.assertIn("en-es", lite["routes"])
        self.assertLessEqual(lite["ramMb"], 1200)
        self.assertLessEqual(lite["vramMb"], 384)
        self.assertEqual(
            lite["components"]["translation"]["provider"], "marian-ct2"
        )
        self.assertIn(
            "tiny", lite["components"]["asr"]["repoId"].casefold()
        )

    def test_external_pack_rejects_executable_or_script_payloads(self):
        for name in (
            "run.py",
            "install.ps1",
            "driver.dll",
            "payload.exe",
            "script.bat",
            "native.so",
            "../escape/model.onnx",
            "/absolute/model.onnx",
        ):
            with self.subTest(name=name):
                self.assertFalse(validate_external_pack_member(name))

    def test_external_pack_accepts_model_data_only(self):
        for name in (
            "manifest.json",
            "model/model.onnx",
            "model/model.ort",
            "model/model.bin",
            "tokenizer/source.spm",
            "tokenizer/vocab.json",
            "tokens.txt",
            "LICENSE",
        ):
            with self.subTest(name=name):
                self.assertTrue(validate_external_pack_member(name))

    @staticmethod
    def valid_external_manifest():
        return {
            "schemaVersion": 2,
            "id": "partner-fast-en-es",
            "version": "1.0.0",
            "title": "Partner Fast EN-ES",
            "recommendedRamGb": 2,
            "commercialUse": True,
            "licenseNote": "Modelo autorizado para uso comercial.",
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

    def test_external_manifest_accepts_registered_data_only_pack(self):
        normalized = validate_external_pack_manifest(
            self.valid_external_manifest()
        )
        self.assertEqual(normalized["id"], "partner-fast-en-es")
        self.assertEqual(normalized["ramMb"], 700)
        self.assertEqual(normalized["supportedBackends"], ["cpu"])

    def test_external_manifest_rejects_unknown_engine_or_provider(self):
        for mutation in (
            ("engine", "run-my-code"),
            ("asr-provider", "custom-python"),
            ("translation-provider", "remote-code"),
        ):
            with self.subTest(mutation=mutation):
                manifest = self.valid_external_manifest()
                kind, value = mutation
                if kind == "engine":
                    manifest["engine"] = value
                elif kind == "asr-provider":
                    manifest["components"]["asr"]["provider"] = value
                else:
                    manifest["components"]["translation"]["provider"] = value
                with self.assertRaises(ModelOperationError) as captured:
                    validate_external_pack_manifest(manifest)
                self.assertEqual(captured.exception.code, "MODEL_EXTERNAL_MANIFEST")

    def test_external_manifest_requires_explicit_memory_and_license(self):
        for missing in ("ramMb", "licenseNote", "routes", "externalAllowed"):
            with self.subTest(missing=missing):
                manifest = self.valid_external_manifest()
                manifest.pop(missing)
                with self.assertRaises(ModelOperationError):
                    validate_external_pack_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
