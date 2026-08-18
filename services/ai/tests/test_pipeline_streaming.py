"""Contrato de salida incremental del pipeline sin cargar modelos reales."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mily_ai.models import InstalledPack
from mily_ai.pipeline import RealtimePipeline
from mily_ai.providers import AsrSegment, Translator
from mily_ai.sessions import SessionRecorder
from mily_ai.streaming import AdaptiveSpeechSegmenter


class FakeAsr:
    def __init__(self):
        self.calls = 0

    def transcribe(self, _samples, _source_language):
        self.calls += 1
        texts = {
            1: "I'm going to be there",
            2: "I'm going to be there with you",
            3: "I'm going to be there with you",
        }
        text = texts.get(self.calls, "")
        return [AsrSegment(0.0, 1.0, text, "en")] if text else []


class FakeTranslator(Translator):
    def __init__(self):
        self.calls: list[str] = []

    def translate(self, text: str, source_language: str) -> str:
        self.calls.append(text)
        return f"es:{text}"


class PipelineStreamingTests(unittest.TestCase):
    def build_pipeline(self, root: Path):
        pack_root = root / "pack"
        (pack_root / "components" / "asr").mkdir(parents=True)
        (pack_root / "components" / "translation").mkdir(parents=True)
        (pack_root / "pack.json").write_text(
            json.dumps(
                {
                    "components": {
                        "asr": {"provider": "faster-whisper"},
                        "translation": {"provider": "m2m100-ct2"},
                    }
                }
            ),
            encoding="utf-8",
        )
        pack = InstalledPack(
            id="realtime-m2m100",
            version="1",
            path=pack_root,
            active=True,
            title="test",
            commercial_use=True,
        )
        recorder = SessionRecorder(root / "sessions", persist_transcripts=True)
        recorder.start("en", "es")
        pipeline = RealtimePipeline(pack, "en", "cpu", recorder)
        fake_asr = FakeAsr()
        fake_translator = FakeTranslator()
        pipeline.asr = fake_asr
        pipeline.translator = fake_translator
        return pipeline, recorder, fake_translator

    def test_segment_cap_carries_over_audio_instead_of_dropping_it(self):
        segmenter = AdaptiveSpeechSegmenter(
            sample_rate=1000,
            first_decode_ms=100,
            partial_step_ms=50,
            finalize_silence_ms=50,
            max_utterance_ms=200,
            energy_threshold=0.1,
        )

        segmenter.push([0.5] * 150)
        events = segmenter.push([0.5] * 100)
        finals = [event for event in events if event.kind == "final"]

        self.assertEqual(len(finals), 1)
        self.assertEqual(len(finals[0].samples), 200)
        self.assertEqual(finals[0].start_sample, 0)
        self.assertEqual(finals[0].end_sample, 200)
        self.assertEqual(segmenter.buffered_samples, 50)
        self.assertTrue(segmenter.speech_active)

        flushed = segmenter.flush()
        self.assertEqual(len(flushed), 1)
        self.assertEqual(len(flushed[0].samples), 50)
        self.assertEqual(flushed[0].start_sample, 200)
        self.assertEqual(flushed[0].end_sample, 250)

    def test_ingest_never_calls_translation_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            pipeline, _recorder, translator = self.build_pipeline(Path(tmp))
            translation_requests = []
            transcription_events = []

            for _ in range(14):
                events, requests = pipeline.ingest([0.2] * 1600)
                transcription_events.extend(events)
                translation_requests.extend(requests)

            self.assertTrue(transcription_events)
            self.assertTrue(translation_requests)
            self.assertEqual(translator.calls, [])

            translated = pipeline.execute_translation(translation_requests[0])
            self.assertEqual(len(translator.calls), 1)
            self.assertTrue(translated.type.startswith("translation."))

    def test_partial_then_stable_translation_then_final(self):
        with tempfile.TemporaryDirectory() as tmp:
            pipeline, recorder, translator = self.build_pipeline(Path(tmp))
            output = []

            # push() sigue siendo una ruta síncrona de compatibilidad/pruebas;
            # el servidor de producción usa ingest/execute_translation por workers.
            for _ in range(14):
                output.extend(pipeline.push([0.2] * 1600))
            for _ in range(3):
                output.extend(pipeline.push([0.0] * 1600))

            types = [item.type for item in output]
            self.assertIn("transcription.partial", types)
            self.assertIn("translation.partial", types)
            self.assertIn("translation.final", types)
            self.assertGreaterEqual(len(translator.calls), 2)

            # Los parciales nunca se persisten como si fueran frases definitivas.
            self.assertEqual(len(recorder.segments), 1)
            self.assertEqual(recorder.segments[0].original, "I'm going to be there with you")

            result = recorder.finish()
            self.assertIsNotNone(result.metadata_path)
            metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["segmentCount"], 1)


if __name__ == "__main__":
    unittest.main()
