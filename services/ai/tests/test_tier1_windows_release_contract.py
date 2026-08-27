import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CI = ROOT / ".github/workflows/ci.yml"
ES_EN = ROOT / "installer/windows/test-es-en-lite.ps1"
ES_ZH = ROOT / "installer/windows/test-es-zh-lite.ps1"


class Tier1WindowsReleaseContractTests(unittest.TestCase):
    def test_windows_has_real_outbound_benchmark_scripts(self):
        self.assertTrue(ES_EN.is_file(), "Falta benchmark Windows ES→EN")
        self.assertTrue(ES_ZH.is_file(), "Falta benchmark Windows ES→ZH")
        en_source = ES_EN.read_text(encoding="utf-8")
        zh_source = ES_ZH.read_text(encoding="utf-8")
        self.assertIn("lite-es-en", en_source)
        self.assertIn("benchmark_tier1_installed_pack", en_source)
        self.assertIn("MilyVoiceTraductor-2.1.0-EsEnLiteBench.json", en_source)
        self.assertIn("lite-es-zh", zh_source)
        self.assertIn("benchmark_tier1_installed_pack", zh_source)
        self.assertIn("MilyVoiceTraductor-2.1.0-EsZhLiteBench.json", zh_source)

    def test_ci_requires_and_packages_both_outbound_reports(self):
        source = CI.read_text(encoding="utf-8")
        self.assertIn("test-es-en-lite.ps1", source)
        self.assertIn("test-es-zh-lite.ps1", source)
        self.assertIn("MilyVoiceTraductor-2.1.0-EsEnLiteBench.json", source)
        self.assertIn("MilyVoiceTraductor-2.1.0-EsZhLiteBench.json", source)
        self.assertNotIn("continue-on-error: true\n        shell: pwsh\n        run: .\\installer\\windows\\test-es-en-lite.ps1", source)
        self.assertNotIn("continue-on-error: true\n        shell: pwsh\n        run: .\\installer\\windows\\test-es-zh-lite.ps1", source)


if __name__ == "__main__":
    unittest.main()
