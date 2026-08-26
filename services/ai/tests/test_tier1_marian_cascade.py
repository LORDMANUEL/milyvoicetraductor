import unittest

from mily_ai.tier1_marian_cascade import Tier1MarianCascadeTranslator, warmup_text


class FakeStage:
    def __init__(self):
        self.calls = []
        self.selected_device = "cpu"
        self.fallback_used = False
        self.fallback_reason = ""

    def translate(self, text, language):
        self.calls.append((text, language))
        return "ok"


class Tier1MarianCascadeTests(unittest.TestCase):
    def test_warmup_text_exists_for_all_tier1_languages(self):
        for language in ("es", "en", "zh"):
            with self.subTest(language=language):
                self.assertTrue(warmup_text(language).strip())

    def test_spanish_to_chinese_warmup_uses_spanish_then_english(self):
        translator = Tier1MarianCascadeTranslator.__new__(Tier1MarianCascadeTranslator)
        translator.source_language = "es"
        translator.pivot_language = "en"
        translator.target_language = "zh"
        translator._first = FakeStage()
        translator._second = FakeStage()
        translator._warmed = False
        translator.selected_device = None
        translator.fallback_used = False
        translator.fallback_reason = ""

        translator.warm_up()

        self.assertEqual(translator._first.calls[0][1], "es")
        self.assertEqual(translator._second.calls[0][1], "en")
        self.assertIn("reunión", translator._first.calls[0][0].lower())
        self.assertIn("meeting", translator._second.calls[0][0].lower())
        self.assertTrue(translator._warmed)


if __name__ == "__main__":
    unittest.main()
