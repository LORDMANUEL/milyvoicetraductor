import unittest
from dataclasses import dataclass

from mily_realtime.timeline import RealtimeTimeline, TimelineError


@dataclass
class FakeChunk:
    sequence_id: int
    captured_monotonic_ns: int
    sample_count: int = 1600
    sample_rate: int = 16000
    channels: int = 1
    sample_format: str = "float32"
    source: str = "microphone"
    discontinuity: bool = False
    samples: object = None


class RealtimeTimelineTests(unittest.TestCase):
    def test_first_chunk_starts_at_media_zero_and_uses_sample_duration(self):
        timeline = RealtimeTimeline()
        payload = object()
        chunk = FakeChunk(sequence_id=0, captured_monotonic_ns=1_000_000_000, samples=payload)

        frame = timeline.accept(chunk)

        self.assertEqual(frame.epoch, 0)
        self.assertEqual(frame.sequence_id, 0)
        self.assertEqual(frame.media_start_ns, 0)
        self.assertEqual(frame.duration_ns, 100_000_000)
        self.assertEqual(frame.jitter_ns, 0)
        self.assertEqual(frame.gap_before, 0)
        self.assertFalse(frame.discontinuity)
        self.assertIs(frame.payload, payload)
        self.assertEqual(timeline.snapshot().media_cursor_ns, 100_000_000)

    def test_capture_jitter_never_moves_sample_derived_media_cursor(self):
        timeline = RealtimeTimeline()
        captures = [1_000_000_000, 1_120_000_000, 1_620_000_000, 1_700_000_000]
        starts = []
        jitters = []

        for sequence_id, capture_ns in enumerate(captures):
            frame = timeline.accept(FakeChunk(sequence_id, capture_ns))
            starts.append(frame.media_start_ns)
            jitters.append(frame.jitter_ns)

        self.assertEqual(starts, [0, 100_000_000, 200_000_000, 300_000_000])
        self.assertEqual(jitters, [0, 20_000_000, 400_000_000, 20_000_000])
        self.assertEqual(timeline.snapshot().media_cursor_ns, 400_000_000)
        self.assertEqual(timeline.snapshot().max_jitter_ns, 400_000_000)

    def test_gap_is_explicit_but_missing_duration_is_not_invented(self):
        timeline = RealtimeTimeline()
        first = timeline.accept(FakeChunk(0, 1_000_000_000))
        after_gap = timeline.accept(FakeChunk(3, 1_300_000_000))

        self.assertEqual(first.media_start_ns, 0)
        self.assertEqual(after_gap.sequence_id, 3)
        self.assertEqual(after_gap.gap_before, 2)
        self.assertTrue(after_gap.discontinuity)
        self.assertEqual(after_gap.media_start_ns, 100_000_000)

        snapshot = timeline.snapshot()
        self.assertEqual(snapshot.gap_events, 1)
        self.assertEqual(snapshot.missing_chunks, 2)
        self.assertEqual(snapshot.expected_sequence_id, 4)
        self.assertEqual(snapshot.media_cursor_ns, 200_000_000)

    def test_duplicate_or_out_of_order_sequence_is_rejected_without_mutation(self):
        timeline = RealtimeTimeline()
        timeline.accept(FakeChunk(0, 1_000_000_000))
        timeline.accept(FakeChunk(1, 1_100_000_000))
        before = timeline.snapshot()

        with self.assertRaises(TimelineError) as context:
            timeline.accept(FakeChunk(1, 1_200_000_000))

        self.assertEqual(context.exception.code, "SEQUENCE_ORDER")
        after = timeline.snapshot()
        self.assertEqual(after.media_cursor_ns, before.media_cursor_ns)
        self.assertEqual(after.expected_sequence_id, before.expected_sequence_id)
        self.assertEqual(after.accepted_chunks, before.accepted_chunks)
        self.assertEqual(after.out_of_order_events, before.out_of_order_events + 1)

    def test_monotonic_timestamp_regression_is_rejected_without_advancing_media(self):
        timeline = RealtimeTimeline()
        timeline.accept(FakeChunk(0, 1_000_000_000))
        before = timeline.snapshot()

        with self.assertRaises(TimelineError) as context:
            timeline.accept(FakeChunk(1, 999_999_999))

        self.assertEqual(context.exception.code, "TIMESTAMP_REGRESSION")
        after = timeline.snapshot()
        self.assertEqual(after.media_cursor_ns, before.media_cursor_ns)
        self.assertEqual(after.expected_sequence_id, 1)
        self.assertEqual(after.timestamp_regressions, 1)

    def test_first_normal_chunk_must_start_at_sequence_zero(self):
        timeline = RealtimeTimeline()
        with self.assertRaises(TimelineError) as context:
            timeline.accept(FakeChunk(4, 1_000_000_000))
        self.assertEqual(context.exception.code, "FIRST_SEQUENCE")
        self.assertEqual(timeline.snapshot().accepted_chunks, 0)

    def test_explicit_discontinuity_starts_new_epoch_at_media_zero(self):
        timeline = RealtimeTimeline()
        timeline.accept(FakeChunk(0, 1_000_000_000))
        timeline.accept(FakeChunk(1, 1_100_000_000))

        restarted = timeline.accept(
            FakeChunk(0, 5_000_000_000, discontinuity=True, source="systemLoopback")
        )
        next_frame = timeline.accept(
            FakeChunk(1, 5_100_000_000, source="systemLoopback")
        )

        self.assertEqual(restarted.epoch, 1)
        self.assertEqual(restarted.media_start_ns, 0)
        self.assertTrue(restarted.discontinuity)
        self.assertEqual(restarted.jitter_ns, 0)
        self.assertEqual(next_frame.epoch, 1)
        self.assertEqual(next_frame.media_start_ns, 100_000_000)
        self.assertEqual(timeline.snapshot().media_cursor_ns, 200_000_000)

    def test_discontinuity_must_restart_sequence_at_zero(self):
        timeline = RealtimeTimeline()
        timeline.accept(FakeChunk(0, 1_000_000_000))
        with self.assertRaises(TimelineError) as context:
            timeline.accept(FakeChunk(1, 2_000_000_000, discontinuity=True))
        self.assertEqual(context.exception.code, "DISCONTINUITY_SEQUENCE")

    def test_stereo_sample_count_is_converted_to_frame_duration(self):
        timeline = RealtimeTimeline()
        frame = timeline.accept(
            FakeChunk(
                sequence_id=0,
                captured_monotonic_ns=1_000_000_000,
                sample_count=3200,
                sample_rate=16000,
                channels=2,
            )
        )
        self.assertEqual(frame.duration_ns, 100_000_000)

    def test_invalid_chunk_metadata_is_rejected(self):
        invalid = [
            FakeChunk(0, 1, sample_count=0),
            FakeChunk(0, 1, sample_rate=0),
            FakeChunk(0, 1, channels=0),
            FakeChunk(0, -1),
            FakeChunk(0, 1, sample_format="pcm16"),
        ]
        for chunk in invalid:
            with self.subTest(chunk=chunk):
                timeline = RealtimeTimeline()
                with self.assertRaises(TimelineError) as context:
                    timeline.accept(chunk)
                self.assertEqual(context.exception.code, "INVALID_CHUNK")


if __name__ == "__main__":
    unittest.main()
