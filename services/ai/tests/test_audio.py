import unittest

from mily_ai.audio import PcmChunkBuffer


class AudioBufferTests(unittest.TestCase):
    def test_buffer_emits_window_and_keeps_overlap(self):
        buffer = PcmChunkBuffer(sample_rate=10, window_seconds=1.0, overlap_seconds=0.2)
        first = buffer.push_samples([0.1] * 6)
        self.assertIsNone(first)
        window = buffer.push_samples([0.2] * 6)
        self.assertEqual(len(window), 10)
        self.assertEqual(buffer.buffered_samples, 4)

    def test_invalid_sample_rate_fails(self):
        with self.assertRaises(ValueError):
            PcmChunkBuffer(sample_rate=0)


if __name__ == "__main__":
    unittest.main()
