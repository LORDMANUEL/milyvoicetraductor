import unittest
from dataclasses import dataclass

from mily_engine_host import (
    AdapterDescriptor,
    AdapterKind,
    EngineHost,
    EngineInvocation,
)
from mily_realtime import RealtimeTimeline


@dataclass
class Chunk:
    sequence_id: int
    captured_monotonic_ns: int
    samples: object
    sample_count: int = 1600
    sample_rate: int = 16000
    channels: int = 1
    sample_format: str = "float32"
    source: str = "systemLoopback"
    discontinuity: bool = False


class CapturingAdapter:
    def __init__(self):
        self.requests = []

    def load(self, config):
        self.config = dict(config)

    def unload(self):
        pass

    def invoke(self, request):
        self.requests.append(request)
        return {
            "sequenceId": request.frame.sequence_id,
            "mediaStartNs": request.frame.media_start_ns,
        }

    def health(self):
        return True


class RealtimeConsumerTests(unittest.TestCase):
    def test_realtime_frame_reaches_adapter_without_payload_copy(self):
        payload = object()
        frame = RealtimeTimeline().accept(
            Chunk(sequence_id=0, captured_monotonic_ns=1_000_000_000, samples=payload)
        )

        created = []

        def factory():
            adapter = CapturingAdapter()
            created.append(adapter)
            return adapter

        host = EngineHost(max_loaded_adapters=1)
        host.register(
            AdapterDescriptor(
                id="fake-asr",
                kind=AdapterKind.ASR,
                title="Fake ASR",
                version="1.0.0",
                contract="asr/v1",
            ),
            factory,
        )
        host.load("fake-asr")

        request = EngineInvocation(
            request_id="req-1",
            route="asr:en",
            frame=frame,
            metadata={"language": "en"},
        )
        result = host.invoke("fake-asr", request)

        captured = created[0].requests[0]
        self.assertIs(captured, request)
        self.assertIs(captured.frame, frame)
        self.assertIs(captured.frame.payload, payload)
        self.assertEqual(captured.frame.sequence_id, 0)
        self.assertEqual(captured.frame.media_start_ns, 0)
        self.assertEqual(captured.frame.duration_ns, 100_000_000)
        self.assertEqual(captured.frame.source, "systemLoopback")
        self.assertEqual(result, {"sequenceId": 0, "mediaStartNs": 0})

    def test_host_does_not_import_realtime_in_production_module(self):
        # The integration dependency is one-way at the test/contract layer. A
        # future transport can change without coupling host.py to Realtime.
        import mily_engine_host.host as host_module

        module_globals = set(host_module.__dict__)
        self.assertNotIn("RealtimeTimeline", module_globals)
        self.assertNotIn("RealtimeFrame", module_globals)


if __name__ == "__main__":
    unittest.main()
