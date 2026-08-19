import tempfile
import unittest
from pathlib import Path

from mily_ai.cloud_providers import GoogleChirpV2Asr
from mily_ai.cpu_budget import detect_cpu_budget
from mily_ai.optional_providers import CTranslate2MarianTranslator, SherpaOnnxAsr
from mily_ai.provider_factory import (
    ProviderConfigurationError,
    build_asr_provider,
    build_translation_provider,
)
from mily_ai.providers import FasterWhisperAsr
from mily_ai.safe_optional_providers import MoonshineResultAsr, WhisperCppBridgeAsr
from mily_ai.vosk_provider import VoskAsr


class ProviderFactoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.budget = detect_cpu_budget("light", physical_cores=2)

    def tearDown(self):
        self.temp.cleanup()

    def test_all_asr_engines_have_registered_adapters(self):
        expected = {
            "faster-whisper": FasterWhisperAsr,
            "moonshine": MoonshineResultAsr,
            "sherpa-onnx": SherpaOnnxAsr,
            "whisper-cpp": WhisperCppBridgeAsr,
            "vosk": VoskAsr,
            "google-chirp": GoogleChirpV2Asr,
        }
        for provider, expected_type in expected.items():
            with self.subTest(provider=provider):
                built = build_asr_provider({"provider": provider}, self.path, "cpu", self.budget, False)
                self.assertIsInstance(built, expected_type)

    def test_marian_provider_is_direct_and_target_aware(self):
        built = build_translation_provider({"provider":"marian-ct2","sourceLanguage":"en","targetLanguage":"es"}, self.path, "cpu", self.budget)
        self.assertIsInstance(built, CTranslate2MarianTranslator)
        self.assertEqual(built.source_language, "en")
        self.assertEqual(built.target_language, "es")

    def test_unknown_provider_is_rejected_before_model_load(self):
        with self.assertRaises(ProviderConfigurationError):
            build_asr_provider({"provider":"mystery"}, self.path, "cpu", self.budget, False)
        with self.assertRaises(ProviderConfigurationError):
            build_translation_provider({"provider":"mystery"}, self.path, "cpu", self.budget)


if __name__ == "__main__":
    unittest.main()
