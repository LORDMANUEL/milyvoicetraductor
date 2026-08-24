import unittest
from dataclasses import dataclass

from mily_realtime.queue import BackpressurePolicy, BoundedRealtimeQueue


@dataclass(frozen=True)
class Frame:
    sequence_id: int
    duration_ns: int = 100_000_000


class BoundedRealtimeQueueTests(unittest.TestCase):
    def test_reject_new_preserves_existing_fifo_when_chunk_limit_is_full(self):
        queue = BoundedRealtimeQueue(
            max_chunks=2,
            max_buffered_duration_ns=500_000_000,
            policy=BackpressurePolicy.REJECT_NEW,
        )

        self.assertTrue(queue.offer(Frame(0)).accepted)
        self.assertTrue(queue.offer(Frame(1)).accepted)
        result = queue.offer(Frame(2))

        self.assertFalse(result.accepted)
        self.assertTrue(result.rejected_new)
        self.assertEqual(result.dropped_sequence_ids, ())
        self.assertEqual(queue.snapshot().depth, 2)
        self.assertEqual(queue.snapshot().rejected_new, 1)
        self.assertEqual(queue.pop().sequence_id, 0)
        self.assertEqual(queue.pop().sequence_id, 1)

    def test_duration_limit_is_enforced_even_below_chunk_limit(self):
        queue = BoundedRealtimeQueue(
            max_chunks=10,
            max_buffered_duration_ns=250_000_000,
            policy=BackpressurePolicy.REJECT_NEW,
        )
        self.assertTrue(queue.offer(Frame(0)).accepted)
        self.assertTrue(queue.offer(Frame(1)).accepted)
        self.assertFalse(queue.offer(Frame(2)).accepted)
        self.assertEqual(queue.snapshot().buffered_duration_ns, 200_000_000)

    def test_drop_oldest_evicts_only_what_is_required_by_chunk_limit(self):
        queue = BoundedRealtimeQueue(
            max_chunks=2,
            max_buffered_duration_ns=500_000_000,
            policy=BackpressurePolicy.DROP_OLDEST,
        )
        queue.offer(Frame(0))
        queue.offer(Frame(1))

        result = queue.offer(Frame(2))

        self.assertTrue(result.accepted)
        self.assertFalse(result.rejected_new)
        self.assertEqual(result.dropped_sequence_ids, (0,))
        self.assertEqual(queue.snapshot().dropped_oldest, 1)
        self.assertEqual(queue.pop().sequence_id, 1)
        self.assertEqual(queue.pop().sequence_id, 2)

    def test_drop_oldest_can_evict_for_media_duration_limit(self):
        queue = BoundedRealtimeQueue(
            max_chunks=10,
            max_buffered_duration_ns=150_000_000,
            policy=BackpressurePolicy.DROP_OLDEST,
        )
        queue.offer(Frame(0))

        result = queue.offer(Frame(1))

        self.assertTrue(result.accepted)
        self.assertEqual(result.dropped_sequence_ids, (0,))
        snapshot = queue.snapshot()
        self.assertEqual(snapshot.depth, 1)
        self.assertEqual(snapshot.buffered_duration_ns, 100_000_000)

    def test_single_frame_larger_than_duration_budget_is_always_rejected(self):
        for policy in BackpressurePolicy:
            with self.subTest(policy=policy):
                queue = BoundedRealtimeQueue(
                    max_chunks=10,
                    max_buffered_duration_ns=50_000_000,
                    policy=policy,
                )
                result = queue.offer(Frame(0, duration_ns=100_000_000))
                self.assertFalse(result.accepted)
                self.assertTrue(result.rejected_new)
                self.assertEqual(result.dropped_sequence_ids, ())
                self.assertEqual(queue.snapshot().depth, 0)
                self.assertEqual(queue.snapshot().rejected_new, 1)

    def test_pop_updates_buffered_duration_and_empty_pop_is_none(self):
        queue = BoundedRealtimeQueue(max_chunks=3, max_buffered_duration_ns=500_000_000)
        queue.offer(Frame(0, 120_000_000))
        queue.offer(Frame(1, 80_000_000))
        self.assertEqual(queue.snapshot().buffered_duration_ns, 200_000_000)

        self.assertEqual(queue.pop().sequence_id, 0)
        self.assertEqual(queue.snapshot().buffered_duration_ns, 80_000_000)
        self.assertEqual(queue.pop().sequence_id, 1)
        self.assertIsNone(queue.pop())
        self.assertEqual(queue.snapshot().buffered_duration_ns, 0)

    def test_invalid_limits_and_frame_duration_are_rejected(self):
        for kwargs in [
            {"max_chunks": 0, "max_buffered_duration_ns": 1},
            {"max_chunks": 1, "max_buffered_duration_ns": 0},
        ]:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    BoundedRealtimeQueue(**kwargs)

        queue = BoundedRealtimeQueue(max_chunks=1, max_buffered_duration_ns=1)
        with self.assertRaises(ValueError):
            queue.offer(Frame(0, duration_ns=0))


if __name__ == "__main__":
    unittest.main()
