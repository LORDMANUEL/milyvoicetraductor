import json
import unittest
from pathlib import Path


class EngineHostComponentMetadataTests(unittest.TestCase):
    def test_engine_host_component_declares_candidate_v1_identity(self):
        path = Path(__file__).resolve().parents[1] / "COMPONENT.json"
        metadata = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(
            metadata,
            {
                "id": "engine-host",
                "package": "milyvoice-engine-host",
                "version": "1.0.0",
                "contract": "engine/v1",
                "stage": "candidate",
            },
        )


if __name__ == "__main__":
    unittest.main()
