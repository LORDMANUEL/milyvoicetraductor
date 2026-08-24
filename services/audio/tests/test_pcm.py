import unittest

import numpy as np

from mily_audio.pcm import MAX_AUDIO_CHUNK_BYTES, PcmChunkBuffer, decode_pcm16_bytes


class PcmTests(unittest.TestCase):
    def test_pcm16_decodes_to_normalized_float32(self):
        raw = np.array([-32768, 0, 16384, 32767], dtype="<i2").tobytes()
        decoded = decode_pcm16_bytes(raw)
        self.assertEqual(decoded.dtype, np.float32)
        self.assertEqual(decoded.shape, (4,))
        self.assertAlmostEqual(float(decoded[0]), -1.0, places=6)
        self.assertAlmostEqual(float(decoded[2]), 0.5, places=6)
        self.assertLess(float(decoded[3]), 1.0)

    def test_invalid_pcm16_payload_is_rejected(self):
        for raw in [b"", b"\x00", b"\x00" * (MAX_AUDIO_CHUNK_BYTES + 2)]:
            with self.subTest(length=len(raw)):
                with self.assertRaises(ValueError):
                    decode_pcm16_bytes(raw)

    def test_buffer_emits_window_and_keeps_overlap(self):
        buffer = PcmChunkBuffer(sample_rate=10, window_seconds=1.0, overlap_seconds=0.2)
        self.assertIsNone(buffer.push_samples([0.1] * 6))
        window = buffer.push_samples([0.2] * 6)
        self.assertIsNotNone(window)
        self.assertEqual(len(window), 10)
        self.assertEqual(buffer.buffered_samples, 4)

    def test_repeated_realtime_chunks_keep_retained_buffer_bounded(self):
        buffer = PcmChunkBuffer(sample_rate=16000, window_seconds=2.4, overlap_seconds=0.35)
        chunk = np.zeros(1600, dtype=np.float32)  # 100 ms
        emitted = 0

        for _ in range(10_000):
            if buffer.push_samples(chunk) is not None:
                emitted += 1
            self.assertLess(buffer.buffered_samples, buffer.window_samples + len(chunk))

        self.assertGreater(emitted, 400)

    def test_invalid_buffer_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            PcmChunkBuffer(sample_rate=0)
        with self.assertRaises(ValueError):
            PcmChunkBuffer(window_seconds=0)
        with self.assertRaises(ValueError):
            PcmChunkBuffer(window_seconds=1.0, overlap_seconds=1.0)


if __name__ == "__main__":
    unittest.main()
