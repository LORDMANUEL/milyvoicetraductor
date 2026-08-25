import inspect
import json
import unittest
from pathlib import Path

from mily_ai.provider_factory import TRANSLATION_BUILDERS, build_translation_provider
from mily_mt import MarianEnEsMtAdapter, MarianZhEsCascadeMtAdapter


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "ai" / "mily_ai" / "model-packs.json"


class LegacyTranslationFactoryContractTests(unittest.TestCase):
    def test_current_factory_exposes_promoted_mt_provider_ids_and_signature(self):
        self.assertIn("marian-ct2", TRANSLATION_BUILDERS)
        self.assertIn("marian-cascade-ct2", TRANSLATION_BUILDERS)
        self.assertEqual(
            tuple(inspect.signature(build_translation_provider).parameters),
            ("component", "model_path", "compute_profile", "cpu_budget"),
        )
        self.assertEqual(MarianEnEsMtAdapter.provider_id, "marian-ct2")
        self.assertEqual(
            MarianZhEsCascadeMtAdapter.provider_id,
            "marian-cascade-ct2",
        )

    def test_promoted_two_gb_packs_map_to_expected_mt_routes(self):
        payload = json.loads(CATALOG.read_text(encoding="utf-8"))
        packs = {item["id"]: item for item in payload["packs"]}
        expected = {
            "fast-moonshine-en-es": ("en-es", "marian-ct2"),
            "lite-en-es": ("en-es", "marian-ct2"),
            "sherpa-zipformer-en-es": ("en-es", "marian-ct2"),
            "lite-zh-es": ("zh-es", "marian-cascade-ct2"),
        }
        for pack_id, (route, provider) in expected.items():
            with self.subTest(pack_id=pack_id):
                pack = packs[pack_id]
                self.assertEqual(pack["tier"], "lite")
                self.assertIn(route, pack["routes"])
                self.assertEqual(pack["recommendedRamGb"], 2)
                self.assertLessEqual(pack["ramMb"], 1200)
                self.assertTrue(pack["commercialUse"])
                self.assertEqual(pack["components"]["translation"]["provider"], provider)

    def test_reverse_routes_are_not_advertised_without_model_packs(self):
        payload = json.loads(CATALOG.read_text(encoding="utf-8"))
        routes = {
            route
            for pack in payload["packs"]
            for route in pack.get("routes", [])
        }
        self.assertNotIn("es-en", routes)
        self.assertNotIn("es-zh", routes)


if __name__ == "__main__":
    unittest.main()
