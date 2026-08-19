"""TDD para separar texto parcial de prefijos suficientemente estables."""

from __future__ import annotations

import unittest

from mily_ai.hypothesis import HypothesisStabilizer


class HypothesisStabilizerTests(unittest.TestCase):
    def test_first_hypothesis_is_visible_but_not_stable(self):
        stabilizer = HypothesisStabilizer()
        state = stabilizer.update("I'm going to be there")
        self.assertEqual(state.partial, "I'm going to be there")
        self.assertEqual(state.stable, "")
        self.assertFalse(state.stable_advanced)

    def test_repeated_prefix_becomes_stable(self):
        stabilizer = HypothesisStabilizer()
        stabilizer.update("I'm going to be there")
        state = stabilizer.update("I'm going to be there with you")
        self.assertEqual(state.stable, "I'm going to be there")
        self.assertTrue(state.stable_advanced)

    def test_dangling_english_modal_waits_for_semantic_context(self):
        stabilizer = HypothesisStabilizer()
        stabilizer.update("I don't think we should")
        state = stabilizer.update("I don't think we should cancel")
        self.assertEqual(state.partial, "I don't think we should cancel")
        self.assertEqual(state.stable, "")
        self.assertFalse(state.stable_advanced)

        state = stabilizer.update("I don't think we should cancel it")
        self.assertEqual(state.stable, "I don't think we should cancel")
        self.assertTrue(state.stable_advanced)

    def test_short_english_prefix_does_not_trigger_partial_translation(self):
        stabilizer = HypothesisStabilizer()
        stabilizer.update("we need")
        state = stabilizer.update("we need the")
        self.assertEqual(state.stable, "")
        self.assertFalse(state.stable_advanced)

    def test_unstable_tail_does_not_replace_locked_prefix(self):
        stabilizer = HypothesisStabilizer()
        stabilizer.update("we need the blue part")
        stabilizer.update("we need the blue part today")
        state = stabilizer.update("we need the blue part tomorrow")
        self.assertEqual(state.stable, "we need the blue part")
        self.assertEqual(state.partial, "we need the blue part tomorrow")

    def test_finalize_returns_complete_text_and_resets(self):
        stabilizer = HypothesisStabilizer()
        stabilizer.update("hello my")
        final = stabilizer.finalize("hello my friend")
        self.assertEqual(final, "hello my friend")
        self.assertEqual(stabilizer.update("next phrase").stable, "")

    def test_punctuation_differences_do_not_destroy_word_prefix(self):
        stabilizer = HypothesisStabilizer()
        stabilizer.update("Hello, my friend")
        state = stabilizer.update("Hello my friend today")
        self.assertEqual(state.stable.lower(), "hello my friend")

    def test_han_text_keeps_low_latency_stability(self):
        stabilizer = HypothesisStabilizer()
        stabilizer.update("请确认订单")
        state = stabilizer.update("请确认订单一零三八")
        self.assertTrue(state.stable_advanced)
        self.assertTrue(state.stable)


if __name__ == "__main__":
    unittest.main()
