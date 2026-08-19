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
