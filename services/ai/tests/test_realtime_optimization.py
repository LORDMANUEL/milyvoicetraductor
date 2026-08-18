import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from mily_ai.cpu_budget import CpuBudget
from mily_ai.models import ModelCatalog, _convert_m2m100_to_ctranslate2
from mily_ai.providers import (
    CachedTranslator,
    FasterWhisperAsr,
    M2M100CTranslate2Translator,
    Translator,
)


class FakeTranslator(Translator):
    def __init__(self):
        self.calls = 0

    def translate(self, text: str, source_language: str) -> str:
        self.calls += 1
        return f"{source_language}:{text}"


class FakeTransformersConverter:
    def __init__(self, source, copy_files=None):
        self.source = Path(source)
        self.copy_files = list(copy_files or [])

    def convert(self, output_dir, quantization, force):
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        (target / "model.bin").write_bytes(b"ct2")
        (target / "config.json").write_text(
            '{"model_type":"Transformer"}', encoding="utf-8"
        )


class RecordingWhisperModel:
    last_args = None
    last_kwargs = None

    def __init__(self, *args, **kwargs):
        type(self).last_args = args
        type(self).last_kwargs = kwargs


class RecordingCt2Translator:
    last_args = None
    last_kwargs = None

    def __init__(self, *args, **kwargs):
        type(self).last_args = args
        type(self).last_kwargs = kwargs


class FakeAutoTokenizer:
    @classmethod
    def from_pretrained(cls, *_args, **_kwargs):
        return cls()


class RealtimeOptimizationTests(unittest.TestCase):
    def test_translation_cache_avoids_recomputing_overlap_text(self):
        inner = FakeTranslator()
        translator = CachedTranslator(inner, max_entries=4)

        first = translator.translate("  Hello   world  ", "en")
        second = translator.translate("Hello world", "en")

        self.assertEqual(first, second)
        self.assertEqual(inner.calls, 1)

    def test_translation_cache_keeps_languages_separate(self):
        inner = FakeTranslator()
        translator = CachedTranslator(inner, max_entries=4)

        translator.translate("hola", "en")
        translator.translate("hola", "zh")

        self.assertEqual(inner.calls, 2)

    def test_whisper_uses_budgeted_cpu_threads(self):
        budget = CpuBudget(
            profile="balanced",
            physical_cores=8,
            asr_threads=5,
            translation_threads=2,
            parallel_stages=True,
        )
        fake_whisper = types.SimpleNamespace(WhisperModel=RecordingWhisperModel)
        fake_ct2 = types.SimpleNamespace(get_cuda_device_count=lambda: 0)
        with patch.dict(
            sys.modules,
            {"faster_whisper": fake_whisper, "ctranslate2": fake_ct2},
        ):
            provider = FasterWhisperAsr(Path("asr"), "cpu", cpu_budget=budget)
            provider._load()

        self.assertEqual(RecordingWhisperModel.last_kwargs["device"], "cpu")
        self.assertEqual(RecordingWhisperModel.last_kwargs["compute_type"], "int8")
        self.assertEqual(RecordingWhisperModel.last_kwargs["cpu_threads"], 5)
        self.assertEqual(RecordingWhisperModel.last_kwargs["num_workers"], 1)

    def test_m2m100_uses_budgeted_cpu_threads(self):
        budget = CpuBudget(
            profile="balanced",
            physical_cores=8,
            asr_threads=5,
            translation_threads=2,
            parallel_stages=True,
        )
        fake_ct2 = types.SimpleNamespace(
            get_cuda_device_count=lambda: 0,
            Translator=RecordingCt2Translator,
        )
        fake_transformers = types.SimpleNamespace(AutoTokenizer=FakeAutoTokenizer)
        with patch.dict(
            sys.modules,
            {"ctranslate2": fake_ct2, "transformers": fake_transformers},
        ):
            provider = M2M100CTranslate2Translator(
                Path("translation"), "cpu", cpu_budget=budget
            )
            provider._load()

        self.assertEqual(RecordingCt2Translator.last_kwargs["device"], "cpu")
        self.assertEqual(RecordingCt2Translator.last_kwargs["compute_type"], "int8")
        self.assertEqual(RecordingCt2Translator.last_kwargs["inter_threads"], 1)
        self.assertEqual(RecordingCt2Translator.last_kwargs["intra_threads"], 2)

    def test_realtime_commercial_pack_uses_m2m100_ctranslate2_int8(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalog = ModelCatalog(Path(tmp))
            pack = catalog.definition("realtime-m2m100")

        self.assertTrue(pack["commercialUse"])
        translation = pack["components"]["translation"]
        self.assertEqual(translation["provider"], "m2m100-ct2")
        self.assertEqual(translation["quantization"], "int8")
        self.assertEqual(translation["repoId"], "facebook/m2m100_418M")
        self.assertNotEqual(translation["revision"], "main")
        self.assertIn("pytorch_model.bin", translation["allowPatterns"])
        self.assertNotIn("rust_model.ot", translation["allowPatterns"])

    def test_ct2_conversion_keeps_hf_tokenizer_in_separate_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "translation"
            source.mkdir()
            (source / "pytorch_model.bin").write_bytes(b"weights")
            (source / "config.json").write_text(
                '{"model_type":"m2m_100"}', encoding="utf-8"
            )
            (source / "sentencepiece.bpe.model").write_bytes(b"spm")
            (source / "vocab.json").write_text("{}", encoding="utf-8")
            (source / "tokenizer_config.json").write_text(
                '{"tokenizer_class":"M2M100Tokenizer"}', encoding="utf-8"
            )
            (source / "special_tokens_map.json").write_text("{}", encoding="utf-8")

            fake_ct2 = types.SimpleNamespace(
                converters=types.SimpleNamespace(TransformersConverter=FakeTransformersConverter)
            )
            with patch.dict(sys.modules, {"ctranslate2": fake_ct2}):
                _convert_m2m100_to_ctranslate2(source, "int8")

            self.assertTrue((source / "model.bin").is_file())
            self.assertEqual(
                (source / "config.json").read_text(encoding="utf-8"),
                '{"model_type":"Transformer"}',
            )
            tokenizer = source / "tokenizer"
            self.assertEqual(
                (tokenizer / "config.json").read_text(encoding="utf-8"),
                '{"model_type":"m2m_100"}',
            )
            self.assertTrue((tokenizer / "sentencepiece.bpe.model").is_file())
            self.assertFalse((source / "pytorch_model.bin").exists())


if __name__ == "__main__":
    unittest.main()
