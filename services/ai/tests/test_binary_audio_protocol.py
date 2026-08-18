"""Pruebas del transporte PCM16 binario para el camino caliente de audio."""

from __future__ import annotations

import struct
import unittest

import numpy as np

from mily_ai.audio import decode_pcm16_bytes


class BinaryAudioProtocolTests(unittest.TestCase):
    def test_binary_pcm_decoder_returns_float32_numpy_array(self):
        raw = struct.pack("<3h", -32768, 0, 32767)
        samples = decode_pcm16_bytes(raw)

        self.assertIsInstance(samples, np.ndarray)
        self.assertEqual(samples.dtype, np.float32)
        np.testing.assert_allclose(
            samples,
            np.asarray([-1.0, 0.0, 32767 / 32768], dtype=np.float32),
            atol=1e-6,
        )

    def test_binary_pcm_decoder_rejects_empty_or_odd_payloads(self):
        for raw in (b"", b"\x00"):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    decode_pcm16_bytes(raw)

    def test_binary_pcm_decoder_rejects_oversized_payload(self):
        with self.assertRaises(ValueError):
            decode_pcm16_bytes(b"\x00\x00" * (16000 * 5 + 1))


if __name__ == "__main__":
    unittest.main()
