import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
PUBLISH_WORKFLOW = ROOT / ".github" / "workflows" / "publish-rc.yml"
WINDOWS = ROOT / "installer" / "windows"


class EngineHubCiReleasePolicyTests(unittest.TestCase):
    """Impide liberar Engine Hub sin evidencia Lite completa bajo 2 GiB."""

    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.publish = PUBLISH_WORKFLOW.read_text(encoding="utf-8")

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
        report = "MilyVoiceTraductor-2.0.1-TargetMachineSimulation.json"
        self.assertIn(report, self.workflow)
        self.assertIn(report, self.publish)
        self.assertTrue((WINDOWS / "test-engine-hub-target-machine.ps1").is_file())

    def test_three_real_lite_benchmarks_run_before_nsis(self):
        steps = (
            ("Moonshine Lite real EN to ES benchmark", "test-moonshine-lite.ps1"),
            ("Whisper Tiny Lite real EN to ES benchmark", "test-whisper-tiny-lite.ps1"),
            ("Mandarin Lite real ZH to ES benchmark", "test-zh-es-lite.ps1"),
        )
        nsis = self.workflow.index("Tauri NSIS bundle")
        for label, script in steps:
            with self.subTest(label=label):
                self.assertLess(self.workflow.index(label), nsis)
                self.assertIn(script, self.workflow)
                self.assertTrue((WINDOWS / script).is_file())

    def test_release_bundle_requires_simulation_and_all_lite_reports(self):
        for filename in (
            "MilyVoiceTraductor-2.0.1-TargetMachineSimulation.json",
            "MilyVoiceTraductor-2.0.1-MoonshineLiteBench.json",
            "MilyVoiceTraductor-2.0.1-WhisperTinyLiteBench.json",
            "MilyVoiceTraductor-2.0.1-ZhEsLiteBench.json",
        ):
            with self.subTest(filename=filename):
                self.assertIn(filename, self.workflow)
                self.assertIn(filename, self.publish)
        self.assertNotIn(
            'Get-Item "dist/performance/MilyVoiceTraductor-2.0.1-MegaBench.json"',
            self.workflow,
        )
        self.assertNotIn(
            "release/MilyVoiceTraductor-2.0.1-MegaBench.json",
            self.publish,
        )


if __name__ == "__main__":
    unittest.main()
