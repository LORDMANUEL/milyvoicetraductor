import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mily_ai.engine_benchmark import benchmark_installed_pack
from mily_ai.models import InstalledPack
from mily_ai.providers import AsrSegment


class FakeAsr:
    def __init__(self, device):
        self.selected_device = device

    def warm_up(self, _language):
        pass

    def transcribe(self, _audio, language):
        return [AsrSegment(0.0, 1.0, "hello world", language)]

    def unload(self):
        self.selected_device = None


class FakeTranslator:
    def __init__(self, device):
        self.selected_device = device

    def warm_up(self):
        pass

    def translate(self, _text, _language):
        return "hola mundo"

    def unload(self):
        self.selected_device = None


class EngineBenchmarkBackendTruthTests(unittest.TestCase):
    @staticmethod
    def definition():
        return {
            "tier": "lite",
            "routes": ["en-es"],
            "ramMb": 900,
            "vramMb": 300,
            "supportedBackends": ["cuda", "cpu"],
            "components": {
                "asr": {"provider": "fake"},
                "translation": {"provider": "fake"},
            },
        }

    def _run(self, asr_device, translation_device, requested):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "components" / "asr").mkdir(parents=True)
            (path / "components" / "translation").mkdir(parents=True)
            pack = InstalledPack("adaptive", "1", path, False, "Adaptive", True)
            with patch(
                "mily_ai.engine_benchmark.build_asr_provider",
                return_value=FakeAsr(asr_device),
            ), patch(
                "mily_ai.engine_benchmark.build_translation_provider",
                return_value=FakeTranslator(translation_device),
            ), patch(
                "mily_ai.engine_benchmark.process_memory_snapshot_mb",
                return_value=(600.0, 700.0),
            ):
                return benchmark_installed_pack(
                    pack,
                    self.definition(),
                    compute_profile=requested,
                    repeats=3,
                    audio_samples=[0.1] * 16000,
                )

    def test_cuda_request_that_falls_back_to_cpu_is_rejected(self):
        report = self._run("cpu", "cpu", "cuda")
        self.assertFalse(report["passed"])
        self.assertEqual(report["backend"], "unverified")
        self.assertEqual(report["asrBackend"], "cpu")
        self.assertEqual(report["translationBackend"], "cpu")
        self.assertIn("BACKEND_MISMATCH", report["failures"])

    def test_measured_cuda_is_recorded_before_provider_unload(self):
        report = self._run("cuda", "cpu", "cuda")
        self.assertTrue(report["passed"])
        self.assertEqual(report["backend"], "cuda")
        self.assertEqual(report["asrBackend"], "cuda")
        self.assertEqual(report["translationBackend"], "cpu")


if __name__ == "__main__":
    unittest.main()
