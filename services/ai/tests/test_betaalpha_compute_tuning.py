import json
import tempfile
import unittest
from pathlib import Path

from mily_ai.ctranslate2_tuning import CTranslate2ComputeTuner
from mily_ai.cpu_budget import detect_cpu_budget


class _FakeTranslator:
    def __init__(self, compute_type, timings, calls):
        self.compute_type = compute_type
        self.timings = timings
        self.calls = calls
        self.unloaded = False

    def benchmark_once(self, _tokens):
        self.calls.append(self.compute_type)
        return self.timings[self.compute_type]

    def unload_model(self, to_cpu=False):
        self.unloaded = True


class BetaAlphaComputeTuningTests(unittest.TestCase):
    def test_tuner_benchmarks_supported_types_and_persists_winner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / "model"
            model.mkdir()
            (model / "model.bin").write_bytes(b"model")
            calls = []
            timings = {
                "int8_float32": 11.0,
                "int8": 7.5,
                "int16": 9.0,
            }

            def factory(compute_type):
                return _FakeTranslator(compute_type, timings, calls)

            tuner = CTranslate2ComputeTuner(root / "cache.json")
            result = tuner.choose(
                model_path=model,
                source_language="en",
                supported={"int8_float32", "int8", "int16"},
                budget=detect_cpu_budget("light", physical_cores=2),
                translator_factory=factory,
                probe_tokens=["▁Hello", "."],
                benchmark=lambda translator, tokens: translator.benchmark_once(tokens),
            )
            self.assertEqual(result.compute_type, "int8")
            self.assertEqual(set(calls), {"int8_float32", "int8", "int16"})
            payload = json.loads((root / "cache.json").read_text(encoding="utf-8"))
            self.assertEqual(next(iter(payload["entries"].values()))["computeType"], "int8")

            calls.clear()
            cached = tuner.choose(
                model_path=model,
                source_language="en",
                supported={"int8_float32", "int8", "int16"},
                budget=detect_cpu_budget("light", physical_cores=2),
                translator_factory=factory,
                probe_tokens=["▁Hello", "."],
                benchmark=lambda translator, tokens: translator.benchmark_once(tokens),
            )
            self.assertEqual(cached.compute_type, "int8")
            self.assertTrue(cached.cached)
            self.assertEqual(calls, [])

    def test_invalid_or_missing_cache_never_blocks_safe_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root / "cache.json"
            cache.write_text("not-json", encoding="utf-8")
            model = root / "model"
            model.mkdir()
            (model / "model.bin").write_bytes(b"model")
            tuner = CTranslate2ComputeTuner(cache)
            result = tuner.choose(
                model_path=model,
                source_language="zh",
                supported={"int8"},
                budget=detect_cpu_budget("light", physical_cores=1),
                translator_factory=lambda kind: _FakeTranslator(kind, {"int8": 5.0}, []),
                probe_tokens=["你", "好"],
                benchmark=lambda translator, tokens: translator.benchmark_once(tokens),
            )
            self.assertEqual(result.compute_type, "int8")


if __name__ == "__main__":
    unittest.main()
