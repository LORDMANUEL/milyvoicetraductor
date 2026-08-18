import json
import tempfile
import unittest
from pathlib import Path

from mily_ai.models import ModelCatalog
from mily_ai.providers import CachedTranslator, Translator


class FakeTranslator(Translator):
    def __init__(self):
        self.calls = 0

    def translate(self, text: str, source_language: str) -> str:
        self.calls += 1
        return f"{source_language}:{text}"


class RealtimeOptimizationTests(unittest.TestCase):
    def test_translation_cache_avoids_recomputing_overlap_text(self):
        inner = FakeTranslator()
        translator = CachedTranslator(inner, max_entries=4)

        first = translator.translate("  Hello   world  ", "en")
        second = translator.translate("Hello world", "en")

        self.assertEqual(first, second)
        self.assertEqual(inner.calls, 1)

    def test_translation_cache_keeps_languages_separate(self):
        inner = FakeTranslator()
        translator = CachedTranslator(inner, max_entries=4)

        translator.translate("hola", "en")
        translator.translate("hola", "zh")

        self.assertEqual(inner.calls, 2)

    def test_realtime_commercial_pack_uses_m2m100_ctranslate2_int8(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalog = ModelCatalog(Path(tmp))
            pack = catalog.definition("realtime-m2m100")

        self.assertTrue(pack["commercialUse"])
        translation = pack["components"]["translation"]
        self.assertEqual(translation["provider"], "m2m100-ct2")
        self.assertEqual(translation["quantization"], "int8")
        self.assertEqual(translation["repoId"], "facebook/m2m100_418M")
        self.assertNotEqual(translation["revision"], "main")
        self.assertIn("pytorch_model.bin", translation["allowPatterns"])
        self.assertNotIn("rust_model.ot", translation["allowPatterns"])


if __name__ == "__main__":
    unittest.main()
