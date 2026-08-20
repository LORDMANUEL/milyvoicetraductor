import unittest
from pathlib import Path
from types import SimpleNamespace

from mily_ai.marian_realtime import CTranslate2RealtimeMarianTranslator
from mily_ai.translation_quality import (
    analyze_source_target_fidelity,
    analyze_translation_quality,
    non_repetitive_ngram_prefix,
)


class _SentencePieceStub:
    def __init__(self):
        self.encoded_texts: list[str] = []

    def encode(self, text, out_type=str):
        self.encoded_texts.append(text)
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

    def test_single_sentence_loop_recovers_the_longest_safe_ngram_prefix(self):
        repeated = (
            "No cancele el pedido 1038 y no cancele el pedido 1038 y "
            "no cancele el pedido 1038."
        )
        self.assertFalse(analyze_translation_quality(repeated).passed)

        prefix = non_repetitive_ngram_prefix(repeated)

        self.assertTrue(prefix)
        self.assertTrue(analyze_translation_quality(prefix).passed)
        self.assertIn("1038", prefix)
        self.assertNotEqual(prefix, repeated)
        self.assertFalse(prefix.rstrip(" .").endswith(" y"))

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

    def test_fidelity_accepts_small_number_as_spanish_word(self):
        result = analyze_source_target_fidelity(
            "The meeting starts at 9.",
            "La reunión empieza a las nueve.",
            "en",
            "es",
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.missing_numbers, ())

    def test_fidelity_accepts_clock_words_without_false_number_loss(self):
        nine = analyze_source_target_fidelity(
            "The meeting starts at 9:00.",
            "La reunión empieza a las nueve.",
            "en",
            "es",
        )
        five_thirty = analyze_source_target_fidelity(
            "The client needs the invoice before 5:30.",
            "El cliente necesita la factura antes de las cinco y media.",
            "en",
            "es",
        )
        self.assertTrue(nine.passed)
        self.assertTrue(five_thirty.passed)

    def test_fidelity_accepts_dot_clock_only_with_time_context(self):
        nine = analyze_source_target_fidelity(
            "The meeting starts at 9.00.",
            "La reunión empieza a las nueve.",
            "en",
            "es",
        )
        five_thirty = analyze_source_target_fidelity(
            "The client needs the invoice before 5.30.",
            "El cliente necesita la factura antes de las cinco y media.",
            "en",
            "es",
        )
        price = analyze_source_target_fidelity(
            "The price is 5.30.",
            "El precio es cinco y treinta.",
            "en",
            "es",
        )
        self.assertTrue(nine.passed)
        self.assertTrue(five_thirty.passed)
        self.assertFalse(price.passed)
        self.assertEqual(price.missing_numbers, ("5.30",))

    def test_fidelity_keeps_order_identifiers_exact_even_when_small(self):
        result = analyze_source_target_fidelity(
            "Do not cancel order 9.",
            "No cancele el pedido nueve.",
            "en",
            "es",
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.reason, "NUMBER_LOST")
        self.assertEqual(result.missing_numbers, ("9",))

    def test_fidelity_keeps_large_identifier_exact(self):
        result = analyze_source_target_fidelity(
            "Do not cancel order 1038.",
            "No cancele el pedido mil treinta y ocho.",
            "en",
            "es",
        )
        self.assertFalse(result.passed)
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

    def test_marian_salvages_safe_prefix_from_single_sentence_loop(self):
        provider = CTranslate2RealtimeMarianTranslator(
            Path("unused"),
            "cpu",
            source_language="en",
            target_language="es",
        )
        loop = [
            "No",
            "cancele",
            "el",
            "pedido",
            "1038",
            "y",
            "no",
            "cancele",
            "el",
            "pedido",
            "1038",
            "y",
            "no",
            "cancele",
            "el",
            "pedido",
            "1038",
        ]
        translator = _TranslatorStub(outputs=[loop, loop])
        provider._translator = translator
        provider._source_sp = _SentencePieceStub()
        provider._target_sp = _SentencePieceStub()

        translated = provider.translate("Do not cancel order 1038.", "en")

        self.assertEqual(translator.calls, 2)
        self.assertTrue(analyze_translation_quality(translated).passed)
        self.assertIn("1038", translated)
        self.assertTrue(translated.casefold().startswith("no "))
        self.assertLess(len(translated.split()), len(loop))

    def test_marian_uses_strict_rescue_when_prefix_would_lose_critical_data(self):
        provider = CTranslate2RealtimeMarianTranslator(
            Path("unused"),
            "cpu",
            source_language="en",
            target_language="es",
        )
        early_loop = [
            "No",
            "no",
            "no",
            "no",
            "no",
            "no",
            "no",
            "no",
            "cancele",
            "el",
            "pedido",
            "1038",
        ]
        self.assertFalse(analyze_translation_quality(" ".join(early_loop)).passed)
        translator = _TranslatorStub(
            outputs=[
                early_loop,
                early_loop,
                ["No", "cancele", "el", "pedido", "1038"],
            ]
        )
        provider._translator = translator
        provider._source_sp = _SentencePieceStub()
        provider._target_sp = _SentencePieceStub()

        translated = provider.translate("Do not cancel order 1038.", "en")

        self.assertEqual(translator.calls, 3)
        self.assertEqual(translated, "No cancele el pedido 1038")
        self.assertEqual(translator.options["beam_size"], 3)
        self.assertEqual(translator.options["no_repeat_ngram_size"], 2)
        self.assertGreaterEqual(translator.options["repetition_penalty"], 1.3)

    def test_marian_uses_beam_four_fidelity_rescue_after_three_failed_outputs(self):
        provider = CTranslate2RealtimeMarianTranslator(
            Path("unused"),
            "cpu",
            source_language="en",
            target_language="es",
        )
        bad = ["Cancele", "el", "pedido"]
        source_sp = _SentencePieceStub()
        translator = _TranslatorStub(
            outputs=[
                bad,
                bad,
                bad,
                ["No", "cancele", "el", "pedido", "1038"],
            ]
        )
        provider._translator = translator
        provider._source_sp = source_sp
        provider._target_sp = _SentencePieceStub()

        translated = provider.translate("Don't cancel order 1038.", "en")

        self.assertEqual(translator.calls, 4)
        self.assertEqual(translated, "No cancele el pedido 1038")
        self.assertEqual(translator.options["beam_size"], 4)
        self.assertEqual(translator.options["no_repeat_ngram_size"], 3)
        self.assertIn("do not cancel order 1038.", source_sp.encoded_texts[-1].casefold())
        self.assertTrue(
            analyze_source_target_fidelity(
                "Don't cancel order 1038.", translated, "en", "es"
            ).passed
        )


if __name__ == "__main__":
    unittest.main()
