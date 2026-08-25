import json
import unittest
from pathlib import Path


class LinguisticComponentMetadataTests(unittest.TestCase):
    def test_linguistic_component_declares_candidate_v1_identity(self):
        path = Path(__file__).resolve().parents[1] / "COMPONENT.json"
        metadata = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(
            metadata,
            {
                "id": "linguistic",
                "package": "milyvoice-linguistic",
                "version": "1.0.0",
                "contract": "linguistic/v1",
                "stage": "candidate",
            },
        )


if __name__ == "__main__":
    unittest.main()
