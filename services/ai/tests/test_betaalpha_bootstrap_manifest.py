import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SETUP = ROOT / "installer" / "windows" / "setup-installed.ps1"


class BetaAlphaBootstrapManifestTests(unittest.TestCase):
    def test_setup_installed_validates_only_engines_declared_by_runtime_manifest(self):
        text = SETUP.read_text(encoding="utf-8")
        self.assertIn("engineHubRuntimes", text)
        self.assertIn("Resolve-RuntimeImportModules", text)
        self.assertIn("moonshine-voice", text)
        self.assertIn("sherpa-onnx", text)
        self.assertIn("faster-whisper", text)
        self.assertIn("transformers", text)
        self.assertIn("google-cloud-speech", text)
        self.assertNotIn(
            "import fastapi,uvicorn,numpy,faster_whisper,transformers,torch,huggingface_hub",
            text,
        )


if __name__ == "__main__":
    unittest.main()
