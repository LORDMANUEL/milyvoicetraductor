import tempfile
import unittest
from pathlib import Path

from mily_ai.bilingual_marian import CTranslate2BilingualMarianRouter
from mily_ai.cpu_budget import detect_cpu_budget
from mily_ai.models import ModelCatalog
from mily_ai.provider_factory import TRANSLATION_BUILDERS, build_translation_provider
from mily_ai.session_routing import route_for_languages


class _Stage:
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def translate(self, text, language):
        self.calls.append((text, language))
        return self.mapping.get(text, text)

    def warm_up(self):
        pass

    def unload(self):
        pass


class BetaAlphaBilingualAutoTests(unittest.TestCase):
    def test_catalog_has_one_bilingual_auto_pack_for_en_and_zh_to_es(self):
        pack = ModelCatalog(Path("unused")).definition("betaalpha-auto-es")
        self.assertEqual(pack["routes"], ["en-es", "zh-es"])
        self.assertEqual(pack["tier"], "lite")
        self.assertLessEqual(pack["ramMb"], 1200)
        self.assertEqual(pack["components"]["asr"]["provider"], "sherpa-onnx")
        self.assertEqual(pack["components"]["asr"]["sherpaMode"], "online-paraformer")
        self.assertEqual(pack["components"]["asr"]["language"], "auto")
        self.assertEqual(
            pack["components"]["translation"]["provider"],
            "marian-bilingual-router-ct2",
        )

    def test_router_uses_direct_en_es_and_cascade_only_for_zh(self):
        first = _Stage({"你好": "hello"})
        second = _Stage({"hello": "hola", "good morning": "buenos días"})
        router = CTranslate2BilingualMarianRouter.__new__(CTranslate2BilingualMarianRouter)
        router._zh_en = first
        router._en_es = second
        router.source_languages = {"en", "zh"}
        router.target_language = "es"
        router.selected_device = "cpu"
        router.fallback_used = False
        router.fallback_reason = ""
        router._warmed = True

        self.assertEqual(router.translate("good morning", "en"), "buenos días")
        self.assertEqual(first.calls, [])
        self.assertEqual(router.translate("你好", "zh"), "hola")
        self.assertEqual(first.calls, [("你好", "zh")])
        self.assertEqual(second.calls, [("good morning", "en"), ("hello", "en")])

    def test_factory_registers_bilingual_router(self):
        self.assertIn("marian-bilingual-router-ct2", TRANSLATION_BUILDERS)
        with tempfile.TemporaryDirectory() as tmp:
            built = build_translation_provider(
                {
                    "provider": "marian-bilingual-router-ct2",
                    "betaAlphaTuneComputeType": True,
                    "stages": [
                        {"sourceLanguage": "zh", "targetLanguage": "en"},
                        {"sourceLanguage": "en", "targetLanguage": "es"},
                    ],
                },
                Path(tmp),
                "cpu",
                detect_cpu_budget("light", physical_cores=2),
            )
            self.assertIsInstance(built, CTranslate2BilingualMarianRouter)

    def test_session_route_is_direction_specific_and_auto_is_deferred(self):
        self.assertEqual(route_for_languages("en", "es"), "en-es")
        self.assertEqual(route_for_languages("zh", "es"), "zh-es")
        self.assertIsNone(route_for_languages("auto", "es"))
        self.assertIsNone(route_for_languages("es", "en"))


if __name__ == "__main__":
    unittest.main()
