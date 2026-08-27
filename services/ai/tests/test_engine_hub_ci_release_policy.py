import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
PUBLISH_WORKFLOW = ROOT / ".github" / "workflows" / "publish-rc.yml"
WINDOWS = ROOT / "installer" / "windows"


class EngineHubCiReleasePolicyTests(unittest.TestCase):
    """Impide liberar Engine Hub 2.1 sin evidencia Lite bidireccional bajo 2 GiB."""

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
        report = "MilyVoiceTraductor-2.1.0-TargetMachineSimulation.json"
        self.assertIn(report, self.workflow)
        self.assertIn(report, self.publish)
        self.assertTrue((WINDOWS / "test-engine-hub-target-machine.ps1").is_file())

    def test_three_stable_english_benchmarks_run_before_nsis(self):
        steps = (
            ("Moonshine Lite real EN to ES benchmark", "test-moonshine-lite.ps1"),
            ("Whisper Tiny Lite real EN to ES benchmark", "test-whisper-tiny-lite.ps1"),
            ("Sherpa Zipformer Lite real EN to ES benchmark", "test-sherpa-lite.ps1"),
        )
        nsis = self.workflow.index("Tauri NSIS bundle")
        for label, script in steps:
            with self.subTest(label=label):
                self.assertLess(self.workflow.index(label), nsis)
                self.assertIn(script, self.workflow)
                self.assertTrue((WINDOWS / script).is_file())

    def test_two_outbound_benchmarks_are_blocking_before_nsis(self):
        steps = (
            ("Spanish Lite real ES to EN benchmark", "test-es-en-lite.ps1"),
            ("Spanish Lite real ES to ZH benchmark", "test-es-zh-lite.ps1"),
        )
        nsis = self.workflow.index("Tauri NSIS bundle")
        for label, script in steps:
            with self.subTest(label=label):
                start = self.workflow.index(label)
                self.assertLess(start, nsis)
                self.assertIn(script, self.workflow)
                self.assertTrue((WINDOWS / script).is_file())
                next_step = self.workflow.find("- name:", start + len(label))
                block = self.workflow[start:next_step if next_step >= 0 else nsis]
                self.assertNotIn("continue-on-error: true", block)

    def test_mandarin_receiver_is_experimental_and_non_blocking(self):
        marker = "Mandarin Lite experimental ZH to ES benchmark"
        self.assertIn(marker, self.workflow)
        start = self.workflow.index(marker)
        rust = self.workflow.index("- name: Rust tests", start)
        block = self.workflow[start:rust]
        self.assertIn("continue-on-error: true", block)
        self.assertIn("test-zh-es-lite.ps1", block)
        self.assertTrue((WINDOWS / "test-zh-es-lite.ps1").is_file())

    def test_sherpa_gate_enforces_real_memory_rtf_and_latency_limits(self):
        text = (WINDOWS / "test-sherpa-lite.ps1").read_text(encoding="utf-8")
        for marker in (
            "sherpa-zipformer-en-es",
            "test_wavs/*.wav",
            "benchmark_installed_pack",
            "totalProductWorkingSetMb",
            "combinedRtfP95",
            "endToEndP95Ms",
            "1536.0",
            "0.80",
            "1500.0",
            "SHERPA_LITE_GATE_OK",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_zh_receiver_benchmark_remains_strict_while_experimental(self):
        text = (WINDOWS / "test-zh-es-lite.ps1").read_text(encoding="utf-8")
        for marker in (
            "analyze_translation_quality",
            "ZH_ES_TRANSLATION_REPETITION",
            "ZH_ES_SEMANTIC_INVARIANT",
            "ZH_ES_SEMANTIC_CONTRADICTION",
            "ZH_ES_OUTPUT_EXPANSION",
            "semanticInvariantsPassed",
            "forbiddenTermsPassed",
            "expansionLimitsPassed",
            "$PackVersion = '1.0.1'",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_release_bundle_requires_stable_bidirectional_benchmark_reports(self):
        required = (
            "MilyVoiceTraductor-2.1.0-TargetMachineSimulation.json",
            "MilyVoiceTraductor-2.1.0-MoonshineLiteBench.json",
            "MilyVoiceTraductor-2.1.0-WhisperTinyLiteBench.json",
            "MilyVoiceTraductor-2.1.0-SherpaLiteBench.json",
            "MilyVoiceTraductor-2.1.0-EsEnLiteBench.json",
            "MilyVoiceTraductor-2.1.0-EsZhLiteBench.json",
        )
        for filename in required:
            with self.subTest(filename=filename):
                self.assertIn(filename, self.workflow)
                self.assertIn(filename, self.publish)

        mandarin_report = "MilyVoiceTraductor-2.1.0-ZhEsLiteBench.json"
        release_bundle = self.workflow[
            self.workflow.index("Prepare release bundle and SHA-256 checksums"):
            self.workflow.index("Collect sanitized diagnostics")
        ]
        self.assertNotIn(mandarin_report, release_bundle)
        self.assertNotIn(mandarin_report, self.publish)
        self.assertNotIn(
            'Get-Item "dist/performance/MilyVoiceTraductor-2.1.0-MegaBench.json"',
            self.workflow,
        )
        self.assertNotIn(
            "release/MilyVoiceTraductor-2.1.0-MegaBench.json",
            self.publish,
        )


if __name__ == "__main__":
    unittest.main()
