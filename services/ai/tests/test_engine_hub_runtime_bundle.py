import unittest
from pathlib import Path


class EngineHubRuntimeBundleTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[3]
        self.requirements = (
            self.root / "services" / "ai" / "requirements.runtime.txt"
        ).read_text(encoding="utf-8")
        self.builder = (
            self.root / "installer" / "windows" / "build-python-runtime.ps1"
        ).read_text(encoding="utf-8")
        cargo_config = self.root / ".cargo" / "config.toml"
        self.cargo_config = (
            cargo_config.read_text(encoding="utf-8") if cargo_config.is_file() else ""
        )

    def test_private_runtime_packages_every_approved_optional_engine(self):
        for distribution in (
            "moonshine-voice==",
            "sherpa-onnx==",
            "vosk==",
            "google-cloud-speech==",
        ):
            with self.subTest(distribution=distribution):
                self.assertIn(distribution, self.requirements)

    def test_runtime_build_smoke_imports_every_packaged_engine(self):
        for module in (
            "moonshine_voice",
            "sherpa_onnx",
            "vosk",
            "google.cloud.speech_v2",
            "ctranslate2",
            "sentencepiece",
            "faster_whisper",
        ):
            with self.subTest(module=module):
                self.assertIn(module, self.builder)

    def test_runtime_manifest_records_engine_hub_contents(self):
        self.assertIn("schemaVersion = 3", self.builder)
        self.assertIn("requiredModules = $RequiredRuntimeModules", self.builder)
        self.assertIn("optionalModules = $OptionalRuntimeModules", self.builder)
        self.assertIn("engineHubRuntimes", self.builder)
        for runtime in (
            "faster-whisper",
            "moonshine-voice",
            "sherpa-onnx",
            "vosk",
            "google-cloud-speech",
        ):
            with self.subTest(runtime=runtime):
                self.assertIn(runtime, self.builder)

    def test_windows_whisper_bindings_are_not_replaced_by_linux_snapshot(self):
        """MSVC must generate native bindings instead of copying Linux layouts."""

        self.assertNotIn("WHISPER_DONT_GENERATE_BINDINGS", self.cargo_config)


if __name__ == "__main__":
    unittest.main()
