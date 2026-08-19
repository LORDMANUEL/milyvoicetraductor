import unittest
from pathlib import Path
from types import SimpleNamespace

from mily_ai.marian_realtime import CTranslate2RealtimeMarianTranslator
from mily_ai.translation_quality import (
    analyze_source_target_fidelity,
    analyze_translation_quality,
)


class _SentencePieceStub:
    def encode(self, text, out_type=str):
        return [token for token in text.replace(".", " .").split() if token]

    def decode(self, tokens):
        return " ".join(tokens)


class _TranslatorStub:
    def __init__(self, outputs=None):
        self.options = None
        self.calls = 0
        self.outputs = list(outputs or [["informe", "técnico", "mañana"]])

    def translate_batch(self, _sources, **options):
        self.options = options
        index = min(self.calls, len(self.outputs) - 1)
        self.calls += 1
        return [SimpleNamespace(hypotheses=[self.outputs[index]])]


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

    def test_fidelity_rejects_lost_negation(self):
        result = analyze_source_target_fidelity(
            "Do not cancel the order.",
            "Cancele el pedido.",
            "en",
            "es",
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.reason, "NEGATION_LOST")

    def test_fidelity_rejects_lost_numbers(self):
        result = analyze_source_target_fidelity(
            "Please confirm order 1038 at 9.",
            "Confirme el pedido a las 9.",
            "en",
            "es",
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.reason, "NUMBER_LOST")
        self.assertEqual(result.missing_numbers, ("1038",))

    def test_fidelity_accepts_preserved_negation_and_numbers(self):
        result = analyze_source_target_fidelity(
            "Do not cancel order 1038.",
            "No cancele el pedido 1038.",
            "en",
            "es",
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.reason, "OK")

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

    def test_marian_retries_when_greedy_loses_negation_or_number(self):
        provider = CTranslate2RealtimeMarianTranslator(
            Path("unused"),
            "cpu",
            source_language="en",
            target_language="es",
        )
        translator = _TranslatorStub(
            outputs=[
                ["Cancele", "el", "pedido"],
                ["No", "cancele", "el", "pedido", "1038"],
            ]
        )
        provider._translator = translator
        provider._source_sp = _SentencePieceStub()
        provider._target_sp = _SentencePieceStub()

        translated = provider.translate("Do not cancel order 1038.", "en")

        self.assertEqual(translator.calls, 2)
        self.assertIn("No", translated)
        self.assertIn("1038", translated)


if __name__ == "__main__":
    unittest.main()
