from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


class StableInstallerReliabilityContractTests(unittest.TestCase):
    def test_nsis_must_show_version_and_abort_on_bootstrap_failure(self) -> None:
        hooks = (ROOT / "apps/desktop/src-tauri/windows/hooks.nsh").read_text(encoding="utf-8")
        self.assertIn('BrandingText "${PRODUCTNAME} ${VERSION}"', hooks)
        self.assertIn('Caption "${PRODUCTNAME} ${VERSION} Setup"', hooks)
        self.assertIn("SetErrorLevel 2", hooks)
        self.assertIn('Abort "MilyVoiceTraductor ${VERSION} - instalación incompleta', hooks)

    def test_runtime_must_bundle_visual_cpp_app_local(self) -> None:
        builder = (ROOT / "installer/windows/build-python-runtime.ps1").read_text(encoding="utf-8")
        for dll in ("concrt140.dll", "msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"):
            self.assertIn(dll, builder)
        self.assertIn("appLocalVisualCppRuntime", builder)

    def test_bootstrap_gate_must_verify_visual_cpp_and_explicit_success(self) -> None:
        gate = (ROOT / "installer/windows/test-bootstrap.ps1").read_text(encoding="utf-8")
        self.assertIn("appLocalVisualCppRuntime", gate)
        self.assertIn("vcruntime140_1.dll", gate)
        self.assertIn("test-runtime-import-diagnostics.ps1", gate)
        self.assertIn("exit 0", gate)

    def test_runtime_import_fixture_must_exist_and_report_failed_module(self) -> None:
        fixture = ROOT / "installer/windows/test-runtime-import-diagnostics.ps1"
        self.assertTrue(fixture.is_file(), "Falta fixture de diagnóstico de imports del runtime.")
        if fixture.is_file():
            text = fixture.read_text(encoding="utf-8")
            self.assertIn("RUNTIME_IMPORT_FAILED", text)
            self.assertIn("runtimeImportFailures", text)
            self.assertIn("milyvoice_missing_fixture", text)

    def test_ci_must_execute_a_real_nsis_bootstrap_failure_path(self) -> None:
        fixture = ROOT / "installer/windows/test-nsis-bootstrap-failure.ps1"
        self.assertTrue(fixture.is_file(), "Falta prueba real de NSIS cuando bootstrap falla.")
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("Verify failed bootstrap makes NSIS fail", ci)
        self.assertIn("test-nsis-bootstrap-failure.ps1", ci)
        if fixture.is_file():
            text = fixture.read_text(encoding="utf-8")
            self.assertIn("LOCALAPPDATA", text)
            self.assertIn("ExitCode", text)
            self.assertIn("devolvió éxito", text)


if __name__ == "__main__":
    unittest.main()
