import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mily_ai.engine_benchmark import benchmark_installed_pack
from mily_ai.models import InstalledPack
from mily_ai.providers import AsrSegment


class FakeAsr:
    def __init__(self, text="hello world"):
        self.text = text
        self.closed = False
        self.finish_calls = 0

    def warm_up(self, _language):
        pass

    def transcribe(self, _audio, language):
        if not self.text:
            return []
        return [AsrSegment(0.0, 1.0, self.text, language)]

    def finish_utterance(self):
        self.finish_calls += 1

    def unload(self):
        self.closed = True


class FakeTranslator:
    def __init__(self):
        self.inputs = []
        self.closed = False

    def warm_up(self):
        pass

    def translate(self, text, _language):
        self.inputs.append(text)
        return "hola mundo" if text else ""

    def unload(self):
        self.closed = True


class EngineBenchmarkTests(unittest.TestCase):
    @staticmethod
    def definition():
        return {
            "tier": "lite",
            "routes": ["en-es"],
            "ramMb": 950,
            "vramMb": 0,
            "components": {
                "asr": {"provider": "fake"},
                "translation": {"provider": "fake"},
            },
        }

    def test_report_uses_asr_output_and_tracks_peak_memory_and_e2e(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "components" / "asr").mkdir(parents=True)
            (path / "components" / "translation").mkdir(parents=True)
            pack = InstalledPack("lite", "1", path, False, "Lite", True)
            asr = FakeAsr()
            translator = FakeTranslator()
            memories = iter(
                [
                    (350.0, 350.0),
                    (500.0, 700.0),
                    (560.0, 900.0),
                    (540.0, 900.0),
                    (520.0, 900.0),
                    (480.0, 900.0),
                ]
            )
            with patch(
                "mily_ai.engine_benchmark.build_asr_provider", return_value=asr
            ), patch(
                "mily_ai.engine_benchmark.build_translation_provider",
                return_value=translator,
            ), patch(
                "mily_ai.engine_benchmark.process_memory_snapshot_mb",
                side_effect=lambda: next(memories, (480.0, 900.0)),
            ):
                report = benchmark_installed_pack(
                    pack,
                    self.definition(),
                    repeats=3,
                    audio_samples=[0.1] * 16000,
                )
            self.assertTrue(report["passed"])
            self.assertEqual(report["packId"], "lite")
            self.assertEqual(report["peakWorkingSetMb"], 900.0)
            self.assertEqual(report["productReserveMb"], 320.0)
            self.assertEqual(report["totalProductWorkingSetMb"], 1220.0)
            self.assertIn("endToEndP95Ms", report)
            self.assertIn("combinedRtfP95", report)
            self.assertEqual(translator.inputs, ["hello world"] * 3)
            self.assertEqual(asr.finish_calls, 3)
            self.assertTrue(asr.closed)
            self.assertTrue(translator.closed)
            self.assertTrue((path / "benchmark.json").is_file())

    def test_empty_asr_result_never_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "components" / "asr").mkdir(parents=True)
            (path / "components" / "translation").mkdir(parents=True)
            pack = InstalledPack("empty", "1", path, False, "Empty", True)
            with patch(
                "mily_ai.engine_benchmark.build_asr_provider",
                return_value=FakeAsr(text=""),
            ), patch(
                "mily_ai.engine_benchmark.build_translation_provider",
                return_value=FakeTranslator(),
            ), patch(
                "mily_ai.engine_benchmark.process_memory_snapshot_mb",
                return_value=(500.0, 500.0),
            ):
                report = benchmark_installed_pack(
                    pack,
                    self.definition(),
                    repeats=3,
                    audio_samples=[0.1] * 16000,
                )
            self.assertFalse(report["passed"])
            self.assertIn("EMPTY_ASR", report["failures"])

    def test_peak_over_two_gib_never_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "components" / "asr").mkdir(parents=True)
            (path / "components" / "translation").mkdir(parents=True)
            pack = InstalledPack("heavy", "1", path, False, "Heavy", True)
            with patch(
                "mily_ai.engine_benchmark.build_asr_provider",
                return_value=FakeAsr(),
            ), patch(
                "mily_ai.engine_benchmark.build_translation_provider",
                return_value=FakeTranslator(),
            ), patch(
                "mily_ai.engine_benchmark.process_memory_snapshot_mb",
                return_value=(1700.0, 2100.0),
            ):
                report = benchmark_installed_pack(
                    pack,
                    self.definition(),
                    repeats=3,
                    audio_samples=[0.1] * 16000,
                )
            self.assertFalse(report["passed"])
            self.assertIn("RAM_HARD_LIMIT", report["failures"])

    def test_product_reserve_can_reject_engine_that_fits_in_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "components" / "asr").mkdir(parents=True)
            (path / "components" / "translation").mkdir(parents=True)
            pack = InstalledPack("isolated", "1", path, False, "Isolated", True)
            with patch(
                "mily_ai.engine_benchmark.build_asr_provider",
                return_value=FakeAsr(),
            ), patch(
                "mily_ai.engine_benchmark.build_translation_provider",
                return_value=FakeTranslator(),
            ), patch(
                "mily_ai.engine_benchmark.process_memory_snapshot_mb",
                return_value=(1700.0, 1800.0),
            ):
                report = benchmark_installed_pack(
                    pack,
                    self.definition(),
                    repeats=3,
                    audio_samples=[0.1] * 16000,
                )
            self.assertEqual(report["peakWorkingSetMb"], 1800.0)
            self.assertEqual(report["totalProductWorkingSetMb"], 2120.0)
            self.assertFalse(report["passed"])
            self.assertIn("RAM_HARD_LIMIT", report["failures"])


if __name__ == "__main__":
    unittest.main()
