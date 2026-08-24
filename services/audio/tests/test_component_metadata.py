import json
import unittest
from pathlib import Path


class AudioComponentMetadataTests(unittest.TestCase):
    def test_audio_component_declares_candidate_v1_identity(self):
        path = Path(__file__).resolve().parents[1] / "COMPONENT.json"
        metadata = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(
            metadata,
            {
                "id": "audio",
                "package": "milyvoice-audio",
                "version": "1.0.0",
                "contract": "audio/v1",
                "stage": "candidate",
            },
        )


if __name__ == "__main__":
    unittest.main()
