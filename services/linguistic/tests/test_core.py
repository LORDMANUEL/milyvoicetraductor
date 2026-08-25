import unittest

from mily_linguistic import (
    ContextBuffer,
    TerminologyBook,
    TerminologyRule,
    normalize_text,
    prepare_translation_input,
    segment_sentences,
)


class LinguisticCoreTests(unittest.TestCase):
    def test_normalize_text_nfkc_and_whitespace_without_rewriting_punctuation(self):
        source = "  ＶＩＮ\t１２３\r\nDo   not  cancel!  "
        self.assertEqual(normalize_text(source), "VIN 123 Do not cancel!")
        self.assertEqual(normalize_text("  \n\t "), "")

    def test_sentence_segmentation_keeps_terminal_punctuation_and_tail(self):
        self.assertEqual(
            segment_sentences("Hello world!  你好。 Next line? tail"),
            ("Hello world!", "你好。", "Next line?", "tail"),
        )
        self.assertEqual(segment_sentences(""), ())

    def test_terminology_word_boundaries_prevent_partial_identifier_matches(self):
        book = TerminologyBook(
            [
                TerminologyRule("VIN", "VIN", "en", "es"),
                TerminologyRule("work order", "orden de trabajo", "en", "es"),
            ]
        )

        selected = book.select("Confirm VIN 1038 in the work order.", "en", "es")
        self.assertEqual([rule.source for rule in selected], ["VIN", "work order"])
        self.assertEqual(book.select("This is VINTAGE inventory.", "en", "es"), ())

    def test_terminology_case_sensitive_mode_and_route_filter(self):
        book = TerminologyBook(
            [
                TerminologyRule("SYNC", "SYNC", "en", "es", case_sensitive=True),
                TerminologyRule("SYNC", "SYNC", "es", "en", case_sensitive=True),
            ]
        )
        self.assertEqual(len(book.select("Use SYNC now", "en", "es")), 1)
        self.assertEqual(book.select("Use sync now", "en", "es"), ())
        self.assertEqual(len(book.select("Usa SYNC", "es", "en")), 1)

    def test_duplicate_terminology_route_and_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            TerminologyBook(
                [
                    TerminologyRule("VIN", "VIN", "en", "es"),
                    TerminologyRule("vin", "número VIN", "en", "es"),
                ]
            )

    def test_context_is_bounded_by_items_and_total_characters(self):
        context = ContextBuffer(max_items=3, max_chars=20)
        context.append("first one", "en")
        context.append("second one", "en")
        context.append("third", "en")
        context.append("fourth", "en")

        snapshot = context.snapshot()
        self.assertLessEqual(len(snapshot), 3)
        self.assertLessEqual(sum(len(item.text) for item in snapshot), 20)
        self.assertEqual(snapshot[-1].text, "fourth")
        self.assertNotIn("first one", [item.text for item in snapshot])

    def test_oversized_context_turn_retains_recent_suffix(self):
        context = ContextBuffer(max_items=2, max_chars=8)
        context.append("1234567890", "en")
        self.assertEqual(context.snapshot()[0].text, "34567890")

    def test_empty_context_turn_is_ignored_and_language_is_required(self):
        context = ContextBuffer(max_items=2, max_chars=20)
        self.assertFalse(context.append("   ", "en"))
        self.assertEqual(context.snapshot(), ())
        with self.assertRaises(ValueError):
            context.append("hello", "")

    def test_prepare_translation_input_is_side_effect_free_and_selects_terms(self):
        context = ContextBuffer(max_items=3, max_chars=100)
        context.append("Previous order 1038.", "en")
        book = TerminologyBook(
            [TerminologyRule("work order", "orden de trabajo", "en", "es")]
        )

        prepared = prepare_translation_input(
            "  Please check the work order.  Next step! ",
            "en",
            "es",
            terminology=book,
            context=context,
        )

        self.assertEqual(prepared.text, "Please check the work order. Next step!")
        self.assertEqual(prepared.source_language, "en")
        self.assertEqual(prepared.target_language, "es")
        self.assertEqual(prepared.segments, ("Please check the work order.", "Next step!"))
        self.assertEqual(prepared.terminology[0].target, "orden de trabajo")
        self.assertEqual(prepared.context[0].text, "Previous order 1038.")
        self.assertEqual(len(context.snapshot()), 1)

    def test_prepare_rejects_empty_text_or_language_codes(self):
        for args in [
            ("", "en", "es"),
            ("hello", "", "es"),
            ("hello", "en", ""),
        ]:
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    prepare_translation_input(*args)


if __name__ == "__main__":
    unittest.main()
