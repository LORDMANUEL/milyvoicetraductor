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
    @staticmethod
    def _pipeline(asr, translator, resource_mode: str = "healthy"):
        pipeline = RealtimePipeline.__new__(RealtimePipeline)
        pipeline.asr = asr
        pipeline._translator_provider = translator
        pipeline._resource_mode = resource_mode
        return pipeline

    def test_pipeline_reports_actual_asr_and_translation_devices(self):
        pipeline = self._pipeline(
            _FakeProvider("cpu", True, "RuntimeError"),
            _FakeProvider("cuda", False),
        )

        status = pipeline.compute_status

        self.assertEqual(status["asrDevice"], "cpu")
        self.assertEqual(status["translationDevice"], "cuda")
        self.assertTrue(status["fallbackUsed"])
        self.assertTrue(status["asrFallbackUsed"])
        self.assertFalse(status["translationFallbackUsed"])
        self.assertEqual(status["asrFallbackReason"], "RuntimeError")
        self.assertEqual(status["translationFallbackReason"], "")
        self.assertEqual(status["resourceMode"], "healthy")

    def test_unknown_provider_is_reported_without_claiming_gpu(self):
        pipeline = self._pipeline(object(), object(), resource_mode="rescue")

        status = pipeline.compute_status

        self.assertEqual(status["asrDevice"], "unknown")
        self.assertEqual(status["translationDevice"], "unknown")
        self.assertFalse(status["fallbackUsed"])
        self.assertEqual(status["resourceMode"], "rescue")


if __name__ == "__main__":
    unittest.main()
