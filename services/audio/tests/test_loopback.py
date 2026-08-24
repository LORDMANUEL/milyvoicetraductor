import unittest

import numpy as np

from mily_audio.loopback import LoopbackError, WasapiLoopbackSource


class FakeStream:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.closed = False
        self.stopped = False

    def read(self, _frames, exception_on_overflow=False):
        assert exception_on_overflow is False
        return self.payload

    def stop_stream(self):
        self.stopped = True

    def close(self):
        self.closed = True


class FakeBackend:
    paFloat32 = 1

    def __init__(self, samples: np.ndarray, alternatives=None, broken_indices=None):
        self.samples_by_index = {7: samples}
        self.open_kwargs = None
        self.open_history = []
        self.streams = []
        self.terminated = False
        self.alternatives = list(alternatives or [])
        self.broken_indices = set(broken_indices or [])
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
        return [self.get_default_wasapi_loopback()] + [
            info for info, _ in self.alternatives
        ]

    def open(self, **kwargs):
        self.open_kwargs = kwargs
        self.open_history.append(dict(kwargs))
        index = int(kwargs["input_device_index"])
        if index in self.broken_indices:
            raise OSError("simulated broken loopback")
        payload = self.samples_by_index[index]
        stream = FakeStream(payload.astype(np.float32).tobytes())
        self.streams.append(stream)
        return stream

    def terminate(self):
        self.terminated = True


def stereo_constant(left: float, right: float) -> np.ndarray:
    return np.column_stack(
        [
            np.full(4800, left, dtype=np.float32),
            np.full(4800, right, dtype=np.float32),
        ]
    )


def alternative(index: int, name: str, samples: np.ndarray):
    return (
        {
            "index": index,
            "maxInputChannels": 2,
            "defaultSampleRate": 48000.0,
            "name": name,
        },
        samples,
    )


class WasapiLoopbackTests(unittest.TestCase):
    def test_default_loopback_is_mixed_to_mono_and_resampled_16khz(self):
        backend = FakeBackend(stereo_constant(0.4, 0.2))
        source = WasapiLoopbackSource(backend_factory=lambda: backend)

        info = source.open_default()
        chunk = source.read_chunk()

        self.assertEqual(info.name, "Default Speakers [Loopback]")
        self.assertEqual(backend.open_kwargs["input_device_index"], 7)
        self.assertEqual(len(chunk), 1600)
        self.assertAlmostEqual(float(np.mean(chunk)), 0.3, places=2)

        source.close()
        self.assertTrue(backend.terminated)
        self.assertTrue(all(stream.closed for stream in backend.streams))

    def test_silent_default_switches_only_to_active_alternative(self):
        silent = np.zeros((4800, 2), dtype=np.float32)
        teams_audio = stereo_constant(0.35, 0.25)
        backend = FakeBackend(
            silent,
            alternatives=[alternative(9, "USB Headset [Loopback]", teams_audio)],
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
        source.close()

    def test_silent_alternative_never_replaces_current_default(self):
        silent = np.zeros((4800, 2), dtype=np.float32)
        backend = FakeBackend(
            silent,
            alternatives=[alternative(9, "Silent USB [Loopback]", silent)],
        )
        source = WasapiLoopbackSource(
            backend_factory=lambda: backend,
            silent_chunks_before_probe=1,
            activity_threshold=0.01,
        )

        source.open_default()
        chunk = source.read_chunk()

        self.assertAlmostEqual(float(np.mean(chunk)), 0.0, places=3)
        self.assertEqual(source.device.index, 7)
        source.close()

    def test_broken_alternative_does_not_drop_valid_current_capture(self):
        silent = np.zeros((4800, 2), dtype=np.float32)
        backend = FakeBackend(
            silent,
            alternatives=[alternative(9, "Broken USB [Loopback]", stereo_constant(0.5, 0.5))],
            broken_indices={9},
        )
        source = WasapiLoopbackSource(
            backend_factory=lambda: backend,
            silent_chunks_before_probe=1,
            activity_threshold=0.01,
        )

        source.open_default()
        chunk = source.read_chunk()

        self.assertAlmostEqual(float(np.mean(chunk)), 0.0, places=3)
        self.assertEqual(source.device.index, 7)
        source.close()

    def test_read_before_open_is_rejected_with_stable_error_code(self):
        source = WasapiLoopbackSource(backend_factory=lambda: None)
        with self.assertRaises(LoopbackError) as context:
            source.read_chunk()
        self.assertEqual(context.exception.code, "LOOPBACK_DEVICE")

    def test_invalid_configuration_is_rejected(self):
        for kwargs in [
            {"target_sample_rate": 0},
            {"chunk_ms": 0},
            {"silent_chunks_before_probe": 0},
            {"activity_threshold": 0},
        ]:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    WasapiLoopbackSource(**kwargs)


if __name__ == "__main__":
    unittest.main()
