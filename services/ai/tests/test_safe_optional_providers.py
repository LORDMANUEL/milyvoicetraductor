import tempfile
import types
import unittest
from pathlib import Path

from mily_ai.safe_optional_providers import (
    MoonshineResultAsr,
    WhisperCppBridgeAsr,
)


class FakeBridgeTransport:
    def __init__(self):
        self.requests = []
        self.closed = False

    def request(self, samples, language):
        self.requests.append((tuple(samples), language))
        return {"text": "hello world", "language": "en"}

    def close(self):
        self.closed = True


class FakeMoonshineStream:
    def __init__(self):
        self.started = 0
        self.stopped = 0
        self.closed = 0
        self.audio = []
        self.update_calls = 0

    def start(self):
        self.started += 1

    def add_audio(self, samples, sample_rate=16000):
        self.audio.extend(float(value) for value in samples)

    def update_transcription(self):
        self.update_calls += 1
        return types.SimpleNamespace(
            lines=[types.SimpleNamespace(text=f"heard-{len(self.audio)}")]
        )

    def stop(self):
        self.stopped += 1
        return self.update_transcription()

    def close(self):
        self.closed += 1


class FakeMoonshineTranscriber:
    def __init__(self):
        self.streams = []
        self.closed = False
        self.non_streaming_calls = 0

    def create_stream(self, update_interval=0.5):
        stream = FakeMoonshineStream()
        self.streams.append((update_interval, stream))
        return stream

    def transcribe_without_streaming(self, *_args, **_kwargs):
        self.non_streaming_calls += 1
        raise AssertionError("Moonshine realtime no debe usar transcribe_without_streaming")

    def close(self):
        self.closed = True


class SafeOptionalProviderTests(unittest.TestCase):
    def test_moonshine_reads_official_transcript_lines(self):
        transcript = types.SimpleNamespace(
            lines=[
                types.SimpleNamespace(text="Hello", start_time=0.0, end_time=0.4),
                types.SimpleNamespace(text="world", start_time=0.4, end_time=0.8),
            ]
        )
        self.assertEqual(
            MoonshineResultAsr._text_from_result(transcript),
            "Hello world",
        )

    def test_moonshine_reuses_stream_and_feeds_only_audio_delta(self):
        with tempfile.TemporaryDirectory() as tmp:
            transcriber = FakeMoonshineTranscriber()
            provider = MoonshineResultAsr(Path(tmp), "cpu")
            provider._transcriber = transcriber

            first = provider.transcribe([0.1, 0.2], "en")
            second = provider.transcribe([0.1, 0.2, 0.3, 0.4], "en")

            self.assertEqual(transcriber.non_streaming_calls, 0)
            self.assertEqual(len(transcriber.streams), 1)
            _, stream = transcriber.streams[0]
            self.assertEqual(stream.started, 1)
            self.assertEqual(stream.audio, [0.1, 0.2, 0.3, 0.4])
            self.assertEqual(first[0].text, "heard-2")
            self.assertEqual(second[0].text, "heard-4")

            provider.unload()
            self.assertEqual(stream.stopped, 1)
            self.assertEqual(stream.closed, 1)
            self.assertTrue(transcriber.closed)

    def test_moonshine_resets_stream_when_new_utterance_starts(self):
        with tempfile.TemporaryDirectory() as tmp:
            transcriber = FakeMoonshineTranscriber()
            provider = MoonshineResultAsr(Path(tmp), "cpu")
            provider._transcriber = transcriber

            provider.transcribe([0.1, 0.2, 0.3], "en")
            provider.transcribe([0.4, 0.5], "en")

            self.assertEqual(len(transcriber.streams), 2)
            first_stream = transcriber.streams[0][1]
            second_stream = transcriber.streams[1][1]
            self.assertEqual(first_stream.stopped, 1)
            self.assertEqual(first_stream.closed, 1)
            self.assertEqual(second_stream.audio, [0.4, 0.5])

    def test_moonshine_resets_when_new_utterance_is_longer_than_previous(self):
        with tempfile.TemporaryDirectory() as tmp:
            transcriber = FakeMoonshineTranscriber()
            provider = MoonshineResultAsr(Path(tmp), "cpu")
            provider._transcriber = transcriber

            provider.transcribe([0.1, 0.2], "en")
            provider.transcribe([0.9, 0.8, 0.7, 0.6], "en")

            self.assertEqual(len(transcriber.streams), 2)
            first_stream = transcriber.streams[0][1]
            second_stream = transcriber.streams[1][1]
            self.assertEqual(first_stream.stopped, 1)
            self.assertEqual(first_stream.closed, 1)
            self.assertEqual(second_stream.audio, [0.9, 0.8, 0.7, 0.6])

    def test_whisper_cpp_bridge_is_persistent_between_segments(self):
        with tempfile.TemporaryDirectory() as tmp:
            transport = FakeBridgeTransport()
            provider = WhisperCppBridgeAsr(
                Path(tmp),
                "cpu",
                transport=transport,
            )
            first = provider.transcribe([0.0, 0.1], "en")
            second = provider.transcribe([0.2, 0.3], "en")
            self.assertEqual(first[0].text, "hello world")
            self.assertEqual(second[0].text, "hello world")
            self.assertEqual(len(transport.requests), 2)
            provider.unload()
            self.assertTrue(transport.closed)


if __name__ == "__main__":
    unittest.main()
