from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


class WindowsInstallerDistributionContractTests(unittest.TestCase):
    def test_nsis_shows_beta_version_and_never_reports_success_after_bootstrap_failure(self) -> None:
        hooks = (ROOT / "apps/desktop/src-tauri/windows/hooks.nsh").read_text(encoding="utf-8")
        self.assertIn('BrandingText "${PRODUCTNAME} ${VERSION} Beta"', hooks)
        self.assertIn('Caption "${PRODUCTNAME} ${VERSION} Beta Setup"', hooks)
        self.assertIn('SetErrorLevel 2', hooks)
        self.assertIn('Abort "MilyVoiceTraductor ${VERSION} Beta', hooks)

    def test_private_python_runtime_carries_visual_cpp_runtime_app_locally(self) -> None:
        builder = (ROOT / "installer/windows/build-python-runtime.ps1").read_text(encoding="utf-8")
        for dll in ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll", "concrt140.dll"):
            self.assertIn(dll, builder)
        self.assertIn("appLocalVisualCppRuntime", builder)
        self.assertIn("System32", builder)

    def test_bootstrap_gate_verifies_app_local_visual_cpp_runtime(self) -> None:
        bootstrap_test = (ROOT / "installer/windows/test-bootstrap.ps1").read_text(encoding="utf-8")
        self.assertIn("appLocalVisualCppRuntime", bootstrap_test)
        self.assertIn("msvcp140.dll", bootstrap_test)
        self.assertIn("vcruntime140_1.dll", bootstrap_test)


if __name__ == "__main__":
    unittest.main()
