import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mily_ai.engine_benchmark import benchmark_installed_pack
from mily_ai.models import InstalledPack


class FakeAsr:
    def warm_up(self, _language):
        pass

    def transcribe(self, _audio, language):
        return []

    def unload(self):
        pass


class FakeTranslator:
    def warm_up(self):
        pass

    def translate(self, text, _language):
        return text

    def unload(self):
        pass


class EngineBenchmarkTests(unittest.TestCase):
    def test_report_is_persisted_and_has_resource_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "components" / "asr").mkdir(parents=True)
            (path / "components" / "translation").mkdir(parents=True)
            pack = InstalledPack("lite", "1", path, False, "Lite", True)
            definition = {
                "routes": ["en-es"],
                "components": {
                    "asr": {"provider": "fake"},
                    "translation": {"provider": "fake"},
                },
            }
            with patch(
                "mily_ai.engine_benchmark.build_asr_provider",
                return_value=FakeAsr(),
            ), patch(
                "mily_ai.engine_benchmark.build_translation_provider",
                return_value=FakeTranslator(),
            ), patch(
                "mily_ai.engine_benchmark.process_working_set_mb",
                return_value=600.0,
            ):
                report = benchmark_installed_pack(pack, definition, repeats=3)
            self.assertTrue(report["passed"])
            self.assertEqual(report["packId"], "lite")
            self.assertTrue((path / "benchmark.json").is_file())
            self.assertLess(report["workingSetMb"], 2048)


if __name__ == "__main__":
    unittest.main()
