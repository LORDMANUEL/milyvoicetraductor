import tempfile
import unittest
import zipfile
from pathlib import Path

from mily_ai.betaalpha_native_marian import _safe_extract_zip


ROOT = Path(__file__).resolve().parents[3]
PATCH = ROOT / "services" / "ai" / "mily_ai" / "betaalpha_native_marian.py"
MAIN = ROOT / "services" / "ai" / "main.py"
LITE_REQ = ROOT / "services" / "ai" / "requirements.lite.txt"


class BetaAlphaNativeMarianConversionTests(unittest.TestCase):
    def test_native_converter_covers_tiny_en_es_and_zh_en_without_transformers(self):
        text = PATCH.read_text(encoding="utf-8")
        self.assertIn("Helsinki-NLP/opus-mt_tiny_eng-spa", text)
        self.assertIn("Helsinki-NLP/opus-mt-zh-en", text)
        self.assertIn("OpusMTConverter", text)
        self.assertIn("final.model.npz.best-perplexity.npz", text)
        self.assertIn("opus-2020-07-17.zip", text)
        self.assertNotIn("TransformersConverter", text)
        self.assertNotIn("import torch", text)
        self.assertNotIn("import transformers", text)

    def test_patch_is_installed_before_cli_import(self):
        text = MAIN.read_text(encoding="utf-8")
        install_at = text.index("install_betaalpha_native_marian_patch()")
        cli_at = text.index("from mily_ai.cli import main")
        self.assertLess(install_at, cli_at)

    def test_lite_requirements_stay_free_of_training_frameworks(self):
        active = [
            line.strip().lower()
            for line in LITE_REQ.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertFalse(any(line.startswith("torch") for line in active))
        self.assertFalse(any(line.startswith("transformers") for line in active))

    def test_native_zip_extractor_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("../escape.txt", "no")
            with self.assertRaises(RuntimeError):
                _safe_extract_zip(archive, root / "out")


if __name__ == "__main__":
    unittest.main()
