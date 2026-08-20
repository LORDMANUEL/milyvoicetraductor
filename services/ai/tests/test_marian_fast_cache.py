import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mily_ai.marian_fast import CTranslate2FastRealtimeMarianTranslator
from mily_ai.marian_realtime import CTranslate2RealtimeMarianTranslator


class MarianFastCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_final_period_reuses_streaming_partial_translation(self):
        calls: list[tuple[str, str]] = []

        def fake_translate(_self, text: str, source_language: str) -> str:
            calls.append((text, source_language))
            return "Hola mundo"

        with patch.object(
            CTranslate2RealtimeMarianTranslator,
            "translate",
            new=fake_translate,
        ):
            translator = CTranslate2FastRealtimeMarianTranslator(
                self.path,
                "cpu",
                source_language="en",
                target_language="es",
            )
            first = translator.translate("Hello world", "en")
            final = translator.translate("Hello world.", "en")

        self.assertEqual(first, "Hola mundo")
        self.assertEqual(final, "Hola mundo.")
        self.assertEqual(calls, [("Hello world", "en")])

    def test_question_and_exclamation_never_reuse_period_cache(self):
        calls: list[str] = []

        def fake_translate(_self, text: str, _source_language: str) -> str:
            calls.append(text)
            return f"es:{text}"

        with patch.object(
            CTranslate2RealtimeMarianTranslator,
            "translate",
            new=fake_translate,
        ):
            translator = CTranslate2FastRealtimeMarianTranslator(
                self.path,
                "cpu",
                source_language="en",
                target_language="es",
            )
            translator.translate("Are you ready", "en")
            translator.translate("Are you ready?", "en")
            translator.translate("Are you ready!", "en")

        self.assertEqual(
            calls,
            ["Are you ready", "Are you ready?", "Are you ready!"],
        )

    def test_period_final_reinfers_when_partial_translation_changes_intent(self):
        calls: list[str] = []

        def fake_translate(_self, text: str, _source_language: str) -> str:
            calls.append(text)
            if text == "You are ready":
                return "¿Estás listo?"
            return "Estás listo."

        with patch.object(
            CTranslate2RealtimeMarianTranslator,
            "translate",
            new=fake_translate,
        ):
            translator = CTranslate2FastRealtimeMarianTranslator(
                self.path,
                "cpu",
                source_language="en",
                target_language="es",
            )
            partial = translator.translate("You are ready", "en")
            final = translator.translate("You are ready.", "en")

        self.assertEqual(partial, "¿Estás listo?")
        self.assertEqual(final, "Estás listo.")
        self.assertEqual(calls, ["You are ready", "You are ready."])

    def test_cache_is_bounded_and_cleared_on_unload(self):
        with patch.object(
            CTranslate2RealtimeMarianTranslator,
            "translate",
            return_value="ok",
        ), patch.object(
            CTranslate2RealtimeMarianTranslator,
            "unload",
            return_value=None,
        ) as parent_unload:
            translator = CTranslate2FastRealtimeMarianTranslator(
                self.path,
                "cpu",
                source_language="en",
                target_language="es",
                punctuation_cache_entries=2,
            )
            translator.translate("one two", "en")
            translator.translate("three four", "en")
            translator.translate("five six", "en")
            self.assertEqual(len(translator._periodless_cache), 2)
            translator.unload()

        self.assertEqual(len(translator._periodless_cache), 0)
        parent_unload.assert_called_once()


if __name__ == "__main__":
    unittest.main()
