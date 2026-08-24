import unittest

import numpy as np

from mily_audio.stream import AudioIngress, AudioSourceKind


class FakeClock:
    def __init__(self, *values: int):
        self._values = iter(values)

    def __call__(self) -> int:
        return next(self._values)


class AudioIngressTests(unittest.TestCase):
    def test_first_chunk_starts_at_zero_and_preserves_metadata(self):
        ingress = AudioIngress(clock_ns=FakeClock(100))
        samples = np.array([0.0, 0.25, -0.5], dtype=np.float32)

        chunk = ingress.accept(
            samples,
            source=AudioSourceKind.MICROPHONE,
            sample_rate=16000,
            channels=1,
        )

        self.assertEqual(chunk.sequence_id, 0)
        self.assertEqual(chunk.captured_monotonic_ns, 100)
        self.assertEqual(chunk.source, AudioSourceKind.MICROPHONE)
        self.assertEqual(chunk.sample_rate, 16000)
        self.assertEqual(chunk.channels, 1)
        self.assertEqual(chunk.sample_count, 3)
        self.assertEqual(chunk.sample_format, "float32")
        self.assertFalse(chunk.discontinuity)
        np.testing.assert_array_equal(chunk.samples, samples)

    def test_sequence_increments_once_per_accepted_chunk(self):
        ingress = AudioIngress(clock_ns=FakeClock(10, 20, 30))
        ids = [
            ingress.accept(
                [0.1],
                source=AudioSourceKind.BROWSER_TAB,
                sample_rate=16000,
                channels=1,
            ).sequence_id
            for _ in range(3)
        ]
        self.assertEqual(ids, [0, 1, 2])

    def test_non_finite_samples_are_rejected_without_consuming_sequence_id(self):
        ingress = AudioIngress(clock_ns=FakeClock(100, 200))

        with self.assertRaises(ValueError):
            ingress.accept(
                [0.0, np.nan],
                source=AudioSourceKind.MEDIA_FILE,
                sample_rate=16000,
                channels=1,
            )

        accepted = ingress.accept(
            [0.0, 0.1],
            source=AudioSourceKind.MEDIA_FILE,
            sample_rate=16000,
            channels=1,
        )
        self.assertEqual(accepted.sequence_id, 0)
        self.assertEqual(accepted.captured_monotonic_ns, 100)

    def test_invalid_sample_rate_or_channels_are_rejected(self):
        ingress = AudioIngress(clock_ns=FakeClock(10))
        for sample_rate, channels in [(0, 1), (-1, 1), (16000, 0), (16000, -2)]:
            with self.subTest(sample_rate=sample_rate, channels=channels):
                with self.assertRaises(ValueError):
                    ingress.accept(
                        [0.1],
                        source=AudioSourceKind.SYSTEM_LOOPBACK,
                        sample_rate=sample_rate,
                        channels=channels,
                    )

    def test_explicit_discontinuity_reset_restarts_sequence_and_marks_one_chunk(self):
        ingress = AudioIngress(clock_ns=FakeClock(10, 20, 30, 40))
        first = ingress.accept(
            [0.1], source=AudioSourceKind.MICROPHONE, sample_rate=16000, channels=1
        )
        second = ingress.accept(
            [0.2], source=AudioSourceKind.MICROPHONE, sample_rate=16000, channels=1
        )
        self.assertEqual((first.sequence_id, second.sequence_id), (0, 1))

        ingress.reset(discontinuity=True)
        restarted = ingress.accept(
            [0.3], source=AudioSourceKind.MICROPHONE, sample_rate=16000, channels=1
        )
        following = ingress.accept(
            [0.4], source=AudioSourceKind.MICROPHONE, sample_rate=16000, channels=1
        )

        self.assertEqual((restarted.sequence_id, following.sequence_id), (0, 1))
        self.assertTrue(restarted.discontinuity)
        self.assertFalse(following.discontinuity)

    def test_non_discontinuous_reset_does_not_restart_stream(self):
        ingress = AudioIngress(clock_ns=FakeClock(1, 2))
        first = ingress.accept(
            [0.1], source=AudioSourceKind.MEDIA_FILE, sample_rate=16000, channels=1
        )
        ingress.reset(discontinuity=False)
        second = ingress.accept(
            [0.2], source=AudioSourceKind.MEDIA_FILE, sample_rate=16000, channels=1
        )
        self.assertEqual((first.sequence_id, second.sequence_id), (0, 1))
        self.assertFalse(second.discontinuity)


if __name__ == "__main__":
    unittest.main()
