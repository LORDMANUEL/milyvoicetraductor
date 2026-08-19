import tempfile
import unittest
from pathlib import Path

from mily_ai.model_advisor import ModelAdvisor
from mily_ai.models import InstalledPack
from mily_ai.resource_governor import ResourceGovernor, ResourceLimits
from mily_ai.runtime_discovery import RuntimeInventory


class FakeCatalog:
    def __init__(self, pack, definition):
        self.pack = pack
        self.definition = definition

    def installed(self):
        return [self.pack]

    def definitions(self):
        return [self.definition]


class FakeInstaller:
    def __init__(self):
        self.selection = None

    def activate_selection(self, pack_id, version, backend):
        self.selection = (pack_id, version, backend)


class BackendFailureIsolationTests(unittest.TestCase):
    def test_one_broken_backend_does_not_abort_the_safe_cpu_candidate(self):
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
                    raise RuntimeError("simulated incompatible CUDA runtime")
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
                FakeCatalog(pack, definition),
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
            self.assertEqual(selection.backend, "cpu")
            self.assertEqual(installer.selection, ("adaptive", "1", "cpu"))
            self.assertEqual(
                selection.rejected["adaptive@cuda"],
                "BENCHMARK_EXECUTION_ERROR",
            )
            self.assertFalse(reports["adaptive@cuda"]["passed"])
            self.assertEqual(
                reports["adaptive@cuda"]["failures"],
                ["BENCHMARK_EXECUTION_ERROR"],
            )
            self.assertEqual(reports["adaptive"]["backend"], "cpu")


if __name__ == "__main__":
    unittest.main()
