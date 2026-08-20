import json
import unittest
from pathlib import Path

from mily_ai.engine_registry import load_engine_descriptors
from mily_ai.provider_factory import TRANSLATION_BUILDERS
from mily_ai.resource_governor import ResourceGovernor, ResourceLimits


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "mily_ai" / "model-packs.json"


class EngineHubThreeLiteRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = json.loads(CATALOG.read_text(encoding="utf-8"))
        cls.packs = {item["id"]: item for item in payload["packs"]}
        cls.engines = {item.id: item for item in load_engine_descriptors()}
        cls.governor = ResourceGovernor(ResourceLimits())

    def test_three_local_lite_profiles_fit_the_complete_product_budget(self):
        expected = {
            "fast-moonshine-en-es": "en-es",
            "lite-en-es": "en-es",
            "lite-zh-es": "zh-es",
        }
        for pack_id, route in expected.items():
            with self.subTest(pack_id=pack_id):
                pack = self.packs[pack_id]
                self.assertEqual(pack["tier"], "lite")
                self.assertIn(route, pack["routes"])
                decision = self.governor.preflight_model(
                    model_ram_mb=float(pack["ramMb"]),
                    dedicated_vram_mb=float(pack.get("vramMb", 0)),
                    shared_gpu_mb=float(pack.get("sharedGpuMb", 0)),
                )
                self.assertTrue(decision.allowed, decision.reason)
                self.assertLessEqual(pack["ramMb"], 1200)
                self.assertLessEqual(pack.get("vramMb", 0), 384)

    def test_mandarin_lite_is_local_commercial_and_has_registered_cascade(self):
        pack = self.packs["lite-zh-es"]
        self.assertTrue(pack["commercialUse"])
        self.assertFalse(pack["bundled"])
        self.assertFalse(pack["externalAllowed"])
        self.assertEqual(pack["engine"], "local-ct2-lite")
        self.assertIn("marian-cascade-ct2", TRANSLATION_BUILDERS)
        self.assertIn("zh-es", self.engines["local-ct2-lite"].routes)

    def test_quality_profiles_remain_downloadable_but_cannot_activate_under_two_gib(self):
        for pack_id in ("realtime-m2m100", "business-qwen", "lite-nllb"):
            with self.subTest(pack_id=pack_id):
                pack = self.packs[pack_id]
                decision = self.governor.preflight_model(
                    model_ram_mb=float(pack["ramMb"]),
                    dedicated_vram_mb=float(pack.get("vramMb", 0)),
                    shared_gpu_mb=float(pack.get("sharedGpuMb", 0)),
                )
                self.assertFalse(decision.allowed)
                self.assertIn(
                    decision.reason,
                    {"PROCESS_MEMORY_LIMIT", "VRAM_LIMIT"},
                )


if __name__ == "__main__":
    unittest.main()
