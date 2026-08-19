import tempfile
import unittest
from pathlib import Path

from mily_ai.model_advisor import ModelAdvisor
from mily_ai.models import InstalledPack
from mily_ai.resource_governor import ResourceGovernor, ResourceLimits
from mily_ai.runtime_discovery import RuntimeInventory


class FakeCatalog:
    def __init__(self, packs, definitions):
        self._packs = packs
        self._definitions = definitions

    def installed(self):
        return list(self._packs)

    def definitions(self):
        return list(self._definitions)


class FakeInstaller:
    def __init__(self):
        self.activated = None

    def activate(self, pack_id, version):
        self.activated = (pack_id, version)


class ModelAdvisorTests(unittest.TestCase):
    @staticmethod
    def inventory():
        return RuntimeInventory(
            runtimes=frozenset({"builtin"}),
            backends=frozenset({"cpu"}),
            details={},
        )

    def test_optimizer_rejects_quality_pack_over_two_gib(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lite = InstalledPack("lite-en-es", "1", root / "lite", False, "Lite", True)
            heavy = InstalledPack("quality", "1", root / "heavy", False, "Quality", True)
            lite.path.mkdir()
            heavy.path.mkdir()
            definitions = [
                {
                    "id": "lite-en-es",
                    "version": "1",
                    "tier": "lite",
                    "routes": ["en-es"],
                    "ramMb": 900,
                    "vramMb": 0,
                    "engine": "local-ct2-lite",
                    "supportedBackends": ["cpu"],
                },
                {
                    "id": "quality",
                    "version": "1",
                    "tier": "quality",
                    "routes": ["en-es"],
                    "ramMb": 2600,
                    "vramMb": 0,
                    "engine": "local-ct2-quality",
                    "supportedBackends": ["cpu"],
                },
            ]
            reports = {
                "lite-en-es": {
                    "packId": "lite-en-es",
                    "combinedRtfP95": 0.55,
                    "endToEndP50Ms": 650,
                    "endToEndP95Ms": 1050,
                    "peakWorkingSetMb": 980,
                    "passed": True,
                },
                "quality": {
                    "packId": "quality",
                    "combinedRtfP95": 0.30,
                    "endToEndP50Ms": 500,
                    "endToEndP95Ms": 800,
                    "peakWorkingSetMb": 2650,
                    "passed": True,
                },
            }
            installer = FakeInstaller()
            advisor = ModelAdvisor(
                FakeCatalog([lite, heavy], definitions),
                installer,
                governor=ResourceGovernor(ResourceLimits()),
                inventory=self.inventory(),
                benchmarker=lambda pack, _definition: reports[pack.id],
            )
            selection, _ = advisor.optimize("en-es", force_benchmark=True)
            self.assertEqual(selection.candidate.id, "lite-en-es")
            self.assertEqual(installer.activated, ("lite-en-es", "1"))
            self.assertEqual(selection.rejected["quality"], "PROCESS_MEMORY_LIMIT")

    def test_measured_peak_overrides_optimistic_declared_ram(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            safe = InstalledPack("safe", "1", root / "safe", False, "Safe", True)
            liar = InstalledPack("liar", "1", root / "liar", False, "Liar", True)
            safe.path.mkdir()
            liar.path.mkdir()
            definitions = [
                {
                    "id": "safe",
                    "version": "1",
                    "tier": "lite",
                    "routes": ["en-es"],
                    "ramMb": 900,
                    "vramMb": 0,
                    "engine": "local-ct2-lite",
                    "supportedBackends": ["cpu"],
                },
                {
                    "id": "liar",
                    "version": "1",
                    "tier": "quality",
                    "routes": ["en-es"],
                    "ramMb": 900,
                    "vramMb": 0,
                    "engine": "local-ct2-quality",
                    "supportedBackends": ["cpu"],
                },
            ]
            reports = {
                "safe": {
                    "packId": "safe",
                    "combinedRtfP95": 0.60,
                    "endToEndP50Ms": 700,
                    "endToEndP95Ms": 1100,
                    "peakWorkingSetMb": 1200,
                    "passed": True,
                },
                "liar": {
                    "packId": "liar",
                    "combinedRtfP95": 0.20,
                    "endToEndP50Ms": 300,
                    "endToEndP95Ms": 500,
                    "peakWorkingSetMb": 2200,
                    "passed": True,
                },
            }
            advisor = ModelAdvisor(
                FakeCatalog([safe, liar], definitions),
                FakeInstaller(),
                governor=ResourceGovernor(ResourceLimits()),
                inventory=self.inventory(),
                benchmarker=lambda pack, _definition: reports[pack.id],
            )
            selection, _ = advisor.optimize("en-es", force_benchmark=True)
            self.assertEqual(selection.candidate.id, "safe")
            self.assertEqual(selection.rejected["liar"], "PROCESS_MEMORY_LIMIT")

    def test_selection_uses_end_to_end_latency_not_translation_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slow_e2e = InstalledPack(
                "slow-e2e", "1", root / "slow", False, "Slow E2E", True
            )
            fast_e2e = InstalledPack(
                "fast-e2e", "1", root / "fast", False, "Fast E2E", True
            )
            slow_e2e.path.mkdir()
            fast_e2e.path.mkdir()
            definitions = [
                {
                    "id": "slow-e2e",
                    "version": "1",
                    "tier": "lite",
                    "routes": ["en-es"],
                    "ramMb": 900,
                    "vramMb": 0,
                    "engine": "local-ct2-lite",
                    "supportedBackends": ["cpu"],
                },
                {
                    "id": "fast-e2e",
                    "version": "1",
                    "tier": "lite",
                    "routes": ["en-es"],
                    "ramMb": 900,
                    "vramMb": 0,
                    "engine": "local-ct2-lite",
                    "supportedBackends": ["cpu"],
                },
            ]
            reports = {
                "slow-e2e": {
                    "packId": "slow-e2e",
                    "asrRtfP95": 0.4,
                    "translationP50Ms": 100,
                    "translationP95Ms": 200,
                    "combinedRtfP95": 0.75,
                    "endToEndP50Ms": 1100,
                    "endToEndP95Ms": 1450,
                    "peakWorkingSetMb": 900,
                    "passed": True,
                },
                "fast-e2e": {
                    "packId": "fast-e2e",
                    "asrRtfP95": 0.4,
                    "translationP50Ms": 350,
                    "translationP95Ms": 500,
                    "combinedRtfP95": 0.40,
                    "endToEndP50Ms": 600,
                    "endToEndP95Ms": 800,
                    "peakWorkingSetMb": 900,
                    "passed": True,
                },
            }
            advisor = ModelAdvisor(
                FakeCatalog([slow_e2e, fast_e2e], definitions),
                FakeInstaller(),
                governor=ResourceGovernor(ResourceLimits()),
                inventory=self.inventory(),
                benchmarker=lambda pack, _definition: reports[pack.id],
            )
            selection, _ = advisor.optimize("en-es", force_benchmark=True)
            self.assertEqual(selection.candidate.id, "fast-e2e")


if __name__ == "__main__":
    unittest.main()
