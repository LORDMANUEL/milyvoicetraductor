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


class ModelAdvisorBackendMatrixTests(unittest.TestCase):
    def test_optimizer_benchmarks_every_available_backend_and_persists_winner(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "adaptive"
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
            calls = []

            def benchmark(_pack, _definition, *, compute_profile):
                calls.append(compute_profile)
                if compute_profile == "cuda":
                    return {
                        "packId": "adaptive",
                        "backend": "cuda",
                        "combinedRtfP95": 0.18,
                        "endToEndP50Ms": 240,
                        "endToEndP95Ms": 390,
                        "enginePeakWorkingSetMb": 760,
                        "totalProductWorkingSetMb": 1080,
                        "passed": True,
                    }
                return {
                    "packId": "adaptive",
                    "backend": "cpu",
                    "combinedRtfP95": 0.52,
                    "endToEndP50Ms": 590,
                    "endToEndP95Ms": 920,
                    "enginePeakWorkingSetMb": 920,
                    "totalProductWorkingSetMb": 1240,
                    "passed": True,
                }

            installer = FakeInstaller()
            advisor = ModelAdvisor(
                FakeCatalog([pack], [definition]),
                installer,
                governor=ResourceGovernor(ResourceLimits()),
                inventory=RuntimeInventory(
                    runtimes=frozenset({"builtin"}),
                    backends=frozenset({"cpu", "cuda"}),
                    details={},
                ),
                benchmarker=benchmark,
            )

            selection, reports = advisor.optimize("en-es", force_benchmark=True)

            self.assertEqual(set(calls), {"cpu", "cuda"})
            self.assertEqual(selection.candidate.id, "adaptive")
            self.assertEqual(selection.backend, "cuda")
            self.assertEqual(installer.selection, ("adaptive", "1", "cuda"))
            self.assertIn("adaptive@cpu", reports)
            self.assertIn("adaptive@cuda", reports)
            self.assertEqual(reports["adaptive"]["backend"], "cuda")

    def test_backend_that_is_not_available_is_not_benchmarked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "adaptive"
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
            calls = []

            def benchmark(_pack, _definition, *, compute_profile):
                calls.append(compute_profile)
                return {
                    "packId": "adaptive",
                    "backend": compute_profile,
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
                    backends=frozenset({"cpu"}),
                    details={},
                ),
                benchmarker=benchmark,
            )

            selection, _ = advisor.optimize("en-es", force_benchmark=True)

            self.assertEqual(calls, ["cpu"])
            self.assertEqual(selection.backend, "cpu")

    def test_cloud_backend_is_never_benchmarked_without_consent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cloud"
            path.mkdir()
            pack = InstalledPack("cloud", "1", path, False, "Cloud", True)
            definition = {
                "id": "cloud",
                "version": "1",
                "tier": "quality",
                "routes": ["en-es"],
                "ramMb": 120,
                "vramMb": 0,
                "engine": "google-chirp",
                "supportedBackends": ["cloud"],
            }
            calls = []

            def benchmark(_pack, _definition, *, compute_profile):
                calls.append(compute_profile)
                raise AssertionError("La nube no debe ejecutarse sin consentimiento")

            advisor = ModelAdvisor(
                FakeCatalog([pack], [definition]),
                FakeInstaller(),
                governor=ResourceGovernor(ResourceLimits()),
                inventory=RuntimeInventory(
                    runtimes=frozenset({"google-cloud"}),
                    backends=frozenset({"cloud"}),
                    details={},
                ),
                benchmarker=benchmark,
            )

            with self.assertRaisesRegex(RuntimeError, "No existe un motor compatible"):
                advisor.optimize("en-es", allow_cloud=False, force_benchmark=True)
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
