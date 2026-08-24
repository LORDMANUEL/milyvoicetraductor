import unittest

from mily_ai import translation_quality as legacy
from mily_linguistic import quality as extracted


class TranslationQualityParityTests(unittest.TestCase):
    def test_quality_report_parity_on_normal_repetition_and_empty_corpus(self):
        corpus = [
            "",
            "Por favor, envíe el informe técnico mañana por la mañana.",
            (
                "Por favor, envíe un informe técnico mañana por la mañana. "
                "Envíe un informe técnico mañana por la mañana por la mañana. "
                "Por favor, envíe un informe técnico mañana por la mañana por la mañana."
            ),
            "Esto funciona. Esto funciona.",
            "muy, muy bien",
        ]
        for text in corpus:
            with self.subTest(text=text):
                self.assertEqual(
                    extracted.analyze_translation_quality(text).as_dict(),
                    legacy.analyze_translation_quality(text).as_dict(),
                )

    def test_fidelity_report_parity_for_negation_numbers_clocks_codes_and_prices(self):
        corpus = [
            ("Do not cancel order 1038.", "No cancele el pedido 1038.", "en", "es"),
            ("Do not cancel order 1038.", "Cancele el pedido 1038.", "en", "es"),
            ("Send 1038 units.", "Envíe 1000 unidades.", "en", "es"),
            ("Set priority 3.", "Establezca prioridad tres.", "en", "es"),
            ("Meeting at 9:00.", "Reunión a las nueve.", "en", "es"),
            ("Meeting at 5:30.", "Reunión a las cinco y media.", "en", "es"),
            ("Price is 5.30 dollars.", "El precio es 5.30 dólares.", "en", "es"),
            ("Price is 5.30 dollars.", "El precio es cinco dólares.", "en", "es"),
            ("Use code 03.", "Use el código 03.", "en", "es"),
            ("Use code 03.", "Use el código tres.", "en", "es"),
            ("Keep VIN 123456.", "Mantenga VIN 123456.", "en", "es"),
            ("Hay 42 piezas.", "There are 42 parts.", "es", "en"),
        ]
        for source, target, source_language, target_language in corpus:
            with self.subTest(source=source, target=target):
                self.assertEqual(
                    extracted.analyze_source_target_fidelity(
                        source, target, source_language, target_language
                    ).as_dict(),
                    legacy.analyze_source_target_fidelity(
                        source, target, source_language, target_language
                    ).as_dict(),
                )

    def test_prefix_recovery_parity(self):
        sentence_loop = "Primera frase útil. Segunda frase útil. Segunda frase útil."
        ngram_loop = (
            "No cancele el pedido 1038 y no cancele el pedido 1038 y "
            "no cancele el pedido 1038."
        )
        self.assertEqual(
            extracted.non_repetitive_sentence_prefix(sentence_loop),
            legacy.non_repetitive_sentence_prefix(sentence_loop),
        )
        self.assertEqual(
            extracted.non_repetitive_ngram_prefix(ngram_loop),
            legacy.non_repetitive_ngram_prefix(ngram_loop),
        )

    def test_validation_error_parity(self):
        invalid_calls = [
            lambda module: module.analyze_translation_quality("hello", ngram_size=1),
            lambda module: module.analyze_translation_quality(
                "hello", max_repeated_ngram_ratio=2.0
            ),
            lambda module: module.non_repetitive_ngram_prefix("hello", ngram_size=1),
        ]
        for call in invalid_calls:
            with self.subTest(call=call):
                with self.assertRaises(ValueError) as legacy_error:
                    call(legacy)
                with self.assertRaises(ValueError) as extracted_error:
                    call(extracted)
                self.assertEqual(str(extracted_error.exception), str(legacy_error.exception))


if __name__ == "__main__":
    unittest.main()
