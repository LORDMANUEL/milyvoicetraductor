"""TDD del segmentador de conversación de baja latencia."""

from __future__ import annotations

import unittest

from mily_ai.streaming import AdaptiveSpeechSegmenter


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


if __name__ == "__main__":
    unittest.main()
