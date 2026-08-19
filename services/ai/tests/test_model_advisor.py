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
                    "asrRtfP95": 0.55,
                    "translationP50Ms": 250,
                    "translationP95Ms": 420,
                    "passed": True,
                },
                "quality": {
                    "packId": "quality",
                    "asrRtfP95": 0.30,
                    "translationP50Ms": 180,
                    "translationP95Ms": 300,
                    "passed": True,
                },
            }
            installer = FakeInstaller()
            advisor = ModelAdvisor(
                FakeCatalog([lite, heavy], definitions),
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
            self.assertEqual(selection.candidate.id, "lite-en-es")
            self.assertEqual(installer.activated, ("lite-en-es", "1"))
            self.assertEqual(selection.rejected["quality"], "PROCESS_MEMORY_LIMIT")


if __name__ == "__main__":
    unittest.main()
