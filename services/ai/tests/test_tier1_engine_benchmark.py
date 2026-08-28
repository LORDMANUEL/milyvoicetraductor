import unittest
from unittest.mock import patch

from mily_ai.tier1_engine_benchmark import _sample_for_route, benchmark_installed_pack


class Tier1BenchmarkRouteTests(unittest.TestCase):
    def test_four_routes_use_the_correct_source_language(self):
        expected = {
            "en-es": "en",
            "zh-es": "zh",
            "es-en": "es",
            "es-zh": "es",
        }
        for route, language in expected.items():
            with self.subTest(route=route):
                source, text = _sample_for_route(route)
                self.assertEqual(source, language)
                self.assertTrue(text.strip())

    def test_wrapper_supplies_source_specific_audio_and_route_to_stable_benchmark(self):
        definition = {"routes": ["es-zh"]}
        sentinel_audio = [0.1] * 2000
        with patch(
            "mily_ai.tier1_engine_benchmark._windows_sapi_fixture",
            return_value=sentinel_audio,
        ) as fixture, patch(
            "mily_ai.tier1_engine_benchmark.base_benchmark.benchmark_installed_pack",
            return_value={"passed": True, "route": "es-zh"},
        ) as stable:
            result = benchmark_installed_pack(object(), definition)

        fixture.assert_called_once_with("es")
        self.assertTrue(result["passed"])
        self.assertEqual(stable.call_args.kwargs["audio_samples"], sentinel_audio)


if __name__ == "__main__":
    unittest.main()
