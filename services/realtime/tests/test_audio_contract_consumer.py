import json
import unittest
from pathlib import Path

import numpy as np

from mily_audio import AudioIngress, AudioSourceKind
from mily_realtime import RealtimeTimeline


class FakeClock:
    def __init__(self, *values: int):
        self._values = iter(values)

    def __call__(self) -> int:
        return next(self._values)


class AudioContractConsumerTests(unittest.TestCase):
    def test_real_audio_chunk_is_consumed_without_payload_copy(self):
        ingress = AudioIngress(clock_ns=FakeClock(1_000_000_000))
        produced = ingress.accept(
            np.zeros(1600, dtype=np.float32),
            source=AudioSourceKind.MICROPHONE,
            sample_rate=16000,
            channels=1,
        )

        frame = RealtimeTimeline().accept(produced)

        self.assertEqual(frame.source, "microphone")
        self.assertEqual(frame.sequence_id, produced.sequence_id)
        self.assertEqual(frame.captured_monotonic_ns, produced.captured_monotonic_ns)
        self.assertEqual(frame.sample_rate, 16000)
        self.assertEqual(frame.channels, 1)
        self.assertEqual(frame.sample_count, 1600)
        self.assertEqual(frame.sample_format, "float32")
        self.assertEqual(frame.media_start_ns, 0)
        self.assertEqual(frame.duration_ns, 100_000_000)
        self.assertIs(frame.payload, produced.samples)

    def test_audio_discontinuity_starts_new_realtime_epoch(self):
        ingress = AudioIngress(clock_ns=FakeClock(100, 200, 1_000, 1_100))
        timeline = RealtimeTimeline()

        first = ingress.accept(
            [0.0] * 1600,
            source=AudioSourceKind.SYSTEM_LOOPBACK,
            sample_rate=16000,
            channels=1,
        )
        second = ingress.accept(
            [0.0] * 1600,
            source=AudioSourceKind.SYSTEM_LOOPBACK,
            sample_rate=16000,
            channels=1,
        )
        timeline.accept(first)
        timeline.accept(second)

        ingress.reset(discontinuity=True)
        restarted = ingress.accept(
            [0.0] * 1600,
            source=AudioSourceKind.SYSTEM_LOOPBACK,
            sample_rate=16000,
            channels=1,
        )
        following = ingress.accept(
            [0.0] * 1600,
            source=AudioSourceKind.SYSTEM_LOOPBACK,
            sample_rate=16000,
            channels=1,
        )

        restart_frame = timeline.accept(restarted)
        follow_frame = timeline.accept(following)

        self.assertEqual(restart_frame.epoch, 1)
        self.assertTrue(restart_frame.discontinuity)
        self.assertEqual(restart_frame.media_start_ns, 0)
        self.assertEqual(follow_frame.epoch, 1)
        self.assertEqual(follow_frame.media_start_ns, 100_000_000)

    def test_audio_and_realtime_contracts_share_source_and_format_values(self):
        root = Path(__file__).resolve().parents[3]
        audio_contract = json.loads(
            (root / "contracts/audio/v1/contract.json").read_text(encoding="utf-8")
        )
        realtime_contract = json.loads(
            (root / "contracts/realtime/v1/contract.json").read_text(encoding="utf-8")
        )

        self.assertEqual(
            realtime_contract["enums"]["AudioSourceKind"],
            audio_contract["enums"]["AudioSourceKind"],
        )
        self.assertEqual(
            realtime_contract["enums"]["SampleFormat"],
            audio_contract["enums"]["SampleFormat"],
        )


if __name__ == "__main__":
    unittest.main()
