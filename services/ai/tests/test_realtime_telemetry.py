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

        snapshot = telemetry.snapshot(
            audio_queue_ms=300, translation_queue_depth=1
        )
        self.assertGreater(snapshot.asr_p50_ms, 0)
        self.assertGreaterEqual(snapshot.asr_p95_ms, snapshot.asr_p50_ms)
        self.assertGreater(snapshot.translation_p50_ms, 0)
        self.assertLess(snapshot.real_time_factor, 1.0)
        self.assertGreaterEqual(
            snapshot.real_time_factor_p95,
            snapshot.real_time_factor,
        )
        self.assertAlmostEqual(snapshot.real_time_factor_p95, 0.8)

    def test_rtf_p95_exposes_spikes_hidden_by_the_median(self):
        telemetry = RealtimeTelemetry(max_samples=8)
        for elapsed_ms in (300.0, 320.0, 340.0, 360.0, 1800.0):
            telemetry.record_asr(elapsed_ms, audio_ms=1000.0)
        snapshot = telemetry.snapshot(audio_queue_ms=0, translation_queue_depth=0)
        self.assertLess(snapshot.real_time_factor, 0.85)
        self.assertGreaterEqual(snapshot.real_time_factor_p95, 1.8)
        controller = LatencyController()
        self.assertEqual(
            controller.classify(
                0,
                0,
                snapshot.real_time_factor_p95,
                process_memory_mb=900.0,
            ),
            "rescue",
        )

    def test_controller_classifies_all_four_resource_states(self):
        controller = LatencyController()
        self.assertEqual(
            controller.classify(
                200,
                1,
                0.5,
                translation_queue_age_ms=150,
                process_memory_mb=900,
            ),
            "healthy",
        )
        self.assertEqual(
            controller.classify(
                650,
                3,
                0.9,
                translation_queue_age_ms=800,
                process_memory_mb=1350,
            ),
            "pressure",
        )
        self.assertEqual(
            controller.classify(
                1500,
                6,
                1.4,
                translation_queue_age_ms=1500,
                process_memory_mb=1750,
            ),
            "catch_up",
        )
        self.assertEqual(
            controller.classify(
                2600,
                8,
                1.9,
                translation_queue_age_ms=2600,
                process_memory_mb=2010,
            ),
            "rescue",
        )

    def test_memory_alone_can_force_rescue_before_two_gib(self):
        controller = LatencyController()
        self.assertEqual(
            controller.classify(
                0,
                0,
                0.1,
                translation_queue_age_ms=0,
                process_memory_mb=1950,
            ),
            "rescue",
        )

    def test_controller_samples_process_tree_and_product_reserve(self):
        calls = []

        def memory_provider():
            calls.append(True)
            return 1650.0

        controller = LatencyController(
            memory_provider=memory_provider,
            product_reserve_mb=320.0,
            memory_sample_interval_seconds=60.0,
        )
        self.assertEqual(controller.classify(0, 0, 0.1), "rescue")
        self.assertEqual(controller.last_process_memory_mb, 1970.0)
        # La segunda clasificación reutiliza la muestra y no recorre procesos
        # por cada chunk de audio.
        self.assertEqual(controller.classify(0, 0, 0.1), "rescue")
        self.assertEqual(len(calls), 1)

    def test_partial_translation_is_optional_outside_healthy(self):
        controller = LatencyController()
        self.assertTrue(controller.allow_partial_translation("healthy"))
        for state in ("pressure", "catch_up", "rescue"):
            with self.subTest(state=state):
                self.assertFalse(controller.allow_partial_translation(state))

    def test_partial_asr_survives_pressure_but_not_catch_up_or_rescue(self):
        controller = LatencyController()
        self.assertTrue(controller.allow_partial_asr("healthy"))
        self.assertTrue(controller.allow_partial_asr("pressure"))
        self.assertFalse(controller.allow_partial_asr("catch_up"))
        self.assertFalse(controller.allow_partial_asr("rescue"))

    def test_expensive_features_are_disabled_progressively(self):
        controller = LatencyController()
        self.assertTrue(controller.allow_speaker_detection("healthy"))
        self.assertFalse(controller.allow_speaker_detection("pressure"))
        self.assertFalse(controller.allow_word_timestamps("catch_up"))
        self.assertFalse(controller.allow_tts("rescue"))


if __name__ == "__main__":
    unittest.main()
