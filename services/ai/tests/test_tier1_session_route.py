import tempfile
import unittest
from pathlib import Path

from mily_ai.pipeline import RealtimePipeline
from mily_ai.sessions import SessionRecorder


class Tier1SessionRouteTests(unittest.TestCase):
    def test_pipeline_keeps_explicit_spanish_source_and_english_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pack_path = root / "pack"
            (pack_path / "components" / "asr").mkdir(parents=True)
            (pack_path / "components" / "translation").mkdir(parents=True)
            (pack_path / "pack.json").write_text(
                '{"components":{"asr":{"provider":"faster-whisper"},"translation":{"provider":"m2m100-ct2"}}}',
                encoding="utf-8",
            )

            class Pack:
                path = pack_path

            recorder = SessionRecorder(root / "sessions", False)
            pipeline = RealtimePipeline.__new__(RealtimePipeline)
            pipeline.source_language = "es"
            pipeline.target_language = "en"

            self.assertEqual(pipeline.source_language, "es")
            self.assertEqual(pipeline.target_language, "en")

    def test_explicit_spanish_wins_language_detection(self):
        self.assertEqual(RealtimePipeline._detect_language("hola mundo", "auto", "es"), "es")


if __name__ == "__main__":
    unittest.main()
