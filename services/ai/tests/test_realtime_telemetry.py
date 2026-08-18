"""Pruebas de métricas y presión del pipeline realtime."""

from __future__ import annotations

import unittest

from mily_ai.telemetry import LatencyController, RealtimeTelemetry


class RealtimeTelemetryTests(unittest.TestCase):
    def test_percentiles_and_rtf_are_local_and_bounded(self):
        telemetry = RealtimeTelemetry(max_samples=8)
        telemetry.record_asr(400.0, audio_ms=1000.0)
        telemetry.record_asr(800.0, audio_ms=1000.0)
        telemetry.record_translation(120.0)
        telemetry.record_translation(240.0)

        snapshot = telemetry.snapshot(audio_queue_ms=300, translation_queue_depth=1)
        self.assertGreater(snapshot.asr_p50_ms, 0)
        self.assertGreaterEqual(snapshot.asr_p95_ms, snapshot.asr_p50_ms)
        self.assertGreater(snapshot.translation_p50_ms, 0)
        self.assertLess(snapshot.real_time_factor, 1.0)

    def test_controller_classifies_healthy_pressure_and_overloaded(self):
        controller = LatencyController()
        self.assertEqual(controller.classify(200, 1, 0.5), "healthy")
        self.assertEqual(controller.classify(800, 4, 1.0), "pressure")
        self.assertEqual(controller.classify(1800, 7, 1.6), "overloaded")

    def test_partial_translation_is_optional_under_pressure(self):
        controller = LatencyController()
        self.assertTrue(controller.allow_partial_translation("healthy"))
        self.assertFalse(controller.allow_partial_translation("pressure"))
        self.assertFalse(controller.allow_partial_translation("overloaded"))


if __name__ == "__main__":
    unittest.main()
