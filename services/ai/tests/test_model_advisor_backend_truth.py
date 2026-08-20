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


class ModelAdvisorBackendTruthTests(unittest.TestCase):
    def test_describe_catalog_uses_declared_memory_without_undefined_state(self):
        definition = {
            "id": "lite",
            "version": "1",
            "tier": "lite",
            "routes": ["en-es"],
            "ramMb": 900,
            "vramMb": 0,
            "engine": "local-ct2-lite",
            "supportedBackends": ["cpu"],
        }
        advisor = ModelAdvisor(
            FakeCatalog([], [definition]),
            FakeInstaller(),
            governor=ResourceGovernor(ResourceLimits()),
            inventory=RuntimeInventory(
                runtimes=frozenset({"builtin"}),
                backends=frozenset({"cpu"}),
                details={},
            ),
        )
        described = advisor.describe_catalog()
        self.assertEqual(len(described), 1)
        self.assertTrue(described[0]["resourceAllowed"])
        self.assertLessEqual(described[0]["estimatedTotalProductMb"], 2048)

    def test_selector_never_claims_cuda_from_a_cpu_benchmark(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pack"
            path.mkdir()
            pack = InstalledPack("adaptive", "1", path, False, "Adaptive", True)
            definition = {
                "id": "adaptive",
                "version": "1",
                "tier": "lite",
                "routes": ["en-es"],
                "ramMb": 900,
                "vramMb": 300,
                "engine": "local-ct2-lite",
                "supportedBackends": ["cuda", "cpu"],
            }
            report = {
                "packId": "adaptive",
                "backend": "cpu",
                "combinedRtfP95": 0.50,
                "endToEndP50Ms": 600,
                "endToEndP95Ms": 900,
                "enginePeakWorkingSetMb": 900,
                "totalProductWorkingSetMb": 1220,
                "passed": True,
            }
            advisor = ModelAdvisor(
                FakeCatalog([pack], [definition]),
                FakeInstaller(),
                governor=ResourceGovernor(ResourceLimits()),
                inventory=RuntimeInventory(
                    runtimes=frozenset({"builtin"}),
                    backends=frozenset({"cpu", "cuda"}),
                    details={},
                ),
                benchmarker=lambda _pack, _definition: report,
            )
            selection, _ = advisor.optimize("en-es", force_benchmark=True)
            self.assertEqual(selection.backend, "cpu")

    def test_measured_cuda_is_used_only_when_report_and_inventory_agree(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pack"
            path.mkdir()
            pack = InstalledPack("adaptive", "1", path, False, "Adaptive", True)
            definition = {
                "id": "adaptive",
                "version": "1",
                "tier": "lite",
                "routes": ["en-es"],
                "ramMb": 900,
                "vramMb": 300,
                "engine": "local-ct2-lite",
                "supportedBackends": ["cuda", "cpu"],
            }
            report = {
                "packId": "adaptive",
                "backend": "cuda",
                "combinedRtfP95": 0.20,
                "endToEndP50Ms": 250,
                "endToEndP95Ms": 400,
                "enginePeakWorkingSetMb": 750,
                "totalProductWorkingSetMb": 1100,
                "passed": True,
            }
            advisor = ModelAdvisor(
                FakeCatalog([pack], [definition]),
                FakeInstaller(),
                governor=ResourceGovernor(ResourceLimits()),
                inventory=RuntimeInventory(
                    runtimes=frozenset({"builtin"}),
                    backends=frozenset({"cpu", "cuda"}),
                    details={},
                ),
                benchmarker=lambda _pack, _definition: report,
            )
            selection, _ = advisor.optimize("en-es", force_benchmark=True)
            self.assertEqual(selection.backend, "cuda")


if __name__ == "__main__":
    unittest.main()
