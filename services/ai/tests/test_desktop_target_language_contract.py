import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REALTIME = ROOT / "apps/desktop/src/lib/realtime.ts"
LIVE = ROOT / "apps/desktop/src/pages/LiveTranslation.svelte"


class DesktopTargetLanguageContractTests(unittest.TestCase):
    def test_realtime_client_has_no_fixed_spanish_target(self):
        source = REALTIME.read_text(encoding="utf-8")
        self.assertIn("targetLanguage", source)
        self.assertIn("targetLanguage: this.targetLanguage", source)
        self.assertNotIn("targetLanguage: 'es'", source)

    def test_live_translation_exposes_three_targets(self):
        source = LIVE.read_text(encoding="utf-8")
        self.assertIn("targetLanguage", source)
        for value in ("es", "en", "zh"):
            self.assertIn(f'<option value="{value}">', source)

    def test_desktop_tts_has_all_tier1_output_locales(self):
        source = LIVE.read_text(encoding="utf-8")
        for locale in ("es-ES", "en-US", "zh-CN"):
            self.assertIn(locale, source)


if __name__ == "__main__":
    unittest.main()
