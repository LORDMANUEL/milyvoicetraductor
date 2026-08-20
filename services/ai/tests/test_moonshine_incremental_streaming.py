import json
import sys
import tempfile
import types
import unittest
from enum import IntEnum
from pathlib import Path
from unittest.mock import patch

from mily_ai.moonshine_provider import MoonshineStreamingAsr


class FakeModelArch(IntEnum):
    TINY_STREAMING = 2


class FakeLine:
    def __init__(self, text):
        self.text = text
        self.start_time = 0.0
        self.duration = 1.0
        self.words = []


class FakeTranscript:
    def __init__(self, text):
        self.lines = [FakeLine(text)]


class FakeStream:
    def __init__(self, update_interval):
        self.update_interval = update_interval
        self.started = 0
        self.closed = 0
        self.added_lengths = []
        self.update_calls = 0

    def start(self):
        self.started += 1

    def add_audio(self, audio, sample_rate):
        self.added_lengths.append((len(audio), sample_rate))

    def update_transcription(self):
        self.update_calls += 1
        return FakeTranscript(f"partial-{sum(length for length, _ in self.added_lengths)}")

    def close(self):
        self.closed += 1


class FakeTranscriber:
    instances = []

    def __init__(self, model_path, model_arch, update_interval=0.5, options=None):
        self.model_path = model_path
        self.model_arch = model_arch
        self.update_interval = update_interval
        self.options = options or {}
        self.streams = []
        self.closed = 0
        self.__class__.instances.append(self)

    def create_stream(self, update_interval=None, options=None):
        stream = FakeStream(update_interval)
        self.streams.append(stream)
        return stream

    def close(self):
        self.closed += 1


class MoonshineIncrementalStreamingTests(unittest.TestCase):
    def setUp(self):
        FakeTranscriber.instances.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        (self.path / "moonshine-config.json").write_text(
            json.dumps(
                {
                    "modelArch": int(FakeModelArch.TINY_STREAMING),
                    "language": "en",
                    "updateInterval": 0.45,
                }
            ),
            encoding="utf-8",
        )
        self.module = types.SimpleNamespace(
            ModelArch=FakeModelArch,
            Transcriber=FakeTranscriber,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_model_arch_is_enum_and_only_audio_delta_is_added(self):
        with patch.dict(sys.modules, {"moonshine_voice": self.module}):
            provider = MoonshineStreamingAsr(self.path, "cpu")
            first = provider.transcribe([0.1] * 100, "en")
            second = provider.transcribe([0.1] * 150, "en")
            third = provider.transcribe([0.1] * 180, "en")

            transcriber = FakeTranscriber.instances[0]
            stream = transcriber.streams[0]
            self.assertIsInstance(transcriber.model_arch, FakeModelArch)
            self.assertGreaterEqual(stream.update_interval, 3600.0)
            self.assertEqual(stream.added_lengths, [(100, 16000), (50, 16000), (30, 16000)])
            self.assertEqual(stream.update_calls, 3)
            self.assertEqual(first[0].text, "partial-100")
            self.assertEqual(second[0].text, "partial-150")
            self.assertEqual(third[0].text, "partial-180")

            provider.finish_utterance()
            self.assertEqual(stream.closed, 1)
            provider.transcribe([0.2] * 100, "en")
            self.assertEqual(len(transcriber.streams), 2)
            self.assertEqual(transcriber.streams[1].added_lengths, [(100, 16000)])

    def test_equal_length_repeated_utterance_starts_a_new_stream(self):
        with patch.dict(sys.modules, {"moonshine_voice": self.module}):
            provider = MoonshineStreamingAsr(self.path, "cpu")
            provider.transcribe([0.1] * 100, "en")
            first_stream = FakeTranscriber.instances[0].streams[0]
            provider.transcribe([0.1] * 100, "en")
            streams = FakeTranscriber.instances[0].streams
            self.assertEqual(first_stream.closed, 1)
            self.assertEqual(len(streams), 2)
            self.assertEqual(streams[1].added_lengths, [(100, 16000)])

    def test_unsupported_language_fails_before_native_inference(self):
        with patch.dict(sys.modules, {"moonshine_voice": self.module}):
            provider = MoonshineStreamingAsr(self.path, "cpu")
            with self.assertRaisesRegex(Exception, "únicamente para inglés"):
                provider.transcribe([0.1] * 100, "zh")
            self.assertEqual(FakeTranscriber.instances, [])

    def test_unload_closes_stream_and_transcriber(self):
        with patch.dict(sys.modules, {"moonshine_voice": self.module}):
            provider = MoonshineStreamingAsr(self.path, "cpu")
            provider.transcribe([0.1] * 100, "en")
            transcriber = FakeTranscriber.instances[0]
            stream = transcriber.streams[0]
            provider.unload()
            self.assertEqual(stream.closed, 1)
            self.assertEqual(transcriber.closed, 1)
            self.assertIsNone(provider.selected_device)


if __name__ == "__main__":
    unittest.main()
