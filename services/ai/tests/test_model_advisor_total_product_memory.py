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


class TotalProductMemorySelectionTests(unittest.TestCase):
    def test_optimizer_rejects_measured_total_product_above_two_gib(self):
        """El selector no puede ignorar Desktop/bridge/iGPU medidos."""

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            safe = InstalledPack("safe", "1", root / "safe", False, "Safe", True)
            misleading = InstalledPack(
                "misleading", "1", root / "misleading", False, "Misleading", True
            )
            safe.path.mkdir()
            misleading.path.mkdir()
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
                    "id": "misleading",
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
                    "combinedRtfP95": 0.55,
                    "endToEndP50Ms": 650,
                    "endToEndP95Ms": 950,
                    "enginePeakWorkingSetMb": 1000,
                    "totalProductWorkingSetMb": 1400,
                    "passed": True,
                },
                "misleading": {
                    "packId": "misleading",
                    "combinedRtfP95": 0.15,
                    "endToEndP50Ms": 250,
                    "endToEndP95Ms": 400,
                    "enginePeakWorkingSetMb": 900,
                    "totalProductWorkingSetMb": 2200,
                    "passed": True,
                },
            }
            installer = FakeInstaller()
            advisor = ModelAdvisor(
                FakeCatalog([safe, misleading], definitions),
                installer,
                governor=ResourceGovernor(ResourceLimits()),
                inventory=RuntimeInventory(
                    runtimes=frozenset({"builtin"}),
                    backends=frozenset({"cpu"}),
                    details={},
                ),
                benchmarker=lambda pack, _definition: reports[pack.id],
            )

            selection, _ = advisor.optimize("en-es", force_benchmark=True)

            self.assertEqual(selection.candidate.id, "safe")
            self.assertEqual(installer.activated, ("safe", "1"))
            self.assertEqual(
                selection.rejected["misleading"], "PROCESS_MEMORY_LIMIT"
            )


if __name__ == "__main__":
    unittest.main()
