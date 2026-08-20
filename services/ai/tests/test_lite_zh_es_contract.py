import json
import unittest
from pathlib import Path

from mily_ai.marian_cascade import CTranslate2MarianCascadeTranslator
from mily_ai.models import ModelCatalog
from mily_ai.provider_factory import TRANSLATION_BUILDERS


class _WarmStage:
    def __init__(self, output: str):
        self.output = output
        self.calls: list[tuple[str, str]] = []
        self.selected_device = "cpu"
        self.fallback_used = False
        self.fallback_reason = ""

    def translate(self, text: str, source_language: str) -> str:
        self.calls.append((text, source_language))
        return self.output


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

    def test_cascade_warmup_primes_each_stage_with_its_own_language(self):
        provider = CTranslate2MarianCascadeTranslator.__new__(
            CTranslate2MarianCascadeTranslator
        )
        provider.source_language = "zh"
        provider.pivot_language = "en"
        provider.target_language = "es"
        provider._first = _WarmStage("degenerate pivot must not be chained")
        provider._second = _WarmStage("horario confirmado")
        provider.selected_device = None
        provider.fallback_used = False
        provider.fallback_reason = ""
        provider._warmed = False

        provider.warm_up()
        provider.warm_up()

        self.assertEqual(len(provider._first.calls), 1)
        self.assertEqual(provider._first.calls[0][1], "zh")
        self.assertTrue(
            any("\u4e00" <= char <= "\u9fff" for char in provider._first.calls[0][0])
        )
        self.assertEqual(
            provider._second.calls,
            [("Please confirm today's meeting schedule.", "en")],
        )
        self.assertTrue(provider._warmed)


if __name__ == "__main__":
    unittest.main()
