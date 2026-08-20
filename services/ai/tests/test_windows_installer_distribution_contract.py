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

    def test_bootstrap_does_not_treat_fixture_native_exit_as_powershell_gate_failure(self) -> None:
        bootstrap_test = (ROOT / "installer/windows/test-bootstrap.ps1").read_text(encoding="utf-8")
        invocation = "& (Join-Path $Root 'installer\\windows\\test-runtime-import-diagnostics.ps1')"
        self.assertIn(invocation, bootstrap_test)
        stale_check = (
            invocation
            + "\n    if ($LASTEXITCODE -ne 0) {\n"
            + "        throw 'Falló el gate de diagnóstico de imports del runtime privado.'"
        )
        self.assertNotIn(stale_check, bootstrap_test)

    def test_bootstrap_gate_explicitly_returns_success_after_diagnostic_fixture(self) -> None:
        bootstrap_test = (ROOT / "installer/windows/test-bootstrap.ps1").read_text(encoding="utf-8")
        self.assertIn(
            "Write-Host 'BOOTSTRAP POLICY OK' -ForegroundColor Green\nexit 0",
            bootstrap_test,
        )

    def test_model_downloads_happen_only_inside_engine_hub(self) -> None:
        onboarding = (ROOT / "apps/desktop/src/pages/Onboarding.svelte").read_text(encoding="utf-8")
        models = (ROOT / "apps/desktop/src/pages/Models.svelte").read_text(encoding="utf-8")
        bootstrap = (ROOT / "installer/windows/setup-installed.ps1").read_text(encoding="utf-8")

        self.assertNotIn("desktopApi.installModel(", onboarding)
        self.assertNotIn("realtime-m2m100", onboarding)
        self.assertIn("desktopApi.installModel(pack.id)", models)
        self.assertIn("pack.resourceAllowed", models)
        self.assertIn("El modelo se descargará desde la aplicación", bootstrap)

    def test_first_launch_without_model_opens_engine_hub_inside_the_app(self) -> None:
        app = (ROOT / "apps/desktop/src/App.svelte").read_text(encoding="utf-8")
        self.assertIn("onboarding.modelState !== 'ready'", app)
        self.assertIn("activePage = 'models'", app)
        self.assertIn("onboarding.modelState === 'ready' ? 'live' : 'models'", app)


if __name__ == "__main__":
    unittest.main()
