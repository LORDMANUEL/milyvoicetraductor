import unittest
from dataclasses import dataclass
from types import SimpleNamespace

from mily_asr import (
    AsrAdapterError,
    MoonshineAsrAdapter,
    SherpaZipformerAsrAdapter,
    WhisperAsrAdapter,
)


@dataclass
class Frame:
    payload: object
    sequence_id: int = 7
    media_start_ns: int = 2_000_000_000
    duration_ns: int = 1_000_000_000
    sample_count: int = 16000
    sample_rate: int = 16000
    channels: int = 1
    sample_format: str = "float32"


@dataclass
class Invocation:
    request_id: str
    route: str
    frame: object
    metadata: dict


class FakeProvider:
    def __init__(self, *, final_api=False):
        self.calls = []
        self.final_calls = []
        self.finish_calls = 0
        self.unload_calls = 0
        self.warmups = []
        self.final_api = final_api

    def warm_up(self, language="en"):
        self.warmups.append(language)

    def transcribe(self, samples, language):
        self.calls.append((samples, language))
        return [
            SimpleNamespace(
                start=0.1,
                end=0.8,
                text=" hello ",
                language="en",
                words=(
                    SimpleNamespace(start=0.1, end=0.4, text="hello"),
                    SimpleNamespace(start=0.4, end=0.8, text="world"),
                ),
            ),
            SimpleNamespace(
                start=0.8,
                end=1.0,
                text=" world ",
                language="en",
                words=(),
            ),
        ]

    def transcribe_final(self, samples, language):
        if not self.final_api:
            raise AttributeError("transcribe_final disabled")
        self.final_calls.append((samples, language))
        return [SimpleNamespace(start=0.0, end=1.0, text="final text", language="en", words=())]

    def finish_utterance(self):
        self.finish_calls += 1

    def unload(self):
        self.unload_calls += 1


class NoFinalProvider:
    def __init__(self):
        self.calls = []
        self.finish_calls = 0
        self.unload_calls = 0

    def transcribe(self, samples, language):
        self.calls.append((samples, language))
        return [SimpleNamespace(start=0.0, end=0.5, text="done", language="en", words=())]

    def finish_utterance(self):
        self.finish_calls += 1

    def unload(self):
        self.unload_calls += 1


class FakeClock:
    def __init__(self, *values):
        self.values = iter(values)

    def __call__(self):
        return next(self.values)


class AsrAdapterTests(unittest.TestCase):
    def adapter(self, cls=WhisperAsrAdapter, *, provider=None, clock=None):
        provider = provider or FakeProvider()
        build_calls = []
        budget_calls = []

        def budget_builder(profile, physical_cores):
            budget = {"profile": profile, "physical": physical_cores}
            budget_calls.append((profile, physical_cores, budget))
            return budget

        def builder(component, model_path, compute_profile, cpu_budget, word_timestamps):
            build_calls.append(
                (dict(component), str(model_path), compute_profile, cpu_budget, word_timestamps)
            )
            return provider

        instance = cls(
            provider_builder=builder,
            cpu_budget_builder=budget_builder,
            clock_ns=clock or FakeClock(100, 200),
        )
        return instance, provider, build_calls, budget_calls

    def test_concrete_adapters_have_stable_promoted_provider_ids(self):
        expected = [
            (WhisperAsrAdapter, "whisper", "faster-whisper"),
            (MoonshineAsrAdapter, "moonshine", "moonshine"),
            (SherpaZipformerAsrAdapter, "sherpa-zipformer", "sherpa-onnx"),
        ]
        for cls, engine_id, provider_id in expected:
            with self.subTest(cls=cls.__name__):
                adapter, *_ = self.adapter(cls)
                self.assertEqual(adapter.engine_id, engine_id)
                self.assertEqual(adapter.provider_id, provider_id)

    def test_load_maps_config_to_existing_provider_factory_signature(self):
        adapter, provider, build_calls, budget_calls = self.adapter()
        adapter.load(
            {
                "modelPath": "C:/models/whisper-tiny",
                "component": {"repoId": "demo/repo"},
                "computeProfile": "cuda",
                "cpuProfile": "light",
                "physicalCores": 2,
                "wordTimestamps": True,
                "warmupLanguage": "en",
            }
        )

        self.assertEqual(budget_calls[0][:2], ("light", 2))
        component, model_path, compute, budget, words = build_calls[0]
        self.assertEqual(component["provider"], "faster-whisper")
        self.assertEqual(component["repoId"], "demo/repo")
        self.assertEqual(model_path, "C:/models/whisper-tiny")
        self.assertEqual(compute, "cuda")
        self.assertIs(budget, budget_calls[0][2])
        self.assertTrue(words)
        self.assertEqual(provider.warmups, ["en"])
        self.assertTrue(adapter.health())

    def test_conflicting_provider_and_missing_model_path_are_rejected(self):
        adapter, *_ = self.adapter()
        with self.assertRaises(AsrAdapterError) as missing:
            adapter.load({})
        self.assertEqual(missing.exception.code, "ASR_MODEL_PATH_REQUIRED")

        with self.assertRaises(AsrAdapterError) as conflict:
            adapter.load(
                {
                    "modelPath": "model",
                    "component": {"provider": "moonshine"},
                }
            )
        self.assertEqual(conflict.exception.code, "ASR_PROVIDER_CONFLICT")

    def test_invoke_preserves_payload_identity_and_normalizes_segments_words_metrics(self):
        payload = [0.0] * 16000
        adapter, provider, *_ = self.adapter(clock=FakeClock(1_000_000_000, 1_250_000_000))
        adapter.load({"modelPath": "model", "warmupLanguage": "en"})
        request = Invocation(
            request_id="req-1",
            route="asr:en",
            frame=Frame(payload),
            metadata={"utteranceId": "utt-7", "sourceLanguage": "en"},
        )

        result = adapter.invoke(request)

        self.assertIs(provider.calls[0][0], payload)
        self.assertEqual(provider.calls[0][1], "en")
        self.assertEqual(result.request_id, "req-1")
        self.assertEqual(result.utterance_id, "utt-7")
        self.assertEqual(result.sequence_id, 7)
        self.assertEqual(result.media_start_ns, 2_000_000_000)
        self.assertEqual(result.media_end_ns, 3_000_000_000)
        self.assertEqual(result.engine_id, "whisper")
        self.assertEqual(result.source_language, "en")
        self.assertEqual(result.detected_language, "en")
        self.assertFalse(result.final)
        self.assertEqual(result.text, "hello world")
        self.assertEqual(len(result.segments), 2)
        self.assertEqual((result.segments[0].start_ms, result.segments[0].end_ms), (100.0, 800.0))
        self.assertEqual(result.segments[0].words[1].text, "world")
        self.assertEqual((result.segments[0].words[1].start_ms, result.segments[0].words[1].end_ms), (400.0, 800.0))
        self.assertEqual(result.metrics.elapsed_ms, 250.0)
        self.assertEqual(result.metrics.audio_duration_ms, 1000.0)
        self.assertEqual(result.metrics.rtf, 0.25)

    def test_final_prefers_provider_transcribe_final_when_available(self):
        provider = FakeProvider(final_api=True)
        adapter, provider, *_ = self.adapter(provider=provider, clock=FakeClock(10, 20))
        adapter.load({"modelPath": "model"})
        payload = [0.0] * 16000

        result = adapter.invoke(
            Invocation(
                request_id="final",
                route="asr:en",
                frame=Frame(payload),
                metadata={"utteranceId": "u", "sourceLanguage": "en", "final": True},
            )
        )

        self.assertIs(provider.final_calls[0][0], payload)
        self.assertEqual(provider.calls, [])
        self.assertEqual(provider.finish_calls, 0)
        self.assertTrue(result.final)
        self.assertEqual(result.text, "final text")

    def test_final_falls_back_to_transcribe_then_finish_utterance(self):
        provider = NoFinalProvider()
        adapter, provider, *_ = self.adapter(provider=provider, clock=FakeClock(10, 20))
        adapter.load({"modelPath": "model"})
        payload = [0.0] * 16000

        result = adapter.invoke(
            Invocation(
                request_id="final",
                route="asr:en",
                frame=Frame(payload),
                metadata={"utteranceId": "u", "sourceLanguage": "en", "final": True},
            )
        )

        self.assertIs(provider.calls[0][0], payload)
        self.assertEqual(provider.finish_calls, 1)
        self.assertTrue(result.final)

    def test_invalid_frame_or_metadata_is_rejected_before_provider_call(self):
        adapter, provider, *_ = self.adapter()
        adapter.load({"modelPath": "model"})
        bad_frames = [
            Frame([0.0], sample_rate=8000),
            Frame([0.0], channels=2),
            Frame([0.0], sample_format="pcm16"),
            Frame([], sample_count=0),
        ]
        for frame in bad_frames:
            with self.subTest(frame=frame):
                with self.assertRaises(AsrAdapterError) as context:
                    adapter.invoke(
                        Invocation("r", "asr", frame, {"utteranceId": "u", "sourceLanguage": "en"})
                    )
                self.assertEqual(context.exception.code, "ASR_WINDOW_INVALID")

        with self.assertRaises(AsrAdapterError) as metadata:
            adapter.invoke(Invocation("r", "asr", Frame([0.0] * 16000), {}))
        self.assertEqual(metadata.exception.code, "ASR_METADATA_INVALID")
        self.assertEqual(provider.calls, [])

    def test_unload_releases_provider_and_health_becomes_false(self):
        adapter, provider, *_ = self.adapter()
        adapter.load({"modelPath": "model"})
        adapter.unload()
        self.assertEqual(provider.unload_calls, 1)
        self.assertFalse(adapter.health())


if __name__ == "__main__":
    unittest.main()
