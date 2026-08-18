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

    def __init__(self, samples: np.ndarray, alternatives=None):
        self.samples_by_index = {7: samples}
        self.open_kwargs = None
        self.open_history = []
        self.terminated = False
        self.alternatives = list(alternatives or [])
        for info, payload in self.alternatives:
            self.samples_by_index[int(info["index"])] = payload

    def get_default_wasapi_loopback(self):
        return {
            "index": 7,
            "maxInputChannels": 2,
            "defaultSampleRate": 48000.0,
            "name": "Default Speakers [Loopback]",
        }

    def get_loopback_devices(self):
        return [self.get_default_wasapi_loopback()] + [info for info, _ in self.alternatives]

    def open(self, **kwargs):
        self.open_kwargs = kwargs
        self.open_history.append(dict(kwargs))
        index = int(kwargs["input_device_index"])
        payload = self.samples_by_index[index]
        return FakeStream(payload.astype(np.float32).tobytes())

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

    def test_silent_default_switches_to_active_teams_output_loopback(self):
        silent_default = np.zeros((4800, 2), dtype=np.float32)
        teams_audio = np.column_stack([
            np.full(4800, 0.35, dtype=np.float32),
            np.full(4800, 0.25, dtype=np.float32),
        ])
        teams_device = {
            "index": 9,
            "maxInputChannels": 2,
            "defaultSampleRate": 48000.0,
            "name": "USB Headset [Loopback]",
        }
        backend = FakeBackend(
            silent_default,
            alternatives=[(teams_device, teams_audio)],
        )
        source = WasapiLoopbackSource(
            backend_factory=lambda: backend,
            silent_chunks_before_probe=2,
            activity_threshold=0.01,
        )

        source.open_default()
        first = source.read_chunk()
        second = source.read_chunk()

        self.assertAlmostEqual(float(np.mean(first)), 0.0, places=3)
        self.assertGreater(float(np.mean(second)), 0.2)
        self.assertIsNotNone(source.device)
        self.assertEqual(source.device.index, 9)
        self.assertEqual(source.device.name, "USB Headset [Loopback]")
        self.assertIn(9, [item["input_device_index"] for item in backend.open_history])
        source.close()


if __name__ == "__main__":
    unittest.main()
