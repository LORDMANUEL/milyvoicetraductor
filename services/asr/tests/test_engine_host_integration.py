import unittest
from dataclasses import dataclass
from types import SimpleNamespace

from mily_asr import MoonshineAsrAdapter, SherpaZipformerAsrAdapter, WhisperAsrAdapter
from mily_engine_host import (
    AdapterDescriptor,
    AdapterKind,
    AdapterStatus,
    EngineHost,
    EngineHostError,
    EngineInvocation,
)
from mily_realtime import RealtimeTimeline


@dataclass
class Chunk:
    sequence_id: int
    captured_monotonic_ns: int
    samples: object
    sample_count: int = 16000
    sample_rate: int = 16000
    channels: int = 1
    sample_format: str = "float32"
    source: str = "systemLoopback"
    discontinuity: bool = False


class GoodProvider:
    def __init__(self):
        self.payloads = []

    def warm_up(self, language="en"):
        pass

    def transcribe(self, samples, language):
        self.payloads.append(samples)
        return [SimpleNamespace(start=0.0, end=1.0, text="hello", language=language, words=())]

    def unload(self):
        pass


class BrokenProvider(GoodProvider):
    def transcribe(self, samples, language):
        raise RuntimeError("asr native failure")


def injected_factory(adapter_cls, provider, clock_values=(100, 200)):
    values = iter(clock_values)

    def provider_builder(component, model_path, compute_profile, cpu_budget, word_timestamps):
        return provider

    def budget_builder(profile, physical_cores):
        return object()

    return lambda: adapter_cls(
        provider_builder=provider_builder,
        cpu_budget_builder=budget_builder,
        clock_ns=lambda: next(values),
    )


class EngineHostAsrIntegrationTests(unittest.TestCase):
    def test_three_promoted_adapters_register_load_invoke_and_unload(self):
        cases = [
            ("whisper", WhisperAsrAdapter),
            ("moonshine", MoonshineAsrAdapter),
            ("sherpa-zipformer", SherpaZipformerAsrAdapter),
        ]
        providers = {adapter_id: GoodProvider() for adapter_id, _ in cases}
        host = EngineHost(max_loaded_adapters=3)

        for adapter_id, adapter_cls in cases:
            host.register(
                AdapterDescriptor(
                    id=adapter_id,
                    kind=AdapterKind.ASR,
                    title=adapter_id,
                    version="1.0.0",
                    contract="asr/v1",
                ),
                injected_factory(adapter_cls, providers[adapter_id]),
            )

        self.assertEqual([item.id for item in host.descriptors()], [item[0] for item in cases])
        for adapter_id, _ in cases:
            self.assertEqual(
                host.load(adapter_id, {"modelPath": f"models/{adapter_id}"}).status,
                AdapterStatus.HEALTHY,
            )

        payload = [0.0] * 16000
        frame = RealtimeTimeline().accept(
            Chunk(sequence_id=0, captured_monotonic_ns=1_000_000_000, samples=payload)
        )

        for adapter_id, _ in cases:
            result = host.invoke(
                adapter_id,
                EngineInvocation(
                    request_id=f"req-{adapter_id}",
                    route="asr:en",
                    frame=frame,
                    metadata={
                        "utteranceId": "utt-1",
                        "sourceLanguage": "en",
                    },
                ),
            )
            self.assertEqual(result.engine_id, adapter_id)
            self.assertEqual(result.text, "hello")
            self.assertEqual(result.media_start_ns, 0)
            self.assertEqual(result.media_end_ns, 1_000_000_000)
            self.assertIs(providers[adapter_id].payloads[0], payload)

        self.assertEqual(host.snapshot().loaded_adapters, 3)
        for adapter_id, _ in cases:
            self.assertEqual(host.unload(adapter_id).status, AdapterStatus.UNLOADED)
        self.assertEqual(host.snapshot().loaded_adapters, 0)

    def test_one_asr_failure_does_not_break_another_adapter(self):
        host = EngineHost(max_loaded_adapters=2)
        bad = BrokenProvider()
        good = GoodProvider()
        host.register(
            AdapterDescriptor("bad-asr", AdapterKind.ASR, "bad", "1.0.0", "asr/v1"),
            injected_factory(WhisperAsrAdapter, bad),
        )
        host.register(
            AdapterDescriptor("good-asr", AdapterKind.ASR, "good", "1.0.0", "asr/v1"),
            injected_factory(MoonshineAsrAdapter, good),
        )
        host.load("bad-asr", {"modelPath": "bad"})
        host.load("good-asr", {"modelPath": "good"})

        payload = [0.0] * 16000
        frame = RealtimeTimeline().accept(Chunk(0, 1_000_000_000, payload))
        request = EngineInvocation(
            request_id="r",
            route="asr:en",
            frame=frame,
            metadata={"utteranceId": "u", "sourceLanguage": "en"},
        )

        with self.assertRaises(EngineHostError) as context:
            host.invoke("bad-asr", request)
        self.assertEqual(context.exception.code, "ADAPTER_INVOKE_FAILED")
        self.assertEqual(host.health("bad-asr").status, AdapterStatus.UNHEALTHY)
        self.assertEqual(host.health("good-asr").status, AdapterStatus.HEALTHY)

        good_result = host.invoke("good-asr", request)
        self.assertEqual(good_result.text, "hello")
        self.assertIs(good.payloads[0], payload)


if __name__ == "__main__":
    unittest.main()
