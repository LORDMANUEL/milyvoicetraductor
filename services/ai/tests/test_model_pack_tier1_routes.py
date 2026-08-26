import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "services" / "ai" / "mily_ai"
CATALOG = AI_ROOT / "model-packs.json"
DESKTOP_CATALOG = ROOT / "resources" / "model-packs.json"
ENGINES = AI_ROOT / "engine-families.json"
PRODUCT_RESERVE_MB = 320
PROCESS_LIMIT_MB = 2048
VRAM_LIMIT_MB = 384


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

    def test_spanish_to_chinese_uses_local_marian_cascade(self):
        pack = _packs(CATALOG)["lite-es-zh"]
        translation = pack["components"]["translation"]
        self.assertEqual(translation["provider"], "marian-cascade-ct2")
        stages = translation["stages"]
        self.assertEqual(
            [(stage["sourceLanguage"], stage["targetLanguage"]) for stage in stages],
            [("es", "en"), ("en", "zh")],
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
