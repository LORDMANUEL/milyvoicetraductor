import unittest
from pathlib import Path

from mily_ai.models import ModelCatalog, validate_external_pack_member


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


if __name__ == "__main__":
    unittest.main()
