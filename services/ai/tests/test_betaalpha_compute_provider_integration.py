import tempfile
import unittest
from pathlib import Path

from mily_ai.cpu_budget import detect_cpu_budget
from mily_ai.marian_cascade import CTranslate2MarianCascadeTranslator
from mily_ai.marian_realtime import CTranslate2RealtimeMarianTranslator
from mily_ai.provider_factory import build_translation_provider


class BetaAlphaComputeProviderIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.budget = detect_cpu_budget("light", physical_cores=2)

    def tearDown(self):
        self.temp.cleanup()

    def test_direct_marian_receives_betaalpha_autotune_flag(self):
        built = build_translation_provider(
            {
                "provider": "marian-ct2",
                "sourceLanguage": "en",
                "targetLanguage": "es",
                "betaAlphaTuneComputeType": True,
            },
            self.root,
            "cpu",
            self.budget,
        )
        self.assertIsInstance(built, CTranslate2RealtimeMarianTranslator)
        self.assertTrue(built.auto_tune_compute_type)

    def test_cascade_propagates_betaalpha_autotune_to_both_stages(self):
        built = build_translation_provider(
            {
                "provider": "marian-cascade-ct2",
                "betaAlphaTuneComputeType": True,
                "stages": [
                    {"sourceLanguage": "zh", "targetLanguage": "en"},
                    {"sourceLanguage": "en", "targetLanguage": "es"},
                ],
            },
            self.root,
            "cpu",
            self.budget,
        )
        self.assertIsInstance(built, CTranslate2MarianCascadeTranslator)
        self.assertTrue(built._first.auto_tune_compute_type)
        self.assertTrue(built._second.auto_tune_compute_type)


if __name__ == "__main__":
    unittest.main()
