import unittest

from mily_ai.betaalpha_optimization import (
    AdaptiveStreamingController,
    ComputeTypeSelector,
    EngineCandidate,
    EngineResidencyPolicy,
    IncrementalTranslationPlanner,
    VadGate,
    rank_engine_candidates,
)


class BetaAlphaOptimizationTests(unittest.TestCase):
    def test_streaming_interval_tracks_rtf_pressure(self):
        ctl = AdaptiveStreamingController()
        self.assertLessEqual(ctl.interval_ms(rtf_p95=0.25, pressure=False), 300)
        self.assertGreaterEqual(ctl.interval_ms(rtf_p95=0.75, pressure=False), 650)
        self.assertGreaterEqual(ctl.interval_ms(rtf_p95=0.4, pressure=True), 700)

    def test_incremental_translation_reuses_stable_prefix(self):
        planner = IncrementalTranslationPlanner()
        first = planner.plan("good morning", "en")
        self.assertEqual(first.text_to_translate, "good morning")
        planner.commit(first, "buenos días")
        second = planner.plan("good morning everybody", "en")
        self.assertEqual(second.stable_source_prefix, "good morning")
        self.assertEqual(second.text_to_translate, "everybody")
        self.assertEqual(second.stable_translation_prefix, "buenos días")

    def test_vad_rejects_silence_and_keeps_preroll(self):
        gate = VadGate(sample_rate=16000, preroll_ms=160, rms_threshold=0.01)
        self.assertFalse(gate.should_process([0.0] * 3200))
        gate.push([0.02] * 3200)
        self.assertTrue(gate.should_process([0.02] * 3200))
        self.assertGreater(len(gate.preroll()), 0)

    def test_engine_score_rewards_latency_memory_quality_and_stability(self):
        fast = EngineCandidate("fast", latency_ms=300, memory_mb=650, quality=0.90, stability=0.99)
        slow = EngineCandidate("slow", latency_ms=700, memory_mb=900, quality=0.92, stability=0.99)
        self.assertEqual(rank_engine_candidates([slow, fast])[0].engine_id, "fast")

    def test_residency_keeps_only_one_asr_hot(self):
        policy = EngineResidencyPolicy()
        policy.activate_asr("moonshine")
        policy.activate_asr("whisper-tiny")
        self.assertEqual(policy.active_asr, "whisper-tiny")
        self.assertEqual(policy.evicted, ["moonshine"])

    def test_compute_type_selector_prefers_supported_benchmarked_winner(self):
        selector = ComputeTypeSelector()
        chosen = selector.choose(
            supported={"int8", "int8_float32", "int16"},
            timings_ms={"int8": 15.0, "int8_float32": 11.0, "int16": 18.0},
        )
        self.assertEqual(chosen, "int8_float32")


if __name__ == "__main__":
    unittest.main()
