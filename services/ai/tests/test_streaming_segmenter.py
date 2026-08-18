"""TDD del segmentador de conversación de baja latencia."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from mily_ai.streaming import AdaptiveSpeechSegmenter, default_partial_step_ms


class StreamingSegmenterTests(unittest.TestCase):
    def make_segmenter(self) -> AdaptiveSpeechSegmenter:
        return AdaptiveSpeechSegmenter(
            sample_rate=100,
            first_decode_ms=900,
            partial_step_ms=450,
            finalize_silence_ms=250,
            max_utterance_ms=2400,
            energy_threshold=0.02,
        )

    def test_pure_silence_never_requests_asr(self):
        segmenter = self.make_segmenter()
        for _ in range(30):
            self.assertEqual(segmenter.push([0.0] * 10), [])
        self.assertFalse(segmenter.speech_active)

    def test_first_partial_arrives_before_old_two_second_window(self):
        segmenter = self.make_segmenter()
        events = []
        for _ in range(10):
            events.extend(segmenter.push([0.2] * 10))

        self.assertTrue(events)
        self.assertEqual(events[0].kind, "partial")
        self.assertGreaterEqual(len(events[0].samples), 90)
        self.assertLess(len(events[0].samples), 200)

    def test_silence_finalizes_active_utterance(self):
        segmenter = self.make_segmenter()
        events = []
        for _ in range(10):
            events.extend(segmenter.push([0.2] * 10))
        for _ in range(3):
            events.extend(segmenter.push([0.0] * 10))

        finals = [event for event in events if event.kind == "final"]
        self.assertEqual(len(finals), 1)
        self.assertGreaterEqual(len(finals[0].samples), 100)
        self.assertFalse(segmenter.speech_active)

    def test_long_speech_is_bounded_by_hard_cap(self):
        segmenter = self.make_segmenter()
        events = []
        for _ in range(30):
            events.extend(segmenter.push([0.25] * 10))

        finals = [event for event in events if event.kind == "final"]
        self.assertTrue(finals)
        self.assertLessEqual(len(finals[0].samples), 240)

    def test_audio_level_reports_rms_and_silence_duration(self):
        segmenter = self.make_segmenter()
        segmenter.push([0.0] * 10)
        silent = segmenter.level
        self.assertAlmostEqual(silent.rms, 0.0)
        self.assertGreaterEqual(silent.silent_ms, 100)

        segmenter.push([0.5] * 10)
        active = segmenter.level
        self.assertGreater(active.rms, 0.49)
        self.assertEqual(active.silent_ms, 0)

    def test_dual_core_default_keeps_fast_first_decode_but_spaces_partial_redecodes(self):
        with patch.dict(os.environ, {"MILY_PHYSICAL_CPUS": "2"}, clear=False):
            segmenter = AdaptiveSpeechSegmenter(
                sample_rate=100,
                first_decode_ms=900,
                partial_step_ms=None,
                finalize_silence_ms=250,
                max_utterance_ms=2400,
                energy_threshold=0.02,
            )
        self.assertEqual(segmenter.first_decode_samples, 90)
        self.assertEqual(segmenter.partial_step_samples, 70)

    def test_four_core_default_retains_aggressive_partial_refresh(self):
        self.assertEqual(default_partial_step_ms(4), 450)
        self.assertEqual(default_partial_step_ms(8), 450)

    def test_one_or_two_core_default_uses_legacy_partial_refresh(self):
        self.assertEqual(default_partial_step_ms(1), 700)
        self.assertEqual(default_partial_step_ms(2), 700)

    def test_partial_decoding_can_be_suspended_without_losing_final_utterance(self):
        segmenter = self.make_segmenter()
        segmenter.set_partial_decoding(False)
        events = []
        for _ in range(12):
            events.extend(segmenter.push([0.2] * 10))
        self.assertFalse(any(event.kind == "partial" for event in events))

        for _ in range(3):
            events.extend(segmenter.push([0.0] * 10))
        finals = [event for event in events if event.kind == "final"]
        self.assertEqual(len(finals), 1)
        self.assertGreaterEqual(len(finals[0].samples), 120)

    def test_partial_decoding_can_recover_after_pressure(self):
        segmenter = self.make_segmenter()
        segmenter.set_partial_decoding(False)
        for _ in range(12):
            segmenter.push([0.2] * 10)
        for _ in range(3):
            segmenter.push([0.0] * 10)

        segmenter.set_partial_decoding(True)
        events = []
        for _ in range(10):
            events.extend(segmenter.push([0.2] * 10))
        self.assertTrue(any(event.kind == "partial" for event in events))


if __name__ == "__main__":
    unittest.main()
