import unittest
from pathlib import Path
from types import SimpleNamespace

from mily_ai.marian_realtime import CTranslate2RealtimeMarianTranslator
from mily_ai.translation_quality import analyze_translation_quality


class _SentencePieceStub:
    def encode(self, _text, out_type=str):
        return ["▁please", "▁send", "▁the", "▁report", "."]

    def decode(self, tokens):
        return " ".join(tokens)


class _TranslatorStub:
    def __init__(self):
        self.options = None

    def translate_batch(self, _sources, **options):
        self.options = options
        return [SimpleNamespace(hypotheses=[["informe", "técnico", "mañana"]])]


class TranslationQualityTests(unittest.TestCase):
    def test_pathological_repetition_is_rejected(self):
        result = analyze_translation_quality(
            "Por favor, envíe un informe técnico mañana por la mañana. "
            "Envíe un informe técnico mañana por la mañana por la mañana. "
            "Por favor, envíe un informe técnico mañana por la mañana por la mañana."
        )
        self.assertFalse(result.passed)
        self.assertGreater(result.repeated_ngram_ratio, 0.25)
        self.assertGreater(result.max_ngram_occurrences, 2)

    def test_normal_short_translation_passes(self):
        result = analyze_translation_quality(
            "Por favor, envíe el informe técnico mañana por la mañana."
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.max_ngram_occurrences, 1)

    def test_marian_decoder_enforces_anti_repetition_options(self):
        provider = CTranslate2RealtimeMarianTranslator(
            Path("unused"),
            "cpu",
            source_language="en",
            target_language="es",
        )
        translator = _TranslatorStub()
        provider._translator = translator
        provider._source_sp = _SentencePieceStub()
        provider._target_sp = _SentencePieceStub()

        translated = provider.translate("Please send the report.", "en")

        self.assertTrue(translated)
        self.assertEqual(translator.options["beam_size"], 1)
        self.assertGreater(translator.options["repetition_penalty"], 1.0)
        self.assertGreaterEqual(translator.options["no_repeat_ngram_size"], 3)


if __name__ == "__main__":
    unittest.main()
