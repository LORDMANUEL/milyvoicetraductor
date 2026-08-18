import unittest
from pathlib import Path
from types import SimpleNamespace

from mily_ai.providers import FasterWhisperAsr


class FakeWhisperModel:
    def __init__(self):
        self.kwargs = None

    def transcribe(self, *_args, **kwargs):
        self.kwargs = kwargs
        word = SimpleNamespace(start=0.10, end=0.40, word=" hello")
        segment = SimpleNamespace(
            start=0.0,
            end=1.0,
            text=" hello",
            words=[word],
        )
        return [segment], SimpleNamespace(language="en", language_probability=1.0)


class WordTimestampTests(unittest.TestCase):
    def test_karaoke_asr_requests_and_returns_word_timestamps(self):
        provider = FasterWhisperAsr(
            Path("."),
            compute_profile="cpu",
            word_timestamps=True,
        )
        fake = FakeWhisperModel()
        provider._model = fake

        result = provider.transcribe([0.1] * 16000, "en")

        self.assertTrue(fake.kwargs["word_timestamps"])
        self.assertEqual(result[0].words[0].text, "hello")
        self.assertAlmostEqual(result[0].words[0].start, 0.10)
        self.assertAlmostEqual(result[0].words[0].end, 0.40)

    def test_meeting_asr_keeps_word_timestamps_disabled(self):
        provider = FasterWhisperAsr(Path("."), compute_profile="cpu")
        fake = FakeWhisperModel()
        provider._model = fake

        provider.transcribe([0.1] * 16000, "en")

        self.assertFalse(fake.kwargs["word_timestamps"])


if __name__ == "__main__":
    unittest.main()
