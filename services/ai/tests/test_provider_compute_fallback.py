from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from mily_ai.cpu_budget import CpuBudget
from mily_ai.providers import FasterWhisperAsr, M2M100CTranslate2Translator


BUDGET = CpuBudget(
    profile="legacy",
    physical_cores=2,
    asr_threads=1,
    translation_threads=1,
    parallel_stages=False,
)


class ProviderComputeFallbackTests(unittest.TestCase):
    def test_faster_whisper_auto_falls_back_to_cpu_if_cuda_constructor_fails(self):
        calls: list[str] = []

        class FakeWhisperModel:
            def __init__(self, _path, *, device, **_kwargs):
                calls.append(device)
                if device == "cuda":
                    raise RuntimeError("CUDA driver mismatch")

        fake_faster_whisper = types.SimpleNamespace(WhisperModel=FakeWhisperModel)
        fake_ct2 = types.SimpleNamespace(get_cuda_device_count=lambda: 1)

        with tempfile.TemporaryDirectory() as directory, patch.dict(
            sys.modules,
            {"faster_whisper": fake_faster_whisper, "ctranslate2": fake_ct2},
        ):
            provider = FasterWhisperAsr(Path(directory), "auto", cpu_budget=BUDGET)
            provider._load()

        self.assertEqual(calls, ["cuda", "cpu"])
        self.assertEqual(provider.selected_device, "cpu")
        self.assertTrue(provider.fallback_used)

    def test_m2m100_auto_falls_back_to_cpu_if_cuda_constructor_fails(self):
        calls: list[str] = []

        class FakeTranslator:
            def __init__(self, _path, *, device, **_kwargs):
                calls.append(device)
                if device == "cuda":
                    raise OSError("CUDA DLL could not load")

        class FakeTokenizer:
            @classmethod
            def from_pretrained(cls, _path, **_kwargs):
                return cls()

        fake_ct2 = types.SimpleNamespace(
            get_cuda_device_count=lambda: 1,
            Translator=FakeTranslator,
        )
        fake_transformers = types.SimpleNamespace(AutoTokenizer=FakeTokenizer)

        with tempfile.TemporaryDirectory() as directory, patch.dict(
            sys.modules,
            {"ctranslate2": fake_ct2, "transformers": fake_transformers},
        ):
            provider = M2M100CTranslate2Translator(
                Path(directory), "auto", cpu_budget=BUDGET
            )
            provider._load()

        self.assertEqual(calls, ["cuda", "cpu"])
        self.assertEqual(provider.selected_device, "cpu")
        self.assertTrue(provider.fallback_used)


if __name__ == "__main__":
    unittest.main()
