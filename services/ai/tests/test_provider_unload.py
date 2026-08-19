import tempfile
import unittest
from pathlib import Path

from mily_ai.pipeline import RealtimePipeline
from mily_ai.providers import (
    CachedTranslator,
    FasterWhisperAsr,
    M2M100CTranslate2Translator,
    NllbTranslator,
    QwenTranslator,
    Translator,
)


class DummyCt2Backend:
    def __init__(self):
        self.calls = 0

    def unload_model(self, to_cpu=False):
        self.calls += 1


class DummyWhisperModel:
    def __init__(self, backend):
        self.model = backend


class DummyTranslator(Translator):
    def __init__(self):
        self.unloaded = 0

    def translate(self, text, source_language):
        return text

    def unload(self):
        self.unloaded += 1


class ProviderUnloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_cached_translator_clears_cache_and_delegates_unload(self):
        inner = DummyTranslator()
        cached = CachedTranslator(inner)
        self.assertEqual(cached.translate("hello", "en"), "hello")
        self.assertEqual(len(cached._cache), 1)
        cached.unload()
        self.assertEqual(len(cached._cache), 0)
        self.assertEqual(inner.unloaded, 1)

    def test_faster_whisper_releases_ctranslate2_model(self):
        backend = DummyCt2Backend()
        provider = FasterWhisperAsr(self.path)
        provider._model = DummyWhisperModel(backend)
        provider._warmed = True
        provider._locked_language = "en"
        provider.selected_device = "cpu"

        provider.unload()

        self.assertEqual(backend.calls, 1)
        self.assertIsNone(provider._model)
        self.assertIsNone(provider._locked_language)
        self.assertIsNone(provider.selected_device)
        self.assertFalse(provider._warmed)

    def test_m2m100_releases_model_and_tokenizer(self):
        backend = DummyCt2Backend()
        provider = M2M100CTranslate2Translator(self.path)
        provider._translator = backend
        provider._tokenizer = object()
        provider._warmed = True
        provider.selected_device = "cpu"

        provider.unload()

        self.assertEqual(backend.calls, 1)
        self.assertIsNone(provider._translator)
        self.assertIsNone(provider._tokenizer)
        self.assertIsNone(provider.selected_device)
        self.assertFalse(provider._warmed)

    def test_torch_quality_providers_drop_model_and_tokenizer(self):
        for provider in (NllbTranslator(self.path), QwenTranslator(self.path)):
            with self.subTest(provider=provider.__class__.__name__):
                provider._model = object()
                provider._tokenizer = object()
                provider._device = "cpu"
                provider.unload()
                self.assertIsNone(provider._model)
                self.assertIsNone(provider._tokenizer)
                self.assertEqual(provider._device, "cpu")

    def test_pipeline_unloads_cached_translator_not_only_inner_provider(self):
        asr = DummyTranslator()
        translator = DummyTranslator()
        cached = CachedTranslator(translator)
        cached.translate("cached", "en")
        pipeline = object.__new__(RealtimePipeline)
        pipeline.asr = asr
        pipeline._translator_provider = translator
        pipeline.translator = cached

        pipeline.unload()

        self.assertEqual(asr.unloaded, 1)
        self.assertEqual(translator.unloaded, 1)
        self.assertEqual(len(cached._cache), 0)


if __name__ == "__main__":
    unittest.main()
