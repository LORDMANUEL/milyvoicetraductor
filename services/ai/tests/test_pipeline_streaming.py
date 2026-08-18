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
            title="test",
            commercial_use=True,
            path=pack_root,
            active=True,
        )
        recorder = SessionRecorder(root / "sessions", enabled=True)
        recorder.start("en", "es")
        pipeline = RealtimePipeline(pack, "en", "cpu", recorder)
        fake_asr = FakeAsr()
        fake_translator = FakeTranslator()
        pipeline.asr = fake_asr
        pipeline.translator = fake_translator
        return pipeline, recorder, fake_translator

    def test_partial_then_stable_translation_then_final(self):
        with tempfile.TemporaryDirectory() as tmp:
            pipeline, recorder, translator = self.build_pipeline(Path(tmp))
            output = []

            # 100 ms por chunk a 16 kHz; primera inferencia alrededor de 0.9 s.
            for _ in range(14):
                output.extend(pipeline.push([0.2] * 1600))
            for _ in range(3):
                output.extend(pipeline.push([0.0] * 1600))

            types = [item.type for item in output]
            self.assertIn("transcription.partial", types)
            self.assertIn("translation.partial", types)
            self.assertIn("translation.final", types)
            self.assertGreaterEqual(len(translator.calls), 2)

            result = recorder.finish()
            self.assertIsNotNone(result.metadata_path)
            metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
            # Los parciales nunca se persisten como si fueran frases definitivas.
            self.assertEqual(len(metadata["segments"]), 1)
            self.assertEqual(metadata["segments"][0]["original"], "I'm going to be there with you")


if __name__ == "__main__":
    unittest.main()
