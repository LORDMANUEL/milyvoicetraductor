import json
import unittest
from pathlib import Path


class RealtimeComponentMetadataTests(unittest.TestCase):
    def test_realtime_component_declares_candidate_v1_identity(self):
        path = Path(__file__).resolve().parents[1] / "COMPONENT.json"
        metadata = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(
            metadata,
            {
                "id": "realtime",
                "package": "milyvoice-realtime",
                "version": "1.0.0",
                "contract": "realtime/v1",
                "stage": "candidate",
            },
        )


if __name__ == "__main__":
    unittest.main()
