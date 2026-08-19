import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
LITE_REQ = ROOT / "services" / "ai" / "requirements.lite.txt"
QUALITY_REQ = ROOT / "services" / "ai" / "requirements.quality.txt"
BUILDER = ROOT / "installer" / "windows" / "build-betaalpha-runtime.ps1"


def active_requirements(path: Path) -> list[str]:
    return [
        line.strip().lower()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


class BetaAlphaRuntimeSplitTests(unittest.TestCase):
    def test_lite_runtime_excludes_quality_only_dependencies(self):
        lines = active_requirements(LITE_REQ)
        text = "\n".join(lines)
        for package in ("torch", "transformers", "google-cloud-speech"):
            self.assertNotIn(package, text)
        for package in (
            "faster-whisper",
            "moonshine-voice",
            "sherpa-onnx",
            "sentencepiece",
        ):
            self.assertIn(package, text)

    def test_quality_runtime_layers_on_top_of_lite(self):
        lines = active_requirements(QUALITY_REQ)
        self.assertIn("-r requirements.lite.txt", lines)
        text = "\n".join(lines)
        self.assertIn("torch", text)
        self.assertIn("transformers", text)

    def test_betaalpha_builder_uses_lite_requirements_and_smoke_checks_only_lite_engines(self):
        self.assertTrue(BUILDER.is_file())
        text = BUILDER.read_text(encoding="utf-8")
        self.assertIn("requirements.lite.txt", text)
        self.assertNotIn("requirements.runtime.txt", text)

        smoke_start = text.index("$runtimeSmoke = @'")
        smoke_end = text.index("'@", smoke_start + len("$runtimeSmoke = @'"))
        smoke = text[smoke_start:smoke_end]
        for module in (
            "moonshine_voice",
            "sherpa_onnx",
            "faster_whisper",
            "ctranslate2",
        ):
            self.assertIn(module, smoke)
        for module in ("import torch", "import transformers", "google.cloud.speech"):
            self.assertNotIn(module, smoke)

        self.assertIn("QUALITY_DEPENDENCY_LEAK", text)
        self.assertIn("channel = 'betaalpha-lite'", text)
        self.assertIn("milyvoice-python-runtime.zip", text)


if __name__ == "__main__":
    unittest.main()
