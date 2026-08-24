import json
import unittest
from pathlib import Path


class AsrComponentMetadataTests(unittest.TestCase):
    def test_asr_component_declares_candidate_v1_identity(self):
        path = Path(__file__).resolve().parents[1] / "COMPONENT.json"
        metadata = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(
            metadata,
            {
                "id": "asr",
                "package": "milyvoice-asr",
                "version": "1.0.0",
                "contract": "asr/v1",
                "stage": "candidate",
            },
        )


if __name__ == "__main__":
    unittest.main()
