"""Contrato de diagnóstico del backend realmente usado por MilyCompute."""

from __future__ import annotations

import unittest

from mily_ai.pipeline import RealtimePipeline


class _FakeProvider:
    def __init__(self, device: str, fallback: bool, reason: str = ""):
        self.selected_device = device
        self.fallback_used = fallback
        self.fallback_reason = reason


class ComputeObservabilityTests(unittest.TestCase):
    def test_pipeline_reports_actual_asr_and_translation_devices(self):
        pipeline = RealtimePipeline.__new__(RealtimePipeline)
        pipeline.asr = _FakeProvider("cpu", True, "RuntimeError")
        pipeline._translator_provider = _FakeProvider("cuda", False)

        status = pipeline.compute_status

        self.assertEqual(status["asrDevice"], "cpu")
        self.assertEqual(status["translationDevice"], "cuda")
        self.assertTrue(status["fallbackUsed"])
        self.assertTrue(status["asrFallbackUsed"])
        self.assertFalse(status["translationFallbackUsed"])
        self.assertEqual(status["asrFallbackReason"], "RuntimeError")
        self.assertEqual(status["translationFallbackReason"], "")

    def test_unknown_provider_is_reported_without_claiming_gpu(self):
        pipeline = RealtimePipeline.__new__(RealtimePipeline)
        pipeline.asr = object()
        pipeline._translator_provider = object()

        status = pipeline.compute_status

        self.assertEqual(status["asrDevice"], "unknown")
        self.assertEqual(status["translationDevice"], "unknown")
        self.assertFalse(status["fallbackUsed"])


if __name__ == "__main__":
    unittest.main()
