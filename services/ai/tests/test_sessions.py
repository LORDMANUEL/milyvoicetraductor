import tempfile
import unittest
from pathlib import Path

from mily_ai.sessions import SessionRecorder, TranscriptSegment, TranscriptWord


class SessionTests(unittest.TestCase):
    def test_opt_in_session_exports_txt_and_srt(self):
        with tempfile.TemporaryDirectory() as tmp:
            recorder = SessionRecorder(Path(tmp), persist_transcripts=True)
            recorder.start("en", "es")
            recorder.add(TranscriptSegment(0.0, 1.5, "hello", "hola"))
            result = recorder.finish()
            self.assertTrue(result.metadata_path.exists())
            self.assertTrue(result.txt_path.exists())
            self.assertTrue(result.srt_path.exists())
            self.assertIn("hola", result.txt_path.read_text(encoding="utf-8"))

    def test_bilingual_and_vtt_exports_include_speaker_and_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            recorder = SessionRecorder(Path(tmp), persist_transcripts=True)
            recorder.start("en", "es")
            recorder.add(
                TranscriptSegment(
                    0.0,
                    1.5,
                    "hello world",
                    "hola mundo",
                    speaker_id="speaker-a",
                    words=(
                        TranscriptWord(0.0, 0.6, "hello"),
                        TranscriptWord(0.6, 1.5, "world"),
                    ),
                )
            )
            result = recorder.finish()
            txt = result.txt_path.read_text(encoding="utf-8")
            self.assertIn("hello world", txt)
            self.assertIn("hola mundo", txt)
            self.assertTrue(result.srt_bilingual_path.exists())
            bilingual = result.srt_bilingual_path.read_text(encoding="utf-8")
            self.assertIn("Hablante A", bilingual)
            self.assertIn("hello world", bilingual)
            vtt = result.vtt_path.read_text(encoding="utf-8")
            self.assertTrue(vtt.startswith("WEBVTT"))
            self.assertIn("Hablante A", vtt)
            self.assertIn("<00:00:00.000>hello", vtt)

    def test_disabled_persistence_creates_no_session_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recorder = SessionRecorder(root, persist_transcripts=False)
            recorder.start("en", "es")
            recorder.add(TranscriptSegment(0.0, 1.0, "hello", "hola"))
            result = recorder.finish()
            self.assertIsNone(result.metadata_path)
            self.assertIsNone(result.vtt_path)
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
