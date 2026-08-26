import json
import unittest
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1] / "mily_ai"
CATALOG = AI_ROOT / "model-packs.json"
ENGINES = AI_ROOT / "engine-families.json"


class ModelPackTier1RouteTests(unittest.TestCase):
    def test_quality_pack_exposes_four_tier1_routes(self):
        payload = json.loads(CATALOG.read_text(encoding="utf-8"))
        packs = {item["id"]: item for item in payload["packs"]}
        self.assertEqual(
            set(packs["realtime-m2m100"]["routes"]),
            {"en-es", "zh-es", "es-en", "es-zh"},
        )

    def test_lite_packs_do_not_claim_unverified_outbound_routes(self):
        payload = json.loads(CATALOG.read_text(encoding="utf-8"))
        packs = {item["id"]: item for item in payload["packs"]}
        for pack_id in ("fast-moonshine-en-es", "lite-en-es", "sherpa-zipformer-en-es", "lite-zh-es"):
            with self.subTest(pack=pack_id):
                routes = set(packs[pack_id]["routes"])
                self.assertNotIn("es-en", routes)
                self.assertNotIn("es-zh", routes)

    def test_engine_registry_matches_verified_quality_and_lite_capabilities(self):
        payload = json.loads(ENGINES.read_text(encoding="utf-8"))
        engines = {item["id"]: item for item in payload["engines"]}
        self.assertEqual(
            set(engines["local-ct2-quality"]["routes"]),
            {"en-es", "zh-es", "es-en", "es-zh"},
        )
        lite_routes = set(engines["local-ct2-lite"]["routes"])
        self.assertEqual(lite_routes, {"en-es", "zh-es"})
        self.assertNotIn("es-en", lite_routes)
        self.assertNotIn("es-zh", lite_routes)


if __name__ == "__main__":
    unittest.main()
