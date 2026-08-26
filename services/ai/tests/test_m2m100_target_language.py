import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from mily_ai.cpu_budget import detect_cpu_budget
from mily_ai.provider_factory import build_asr_provider, build_translation_provider
from mily_ai.tier1_providers import TargetAwareM2M100CTranslate2Translator, Tier1FasterWhisperAsr


class _FakeTokenizer:
    def __init__(self):
        self.src_lang = None
        self.lang_code_to_token = {"es": "__es__", "en": "__en__", "zh": "__zh__"}

    def encode(self, _text):
        return [1, 2]

    def convert_ids_to_tokens(self, _ids):
        return ["hello", "world"]

    def convert_tokens_to_ids(self, tokens):
        return list(range(len(tokens)))

    def decode(self, _ids, skip_special_tokens=True):
        return "translated"


class _FakeTranslator:
    def __init__(self):
        self.target_prefix = None

    def translate_batch(self, _source, *, target_prefix, **_kwargs):
        self.target_prefix = target_prefix
        return [SimpleNamespace(hypotheses=[["__target__", "translated"]])]


class _FakeWhisperModel:
    def __init__(self):
        self.language = None

    def transcribe(self, _samples, **kwargs):
        self.language = kwargs.get("language")
        return iter(()), SimpleNamespace(language=self.language, language_probability=1.0)


class TargetAwareM2M100Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.budget = detect_cpu_budget("light", physical_cores=2)

    def tearDown(self):
        self.temp.cleanup()

    def test_factory_keeps_requested_target_language_for_m2m100(self):
        translator = build_translation_provider(
            {"provider": "m2m100-ct2"},
            self.path,
            "cpu",
            self.budget,
            target_language="en",
        )
        self.assertIsInstance(translator, TargetAwareM2M100CTranslate2Translator)
        self.assertEqual(translator.target_language, "en")

    def test_translate_uses_target_language_token(self):
        translator = TargetAwareM2M100CTranslate2Translator(
            self.path,
            "cpu",
            cpu_budget=self.budget,
            target_language="zh",
        )
        fake_translator = _FakeTranslator()
        fake_tokenizer = _FakeTokenizer()
        translator._translator = fake_translator
        translator._tokenizer = fake_tokenizer

        result = translator.translate("hello world", "es")

        self.assertEqual(result, "translated")
        self.assertEqual(fake_tokenizer.src_lang, "es")
        self.assertEqual(fake_translator.target_prefix, [["__zh__"]])

    def test_faster_whisper_factory_warmup_preserves_explicit_spanish(self):
        provider = build_asr_provider(
            {"provider": "faster-whisper"},
            self.path,
            "cpu",
            self.budget,
            False,
        )
        self.assertIsInstance(provider, Tier1FasterWhisperAsr)
        fake_model = _FakeWhisperModel()
        provider._model = fake_model

        provider.warm_up("es")

        self.assertEqual(fake_model.language, "es")


if __name__ == "__main__":
    unittest.main()
