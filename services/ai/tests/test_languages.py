"""Contrato lingüístico Tier 1 independiente del protocolo realtime actual."""

from __future__ import annotations

import unittest

from mily_ai.languages import (
    TIER1_LANGUAGES,
    get_tier1_route,
    is_tier1_route,
    normalize_language,
)


class LanguageRoutingTests(unittest.TestCase):
    def test_normalizes_supported_locale_aliases(self):
        self.assertEqual(normalize_language("en-US"), "en")
        self.assertEqual(normalize_language("es-419"), "es")
        self.assertEqual(normalize_language("zh-CN"), "zh")
        self.assertEqual(normalize_language("cmn"), "zh")
        self.assertEqual(normalize_language("auto"), "auto")

    def test_tier1_languages_are_spanish_english_and_mandarin(self):
        self.assertEqual(TIER1_LANGUAGES, frozenset({"es", "en", "zh"}))

    def test_four_priority_routes_are_bidirectional_through_spanish(self):
        expected = {
            ("en", "es"),
            ("es", "en"),
            ("zh", "es"),
            ("es", "zh"),
        }
        actual = {
            (source, target)
            for source in TIER1_LANGUAGES
            for target in TIER1_LANGUAGES
            if is_tier1_route(source, target)
        }
        self.assertEqual(actual, expected)

    def test_route_profile_is_direction_specific(self):
        self.assertEqual(get_tier1_route("en", "es").profile, "en-es-realtime")
        self.assertEqual(get_tier1_route("es", "en").profile, "es-en-realtime")
        self.assertEqual(get_tier1_route("zh", "es").profile, "zh-es-realtime")
        self.assertEqual(get_tier1_route("es", "zh").profile, "es-zh-realtime")

    def test_auto_requires_language_detection_before_route_selection(self):
        self.assertIsNone(get_tier1_route("auto", "es"))

    def test_english_to_chinese_is_not_a_tier1_fast_path(self):
        self.assertFalse(is_tier1_route("en", "zh"))
        self.assertIsNone(get_tier1_route("en", "zh"))


if __name__ == "__main__":
    unittest.main()
