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
        self.selection = None

    def activate_selection(self, pack_id, version, backend):
        self.selection = (pack_id, version, backend)


class MeasuredSharedGpuMemoryTests(unittest.TestCase):
    def test_shared_igpu_memory_is_added_to_measured_total_product(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            safe = InstalledPack("safe", "1", root / "safe", False, "Safe", True)
            igpu = InstalledPack("igpu", "1", root / "igpu", False, "iGPU", True)
            safe.path.mkdir()
            igpu.path.mkdir()
            definitions = [
                {
                    "id": "safe",
                    "version": "1",
                    "tier": "lite",
                    "routes": ["en-es"],
                    "ramMb": 900,
                    "vramMb": 0,
                    "sharedGpuMb": 0,
                    "engine": "local-ct2-lite",
                    "supportedBackends": ["cpu"],
                },
                {
                    "id": "igpu",
                    "version": "1",
                    "tier": "lite",
                    "routes": ["en-es"],
                    "ramMb": 900,
                    "vramMb": 0,
                    "sharedGpuMb": 200,
                    "engine": "local-ct2-lite",
                    "supportedBackends": ["cpu"],
                },
            ]
            reports = {
                "safe": {
                    "packId": "safe",
                    "backend": "cpu",
                    "combinedRtfP95": 0.55,
                    "endToEndP50Ms": 650,
                    "endToEndP95Ms": 950,
                    "enginePeakWorkingSetMb": 980,
                    "totalProductWorkingSetMb": 1450,
                    "passed": True,
                },
                "igpu": {
                    "packId": "igpu",
                    "backend": "cpu",
                    "combinedRtfP95": 0.15,
                    "endToEndP50Ms": 250,
                    "endToEndP95Ms": 400,
                    "enginePeakWorkingSetMb": 900,
                    "totalProductWorkingSetMb": 1900,
                    "passed": True,
                },
            }
            installer = FakeInstaller()
            advisor = ModelAdvisor(
                FakeCatalog([safe, igpu], definitions),
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
            self.assertEqual(selection.rejected["igpu"], "PROCESS_MEMORY_LIMIT")
            self.assertEqual(installer.selection, ("safe", "1", "cpu"))


if __name__ == "__main__":
    unittest.main()
