import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REALTIME = ROOT / "apps/desktop/src/lib/realtime.ts"
ROUTE = ROOT / "apps/desktop/src/lib/tier1-route.ts"
LIVE = ROOT / "apps/desktop/src/pages/Tier1LiveTranslation.svelte"
APP = ROOT / "apps/desktop/src/App.svelte"


class DesktopTargetLanguageContractTests(unittest.TestCase):
    def test_realtime_client_has_no_fixed_spanish_target(self):
        source = REALTIME.read_text(encoding="utf-8")
        self.assertIn("targetLanguage", source)
        self.assertIn("targetLanguage: this.targetLanguage", source)
        self.assertNotIn("targetLanguage: 'es'", source)
        self.assertIn("getTier1TargetLanguage", source)

    def test_tier1_live_wrapper_exposes_three_targets(self):
        source = LIVE.read_text(encoding="utf-8")
        self.assertIn("targetLanguage", source)
        for value in ("es", "en", "zh"):
            self.assertIn(f'<option value="{value}">', source)

    def test_desktop_tts_has_all_tier1_output_locales(self):
        source = ROUTE.read_text(encoding="utf-8")
        for locale in ("es-ES", "en-US", "zh-CN"):
            self.assertIn(locale, source)

    def test_app_uses_tier1_wrapper_without_replacing_stable_page(self):
        source = APP.read_text(encoding="utf-8")
        self.assertIn("./pages/Tier1LiveTranslation.svelte", source)
        wrapper = LIVE.read_text(encoding="utf-8")
        self.assertIn("./LiveTranslation.svelte", wrapper)

    def test_outbound_wrapper_installs_and_benchmarks_preferred_lite_pack(self):
        wrapper = LIVE.read_text(encoding="utf-8")
        self.assertIn("desktopApi.getModelCatalog", wrapper)
        self.assertIn("desktopApi.installModel", wrapper)
        self.assertIn("desktopApi.optimizeModels", wrapper)
        self.assertIn("lite-es-en", wrapper)
        self.assertIn("lite-es-zh", wrapper)
        self.assertIn("resourceAllowed", wrapper)


if __name__ == "__main__":
    unittest.main()
