import json
import unittest
from pathlib import Path


CATALOG = Path(__file__).resolve().parents[1] / "mily_ai" / "model-packs.json"


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


if __name__ == "__main__":
    unittest.main()
