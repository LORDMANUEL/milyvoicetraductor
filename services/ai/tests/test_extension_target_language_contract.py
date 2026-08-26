import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
POPUP = ROOT / "apps/extension/popup.html"
POPUP_JS = ROOT / "apps/extension/popup.js"
BACKGROUND = ROOT / "apps/extension/background.js"
OFFSCREEN = ROOT / "apps/extension/offscreen.js"
TTS = ROOT / "apps/extension/tts.js"


class ExtensionTargetLanguageContractTests(unittest.TestCase):
    def test_popup_exposes_target_language_selector(self):
        html = POPUP.read_text(encoding="utf-8")
        self.assertIn('id="target"', html)
        for value in ("es", "en", "zh"):
            self.assertIn(f'value="{value}"', html)

    def test_popup_persists_target_language(self):
        source = POPUP_JS.read_text(encoding="utf-8")
        self.assertIn("targetLanguage", source)
        self.assertIn("target.value", source)

    def test_background_and_offscreen_propagate_dynamic_target(self):
        background = BACKGROUND.read_text(encoding="utf-8")
        offscreen = OFFSCREEN.read_text(encoding="utf-8")
        self.assertIn("targetLanguage: options.targetLanguage", background)
        self.assertIn("targetLanguage: message.targetLanguage", offscreen)
        self.assertNotIn("targetLanguage: 'es'", offscreen)

    def test_tts_is_target_language_aware(self):
        source = TTS.read_text(encoding="utf-8")
        self.assertIn("targetLanguage", source)
        self.assertIn("zh-CN", source)
        self.assertIn("en-US", source)
        self.assertIn("es-ES", source)


if __name__ == "__main__":
    unittest.main()
