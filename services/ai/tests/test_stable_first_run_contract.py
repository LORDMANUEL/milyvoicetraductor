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

    def test_real_nsis_verifies_first_launch_without_implicit_model_download(self) -> None:
        nsis_test = (ROOT / "installer/windows/test-nsis-installer.ps1").read_text(encoding="utf-8")
        self.assertIn("Assert-FirstRunStartsWithoutModelDownload", nsis_test)
        self.assertIn("model-pending", nsis_test)
        self.assertIn("current.json", nsis_test)
        self.assertIn("Start-Sleep -Seconds 5", nsis_test)
        self.assertIn("descarga o preparación implícita", nsis_test)


if __name__ == "__main__":
    unittest.main()
