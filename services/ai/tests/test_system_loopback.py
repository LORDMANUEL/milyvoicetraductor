import unittest

import numpy as np

from mily_ai.system_loopback import WasapiLoopbackSource


class FakeStream:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.closed = False

    def read(self, _frames, exception_on_overflow=False):
        assert exception_on_overflow is False
        return self.payload

    def stop_stream(self):
        pass

    def close(self):
        self.closed = True


class FakeBackend:
    paFloat32 = 1

    def __init__(self, samples: np.ndarray):
        self.samples = samples
        self.open_kwargs = None
        self.terminated = False

    def get_default_wasapi_loopback(self):
        return {
            "index": 7,
            "maxInputChannels": 2,
            "defaultSampleRate": 48000.0,
            "name": "Default Speakers [Loopback]",
        }

    def open(self, **kwargs):
        self.open_kwargs = kwargs
        return FakeStream(self.samples.astype(np.float32).tobytes())

    def terminate(self):
        self.terminated = True


class WasapiLoopbackTests(unittest.TestCase):
    def test_default_loopback_is_mixed_to_mono_and_resampled_16khz(self):
        # 100 ms stereo @ 48 kHz. Left +0.4, right +0.2 => mono ~0.3.
        stereo = np.column_stack([
            np.full(4800, 0.4, dtype=np.float32),
            np.full(4800, 0.2, dtype=np.float32),
        ])
        backend = FakeBackend(stereo)
        source = WasapiLoopbackSource(backend_factory=lambda: backend)

        info = source.open_default()
        chunk = source.read_chunk()

        self.assertEqual(info.name, "Default Speakers [Loopback]")
        self.assertEqual(backend.open_kwargs["input_device_index"], 7)
        self.assertEqual(len(chunk), 1600)
        self.assertAlmostEqual(float(np.mean(chunk)), 0.3, places=2)
        source.close()
        self.assertTrue(backend.terminated)


if __name__ == "__main__":
    unittest.main()
