import tempfile
import unittest
from pathlib import Path

from mily_ai.sessions import SessionRecorder, TranscriptSegment


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

    def test_disabled_persistence_creates_no_session_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recorder = SessionRecorder(root, persist_transcripts=False)
            recorder.start("en", "es")
            recorder.add(TranscriptSegment(0.0, 1.0, "hello", "hola"))
            result = recorder.finish()
            self.assertIsNone(result.metadata_path)
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
