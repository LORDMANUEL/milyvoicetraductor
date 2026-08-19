import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
WINDOWS = ROOT / "installer" / "windows"


class EngineHubCiReleasePolicyTests(unittest.TestCase):
    """Impide volver a bloquear el producto Lite con un pack Quality >2 GiB."""

    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_quality_pack_is_policy_checked_not_activated_in_two_gib_gate(self):
        self.assertIn("test-quality-pack-policy.ps1", self.workflow)
        self.assertNotIn("test-realtime-model.ps1", self.workflow)
        script = WINDOWS / "test-quality-pack-policy.ps1"
        self.assertTrue(script.is_file())
        text = script.read_text(encoding="utf-8")
        self.assertIn("realtime-m2m100", text)
        self.assertIn("PROCESS_MEMORY_LIMIT", text)

    def test_target_machine_simulation_is_explicit_and_published(self):
        self.assertIn("Engine Hub target-machine simulation", self.workflow)
        self.assertIn("test-engine-hub-target-machine.ps1", self.workflow)
        self.assertIn(
            "MilyVoiceTraductor-2.0.1-TargetMachineSimulation.json",
            self.workflow,
        )
        self.assertTrue((WINDOWS / "test-engine-hub-target-machine.ps1").is_file())

    def test_two_real_lite_benchmarks_run_before_nsis(self):
        moonshine = self.workflow.index("Moonshine Lite real EN to ES benchmark")
        whisper = self.workflow.index("Whisper Tiny Lite real EN to ES benchmark")
        nsis = self.workflow.index("Tauri NSIS bundle")
        self.assertLess(moonshine, nsis)
        self.assertLess(whisper, nsis)
        self.assertTrue((WINDOWS / "test-whisper-tiny-lite.ps1").is_file())

    def test_release_bundle_requires_simulation_and_both_lite_reports(self):
        for filename in (
            "MilyVoiceTraductor-2.0.1-TargetMachineSimulation.json",
            "MilyVoiceTraductor-2.0.1-MoonshineLiteBench.json",
            "MilyVoiceTraductor-2.0.1-WhisperTinyLiteBench.json",
        ):
            self.assertIn(filename, self.workflow)
        self.assertNotIn(
            'Get-Item "dist/performance/MilyVoiceTraductor-2.0.1-MegaBench.json"',
            self.workflow,
        )


if __name__ == "__main__":
    unittest.main()
