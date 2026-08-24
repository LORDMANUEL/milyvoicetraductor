import unittest
from dataclasses import dataclass

from mily_realtime import BackpressurePolicy, BoundedRealtimeQueue, RealtimeTimeline


@dataclass(frozen=True)
class Chunk:
    sequence_id: int
    captured_monotonic_ns: int
    sample_count: int = 1600
    sample_rate: int = 16000
    channels: int = 1
    sample_format: str = "float32"
    source: str = "systemLoopback"
    discontinuity: bool = False
    samples: object = None


@dataclass(frozen=True)
class QueueFrame:
    sequence_id: int
    duration_ns: int = 100_000_000


class LongRunRealtimeTests(unittest.TestCase):
    def test_sixty_minutes_of_capture_jitter_never_accumulates_media_drift(self):
        timeline = RealtimeTimeline()
        capture_ns = 1_000_000_000
        chunks = 36_000  # 60 minutes at 100 ms/chunk.

        for sequence_id in range(chunks):
            if sequence_id > 0:
                # Normal capture jitter alternates +/-10 ms. Every 1,000 chunks
                # simulate a 500 ms CPU/capture stall. Capture time stays
                # monotonic, but none of this is allowed to move media time.
                if sequence_id % 1000 == 0:
                    delta_ns = 500_000_000
                elif sequence_id % 2:
                    delta_ns = 90_000_000
                else:
                    delta_ns = 110_000_000
                capture_ns += delta_ns

            frame = timeline.accept(Chunk(sequence_id, capture_ns))
            self.assertEqual(frame.media_start_ns, sequence_id * 100_000_000)

        snapshot = timeline.snapshot()
        self.assertEqual(snapshot.accepted_chunks, chunks)
        self.assertEqual(snapshot.expected_sequence_id, chunks)
        self.assertEqual(snapshot.media_cursor_ns, 3_600_000_000_000)
        self.assertEqual(snapshot.gap_events, 0)
        self.assertEqual(snapshot.missing_chunks, 0)
        self.assertEqual(snapshot.out_of_order_events, 0)
        self.assertEqual(snapshot.timestamp_regressions, 0)
        self.assertEqual(snapshot.max_jitter_ns, 400_000_000)

    def test_sustained_slow_consumer_keeps_queue_bounded(self):
        queue = BoundedRealtimeQueue(
            max_chunks=8,
            max_buffered_duration_ns=500_000_000,
            policy=BackpressurePolicy.DROP_OLDEST,
        )

        offers = 100_000
        for sequence_id in range(offers):
            result = queue.offer(QueueFrame(sequence_id))
            self.assertTrue(result.accepted)
            snapshot = queue.snapshot()
            self.assertLessEqual(snapshot.depth, 5)
            self.assertLessEqual(snapshot.buffered_duration_ns, 500_000_000)

        snapshot = queue.snapshot()
        self.assertEqual(snapshot.depth, 5)
        self.assertEqual(snapshot.buffered_duration_ns, 500_000_000)
        self.assertEqual(snapshot.dropped_oldest, offers - 5)
        self.assertEqual(snapshot.rejected_new, 0)

        remaining = []
        while (frame := queue.pop()) is not None:
            remaining.append(frame.sequence_id)
        self.assertEqual(remaining, list(range(offers - 5, offers)))


if __name__ == "__main__":
    unittest.main()
