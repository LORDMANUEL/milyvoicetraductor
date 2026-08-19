"""Contratos de latencia para traducción parcial en equipos CPU modestos."""

from __future__ import annotations

import unittest

from mily_ai.pipeline import TranslationRequest, partial_translation_ready
from mily_ai.queueing import serial_translation_action


def request(kind: str, text: str) -> TranslationRequest:
    return TranslationRequest(
        type=kind,
        start=0.0,
        end=1.0,
        original=text,
        language="en",
        utterance_id="u-1",
        created_at=1.0,
    )


class TranslationLatencyPolicyTests(unittest.TestCase):
    def test_mandarin_stable_prefix_can_translate_without_spaces(self):
        self.assertTrue(partial_translation_ready("你好", "zh"))
        self.assertTrue(partial_translation_ready("请确认", "zh"))

    def test_english_partial_requires_useful_context(self):
        self.assertFalse(partial_translation_ready("I don't", "en"))
        self.assertTrue(partial_translation_ready("I don't agree", "en"))

    def test_serial_cpu_runs_partial_when_only_one_audio_chunk_is_waiting(self):
        action = serial_translation_action(
            request("translation.partial", "I don't agree"),
            audio_queue_ms=100,
        )
        self.assertEqual(action, "run")

    def test_serial_cpu_drops_partial_when_audio_backlog_is_material(self):
        action = serial_translation_action(
            request("translation.partial", "I don't agree"),
            audio_queue_ms=200,
        )
        self.assertEqual(action, "drop")

    def test_serial_cpu_final_is_never_dropped(self):
        action = serial_translation_action(
            request("translation.final", "Do not cancel order 1038"),
            audio_queue_ms=500,
        )
        self.assertEqual(action, "defer")


if __name__ == "__main__":
    unittest.main()
