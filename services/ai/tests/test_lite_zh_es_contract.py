import json
import unittest
from pathlib import Path

from mily_ai.models import ModelCatalog
from mily_ai.provider_factory import TRANSLATION_BUILDERS


class LiteZhEsContractTests(unittest.TestCase):
    def test_catalog_contains_local_zh_es_lite_under_memory_budget(self):
        catalog = ModelCatalog(Path("unused"))
        definition = catalog.definition("lite-zh-es")
        self.assertEqual(definition["tier"], "lite")
        self.assertEqual(definition["routes"], ["zh-es"])
        self.assertLessEqual(definition["ramMb"], 1200)
        self.assertLessEqual(definition["vramMb"], 384)
        self.assertTrue(definition["commercialUse"])
        self.assertEqual(definition["engine"], "local-ct2-lite")

    def test_zh_es_uses_multilingual_tiny_asr_and_two_stage_marian(self):
        definition = ModelCatalog(Path("unused")).definition("lite-zh-es")
        components = definition["components"]
        asr = components["asr"]
        translation = components["translation"]
        self.assertEqual(asr["provider"], "faster-whisper")
        self.assertIn("faster-whisper-tiny", asr["repoId"])
        self.assertNotIn("tiny.en", asr["repoId"])
        self.assertEqual(translation["provider"], "marian-cascade-ct2")
        stages = translation["stages"]
        self.assertEqual(len(stages), 2)
        self.assertEqual(
            [(stage["sourceLanguage"], stage["targetLanguage"]) for stage in stages],
            [("zh", "en"), ("en", "es")],
        )
        self.assertTrue(all(stage["quantization"] == "int8" for stage in stages))

    def test_provider_and_engine_route_are_registered(self):
        self.assertIn("marian-cascade-ct2", TRANSLATION_BUILDERS)
        path = Path(__file__).resolve().parents[1] / "mily_ai" / "engine-families.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        lite = next(item for item in payload["engines"] if item["id"] == "local-ct2-lite")
        self.assertIn("zh-es", lite["routes"])


if __name__ == "__main__":
    unittest.main()
