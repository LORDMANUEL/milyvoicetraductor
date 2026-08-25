import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MtComponentMetadataTests(unittest.TestCase):
    def test_mt_component_declares_candidate_v1_identity(self):
        metadata = json.loads((ROOT / "COMPONENT.json").read_text(encoding="utf-8"))
        self.assertEqual(
            metadata,
            {
                "id": "mt",
                "package": "milyvoice-mt",
                "version": "1.0.0",
                "contract": "mt/v1",
                "stage": "candidate",
            },
        )


if __name__ == "__main__":
    unittest.main()
