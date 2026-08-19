import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mily_ai.models import InstalledPack
from mily_ai.pipeline import RealtimePipeline, TranslationRequest
from mily_ai.providers import AsrSegment, Translator
from mily_ai.sessions import SessionRecorder
from mily_ai.streaming import AdaptiveSpeechSegmenter


class _Asr:
    selected_device = "cpu"
    fallback_used = False
    fallback_reason = ""
    word_timestamps = False

    def transcribe(self, samples, source_language):
        return [AsrSegment(0.0, len(samples) / 16000.0, "hello world", "en")]

    def unload(self):
        pass


class _Translator(Translator):
    selected_device = "cpu"
    fallback_used = False
    fallback_reason = ""

    def __init__(self):
        self.calls = []

    def translate(self, text: str, source_language: str) -> str:
        self.calls.append((text, source_language))
        mapping = {
            "good morning": "buenos días",
            "everybody": "a todos",
            "good morning everybody": "buenos días a todos",
        }
        return mapping.get(text, f"es:{text}")

    def unload(self):
        pass


class BetaAlphaPipelineTests(unittest.TestCase):
    def _pipeline(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        pack_root = root / "pack"
        pack_root.mkdir()
        (pack_root / "pack.json").write_text(
            json.dumps(
                {
                    "components": {
                        "asr": {"provider": "sherpa-onnx"},
                        "translation": {
                            "provider": "marian-ct2",
                            "sourceLanguage": "en",
                            "targetLanguage": "es",
                        },
                    }
                }
            ),
            encoding="utf-8",
        )
        (pack_root / "components" / "asr").mkdir(parents=True)
        (pack_root / "components" / "translation").mkdir(parents=True)
        pack = InstalledPack(
            id="betaalpha-test-en-es",
            version="1.0.0",
            path=pack_root,
            active=True,
            title="BetaAlpha test",
            commercial_use=True,
        )
        translator = _Translator()
        recorder = SessionRecorder(root / "sessions", persist_transcripts=False)
        patches = (
            patch("mily_ai.pipeline.build_asr_provider", return_value=_Asr()),
            patch("mily_ai.pipeline.build_translation_provider", return_value=translator),
        )
        for item in patches:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in patches])
        self.addCleanup(temp.cleanup)
        return RealtimePipeline(pack, "en", "cpu", recorder), translator

    def test_partial_translation_reuses_committed_prefix_but_final_rechecks_full_sentence(self):
        pipeline, translator = self._pipeline()
        first = pipeline.execute_translation(
            TranslationRequest(
                type="translation.partial",
                start=0.0,
                end=1.0,
                original="good morning",
                language="en",
                utterance_id="u-1",
            )
        )
        second = pipeline.execute_translation(
            TranslationRequest(
                type="translation.partial",
                start=0.0,
                end=1.4,
                original="good morning everybody",
                language="en",
                utterance_id="u-1",
            )
        )
        final = pipeline.execute_translation(
            TranslationRequest(
                type="translation.final",
                start=0.0,
                end=1.6,
                original="good morning everybody",
                language="en",
                utterance_id="u-1",
            )
        )
        self.assertEqual(first.translation, "buenos días")
        self.assertEqual(second.translation, "buenos días a todos")
        self.assertEqual(final.translation, "buenos días a todos")
        self.assertEqual(
            translator.calls,
            [
                ("good morning", "en"),
                ("everybody", "en"),
                ("good morning everybody", "en"),
            ],
        )

    def test_dynamic_partial_interval_can_change_without_resetting_utterance(self):
        segmenter = AdaptiveSpeechSegmenter(
            sample_rate=16000,
            first_decode_ms=900,
            partial_step_ms=700,
        )
        segmenter.push([0.02] * 8000)
        buffered_before = segmenter.buffered_samples
        segmenter.set_partial_step_ms(280)
        self.assertEqual(segmenter.buffered_samples, buffered_before)
        self.assertEqual(segmenter.partial_step_samples, 4480)


if __name__ == "__main__":
    unittest.main()
