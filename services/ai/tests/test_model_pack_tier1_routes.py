import json
import tempfile
import unittest
from pathlib import Path

from mily_ai.cpu_budget import detect_cpu_budget
from mily_ai.provider_factory import build_translation_provider


ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "services" / "ai" / "mily_ai"
CATALOG = AI_ROOT / "model-packs.json"
DESKTOP_CATALOG = ROOT / "resources" / "model-packs.json"
ENGINES = AI_ROOT / "engine-families.json"
PRODUCT_RESERVE_MB = 320
PROCESS_LIMIT_MB = 2048
VRAM_LIMIT_MB = 384
DIRECT_ES_ZH_REPO = "Helsinki-NLP/opus-tatoeba-es-zh"
DIRECT_ES_ZH_REVISION = "66c9fde497d230664c53c4c91c21d2e30f8cab47"
DIRECT_ES_ZH_PREFIX = ">>cmn_Hans<<"
DIRECT_ES_ZH_VERSION = "1.0.1"


def _packs(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {item["id"]: item for item in payload["packs"]}


class ModelPackTier1RouteTests(unittest.TestCase):
    def test_quality_pack_keeps_four_tier1_routes_as_optional_quality(self):
        packs = _packs(CATALOG)
        self.assertEqual(
            set(packs["realtime-m2m100"]["routes"]),
            {"en-es", "zh-es", "es-en", "es-zh"},
        )

    def test_outbound_lite_packs_cover_spanish_to_english_and_chinese(self):
        packs = _packs(CATALOG)
        expected = {
            "lite-es-en": {"es-en"},
            "lite-es-zh": {"es-zh"},
        }
        for pack_id, routes in expected.items():
            with self.subTest(pack=pack_id):
                pack = packs[pack_id]
                self.assertEqual(set(pack["routes"]), routes)
                self.assertEqual(pack["tier"], "lite")
                self.assertLessEqual(pack["ramMb"] + PRODUCT_RESERVE_MB, PROCESS_LIMIT_MB)
                self.assertLessEqual(pack["vramMb"], VRAM_LIMIT_MB)
                self.assertEqual(pack["components"]["asr"]["repoId"], "Systran/faster-whisper-tiny")

    def test_spanish_to_chinese_uses_pinned_direct_marian(self):
        pack = _packs(CATALOG)["lite-es-zh"]
        self.assertEqual(pack["version"], DIRECT_ES_ZH_VERSION)
        translation = pack["components"]["translation"]
        self.assertEqual(translation["provider"], "marian-ct2")
        self.assertEqual(translation["repoId"], DIRECT_ES_ZH_REPO)
        self.assertEqual(translation["revision"], DIRECT_ES_ZH_REVISION)
        self.assertEqual(translation["sourceLanguage"], "es")
        self.assertEqual(translation["targetLanguage"], "zh")
        self.assertEqual(translation["targetPrefix"], DIRECT_ES_ZH_PREFIX)
        self.assertNotIn("stages", translation)

    def test_direct_spanish_to_chinese_prefix_reaches_provider(self):
        translation = _packs(CATALOG)["lite-es-zh"]["components"]["translation"]
        with tempfile.TemporaryDirectory() as temp:
            provider = build_translation_provider(
                translation,
                Path(temp),
                "cpu",
                detect_cpu_budget("light", physical_cores=2),
            )
        self.assertEqual(provider.source_language, "es")
        self.assertEqual(provider.target_language, "zh")
        self.assertEqual(provider.target_prefix, DIRECT_ES_ZH_PREFIX)
        self.assertEqual(
            provider._model_input("Confirme el pedido 1038."),
            ">>cmn_Hans<< Confirme el pedido 1038.",
        )

    def test_receive_lite_packs_do_not_claim_outbound_routes(self):
        packs = _packs(CATALOG)
        for pack_id in ("fast-moonshine-en-es", "lite-en-es", "sherpa-zipformer-en-es", "lite-zh-es"):
            with self.subTest(pack=pack_id):
                routes = set(packs[pack_id]["routes"])
                self.assertNotIn("es-en", routes)
                self.assertNotIn("es-zh", routes)

    def test_python_and_desktop_catalogs_match_tier1_lite_contract(self):
        python_packs = _packs(CATALOG)
        desktop_packs = _packs(DESKTOP_CATALOG)
        for pack_id in ("lite-es-en", "lite-es-zh"):
            with self.subTest(pack=pack_id):
                for field in ("version", "tier", "routes", "ramMb", "vramMb", "engine", "supportedBackends"):
                    self.assertEqual(python_packs[pack_id][field], desktop_packs[pack_id][field])
                self.assertEqual(python_packs[pack_id]["components"], desktop_packs[pack_id]["components"])

    def test_engine_registry_exposes_all_verified_lite_routes(self):
        payload = json.loads(ENGINES.read_text(encoding="utf-8"))
        engines = {item["id"]: item for item in payload["engines"]}
        self.assertEqual(
            set(engines["local-ct2-quality"]["routes"]),
            {"en-es", "zh-es", "es-en", "es-zh"},
        )
        self.assertEqual(
            set(engines["local-ct2-lite"]["routes"]),
            {"en-es", "zh-es", "es-en", "es-zh"},
        )


if __name__ == "__main__":
    unittest.main()
