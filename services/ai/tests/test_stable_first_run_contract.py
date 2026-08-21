from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


class StableFirstRunContractTests(unittest.TestCase):
    def test_onboarding_never_downloads_a_model_implicitly(self) -> None:
        onboarding = (ROOT / "apps/desktop/src/pages/Onboarding.svelte").read_text(encoding="utf-8")
        self.assertNotIn("desktopApi.installModel(", onboarding)
        self.assertNotIn("realtime-m2m100", onboarding)

    def test_missing_model_routes_to_model_manager_inside_the_app(self) -> None:
        app = (ROOT / "apps/desktop/src/App.svelte").read_text(encoding="utf-8")
        self.assertIn("onboarding.modelState !== 'ready'", app)
        self.assertIn("activePage = 'models'", app)

    def test_bridge_readiness_requires_binary_and_native_manifest(self) -> None:
        commands = (ROOT / "apps/desktop/src-tauri/src/commands/mod.rs").read_text(encoding="utf-8")
        self.assertIn('let bridge_root = state.paths.data_dir.join("bridge");', commands)
        self.assertIn('bridge_root.join(bridge_name).is_file()', commands)
        self.assertIn('bridge_root.join("com.milyvoice.traductor.json").is_file()', commands)
        self.assertIn('bridge_binary_ready && native_manifest_ready', commands)

    def test_real_nsis_verifies_first_launch_without_implicit_model_download(self) -> None:
        nsis_test = (ROOT / "installer/windows/test-first-run-no-model-download.ps1").read_text(encoding="utf-8")
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("Assert-FirstRunStartsWithoutModelDownload", nsis_test)
        self.assertIn("model-pending", nsis_test)
        self.assertIn("current.json", nsis_test)
        self.assertIn("Start-Sleep -Seconds 5", nsis_test)
        self.assertIn("descarga o preparación implícita", nsis_test)
        self.assertIn("test-first-run-no-model-download.ps1", ci)


if __name__ == "__main__":
    unittest.main()
