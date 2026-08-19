from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BUILD_RUNTIME = ROOT / "installer" / "windows" / "build-python-runtime.ps1"
SETUP_INSTALLED = ROOT / "installer" / "windows" / "setup-installed.ps1"
NSIS_GATE = ROOT / "installer" / "windows" / "test-nsis-installer.ps1"
CLI = ROOT / "services" / "ai" / "mily_ai" / "cli.py"


class WindowsBootstrapContractTests(unittest.TestCase):
    def test_runtime_manifest_separates_core_from_optional_engines(self):
        text = BUILD_RUNTIME.read_text(encoding="utf-8")
        self.assertIn("$RequiredRuntimeModules = @(", text)
        self.assertIn("$OptionalRuntimeModules = @(", text)
        self.assertIn("requiredModules = $RequiredRuntimeModules", text)
        self.assertIn("optionalModules = $OptionalRuntimeModules", text)

        required_block = re.search(
            r"\$RequiredRuntimeModules\s*=\s*@\((.*?)\)\s*\n\$OptionalRuntimeModules",
            text,
            flags=re.S,
        )
        self.assertIsNotNone(required_block)
        required = required_block.group(1)
        for module in (
            "fastapi",
            "uvicorn",
            "numpy",
            "faster_whisper",
            "ctranslate2",
            "huggingface_hub",
            "sentencepiece",
        ):
            self.assertIn(f"'{module}'", required)
        self.assertNotIn("'torch'", required)
        self.assertNotIn("'transformers'", required)

    def test_postinstall_reads_manifest_contract_and_does_not_require_quality_stack(self):
        text = SETUP_INSTALLED.read_text(encoding="utf-8")
        self.assertIn("$runtimeManifest.requiredModules", text)
        self.assertIn("$runtimeManifest.optionalModules", text)
        self.assertNotIn(
            'import fastapi,uvicorn,numpy,faster_whisper,transformers,torch,huggingface_hub',
            text,
        )

    def test_powershell_error_output_avoids_code_colon_interpolation(self):
        text = SETUP_INSTALLED.read_text(encoding="utf-8")
        self.assertIn("Write-Error ('{0}: {1}' -f $code, $message)", text)
        self.assertNotIn('Write-Error "$code`:', text)

    def test_diagnose_consumes_the_runtime_manifest_contract(self):
        text = CLI.read_text(encoding="utf-8")
        self.assertIn("def _runtime_module_contract", text)
        self.assertIn("requiredModules", text)
        self.assertIn("optionalModules", text)

    def test_nsis_gate_parses_all_bundled_powershell_with_windows_powershell_51(self):
        text = NSIS_GATE.read_text(encoding="utf-8")
        self.assertIn("System.Management.Automation.Language.Parser", text)
        self.assertIn("powershell.exe", text.casefold())
        self.assertIn("setup-installed.ps1", text)
        self.assertIn("register-native-host.ps1", text)


if __name__ == "__main__":
    unittest.main()
