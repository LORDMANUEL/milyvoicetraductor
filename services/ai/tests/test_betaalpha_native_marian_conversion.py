import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "services" / "ai" / "mily_ai" / "model-packs.json"
MODELS = ROOT / "services" / "ai" / "mily_ai" / "models.py"


class BetaAlphaNativeMarianConversionTests(unittest.TestCase):
    def test_lite_marian_packs_download_native_opus_assets(self):
        payload = json.loads(CATALOG.read_text(encoding="utf-8"))
        packs = {item["id"]: item for item in payload["packs"]}

        native_names = {
            "final.model.npz.best-perplexity.npz",
            "final.model.npz.best-perplexity.npz.decoder.yml",
            "vocab.spm",
        }
        for pack_id in ("lite-en-es", "fast-moonshine-en-es", "betaalpha-zipformer-en-es"):
            translation = packs[pack_id]["components"]["translation"]
            patterns = set(translation.get("allowPatterns", ()))
            self.assertTrue(
                native_names.issubset(patterns),
                f"{pack_id} debe poder convertirse sin Torch/Transformers",
            )

    def test_marian_conversion_prefers_opus_native_converter(self):
        text = MODELS.read_text(encoding="utf-8")
        self.assertIn("OpusMTConverter", text)
        start = text.index("def _convert_marian_to_ctranslate2")
        end = text.index("\ndef _prepare_component", start)
        marian_block = text[start:end]
        self.assertIn("OpusMTConverter", marian_block)
        self.assertNotIn("TransformersConverter", marian_block)


if __name__ == "__main__":
    unittest.main()
