import unittest
from pathlib import Path


class EngineHubReleasePolicyTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[3]
        self.ci = (self.root / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        self.policy_path = (
            self.root / "installer" / "windows" / "test-quality-pack-policy.ps1"
        )

    def test_complete_ci_runs_for_main_and_pruebas(self):
        self.assertGreaterEqual(self.ci.count("branches: [main, pruebas]"), 2)

    def test_two_gib_release_never_requires_the_oversized_quality_benchmark(self):
        self.assertNotIn(
            "run: .\\installer\\windows\\test-realtime-model.ps1",
            self.ci,
        )
        self.assertIn(
            "run: .\\installer\\windows\\test-quality-pack-policy.ps1",
            self.ci,
        )

    def test_real_lite_benchmark_is_a_mandatory_windows_gate(self):
        marker = "run: .\\installer\\windows\\test-moonshine-lite.ps1"
        self.assertIn(marker, self.ci)
        self.assertIn("Moonshine Lite real EN to ES benchmark", self.ci)

    def test_release_bundle_contains_lite_and_quality_policy_evidence(self):
        self.assertIn(
            "MilyVoiceTraductor-2.0.1-MoonshineLiteBench.json",
            self.ci,
        )
        self.assertIn(
            "MilyVoiceTraductor-2.0.1-QualityPolicy.json",
            self.ci,
        )
        self.assertNotIn(
            '$megaBench = Get-Item "dist/performance/MilyVoiceTraductor-2.0.1-MegaBench.json"',
            self.ci,
        )

    def test_quality_policy_asserts_resource_rejection_without_downloading_weights(self):
        self.assertTrue(self.policy_path.is_file())
        script = self.policy_path.read_text(encoding="utf-8")
        self.assertIn("realtime-m2m100", script)
        self.assertIn("PROCESS_MEMORY_LIMIT", script)
        self.assertIn("QualityPolicy.json", script)
        self.assertNotIn("snapshot_download", script)
        self.assertNotIn("test-realtime-model.ps1", script)


if __name__ == "__main__":
    unittest.main()
