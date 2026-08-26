import unittest
from types import SimpleNamespace

from mily_ai.tier1_pipeline import Tier1RealtimePipeline, resolve_target_language


class Tier1SessionRouteTests(unittest.TestCase):
    def test_explicit_target_wins_recorder_default(self):
        recorder = SimpleNamespace(target_language="es")
        self.assertEqual(resolve_target_language(recorder, "en"), "en")

    def test_recorder_target_is_used_when_server_does_not_pass_explicit_target(self):
        recorder = SimpleNamespace(target_language="zh")
        self.assertEqual(resolve_target_language(recorder, None), "zh")

    def test_explicit_spanish_wins_language_detection(self):
        self.assertEqual(
            Tier1RealtimePipeline._detect_language("hola mundo", "auto", "es"),
            "es",
        )

    def test_detected_tier1_language_wins_when_available(self):
        self.assertEqual(
            Tier1RealtimePipeline._detect_language("hello", "en", "auto"),
            "en",
        )
        self.assertEqual(
            Tier1RealtimePipeline._detect_language("你好", "zh", "auto"),
            "zh",
        )


if __name__ == "__main__":
    unittest.main()
