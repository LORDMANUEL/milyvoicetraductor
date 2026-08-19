import unittest

from mily_ai.engine_registry import (
    BenchmarkSample,
    EngineCandidate,
    EngineDescriptor,
    EngineRegistry,
)
from mily_ai.resource_governor import ResourceGovernor, ResourceLimits


class EngineRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = EngineRegistry(
            ResourceGovernor(ResourceLimits()),
            descriptors=[
                EngineDescriptor(
                    id="cpu-lite",
                    kind="pipeline",
                    title="CPU Lite",
                    routes=("en-es",),
                    runtime="builtin",
                    cloud=False,
                    commercial_use=True,
                ),
                EngineDescriptor(
                    id="quality-heavy",
                    kind="pipeline",
                    title="Quality Heavy",
                    routes=("en-es",),
                    runtime="builtin",
                    cloud=False,
                    commercial_use=True,
                ),
                EngineDescriptor(
                    id="google-chirp",
                    kind="asr",
                    title="Google Chirp",
                    routes=("en-es",),
                    runtime="google-cloud",
                    cloud=True,
                    commercial_use=True,
                ),
            ],
        )

    def test_out_of_budget_candidate_is_never_selected(self):
        selected = self.registry.select(
            route="en-es",
            candidates=[
                EngineCandidate(
                    id="quality-heavy",
                    engine_id="quality-heavy",
                    ram_mb=2300,
                    vram_mb=0,
                    quality_score=0.99,
                    benchmark=BenchmarkSample(rtf=0.2, p95_ms=500),
                ),
                EngineCandidate(
                    id="cpu-lite",
                    engine_id="cpu-lite",
                    ram_mb=900,
                    vram_mb=0,
                    quality_score=0.82,
                    benchmark=BenchmarkSample(rtf=0.55, p95_ms=950),
                ),
            ],
            installed_runtimes={"builtin"},
        )
        self.assertEqual(selected.candidate.id, "cpu-lite")
        self.assertIn("quality-heavy", selected.rejected)

    def test_product_reserve_is_applied_during_selection(self):
        selected = self.registry.select(
            route="en-es",
            candidates=[
                EngineCandidate(
                    id="quality-heavy",
                    engine_id="quality-heavy",
                    ram_mb=1800,
                    vram_mb=0,
                    quality_score=0.99,
                    benchmark=BenchmarkSample(rtf=0.2, p95_ms=400),
                ),
                EngineCandidate(
                    id="cpu-lite",
                    engine_id="cpu-lite",
                    ram_mb=1200,
                    vram_mb=0,
                    quality_score=0.80,
                    benchmark=BenchmarkSample(rtf=0.55, p95_ms=950),
                ),
            ],
            installed_runtimes={"builtin"},
        )
        self.assertEqual(selected.candidate.id, "cpu-lite")
        self.assertEqual(
            selected.rejected["quality-heavy"], "PROCESS_MEMORY_LIMIT"
        )

    def test_cloud_engine_requires_explicit_consent(self):
        candidate = EngineCandidate(
            id="chirp",
            engine_id="google-chirp",
            ram_mb=120,
            vram_mb=0,
            quality_score=0.95,
            benchmark=BenchmarkSample(rtf=0.1, p95_ms=300),
        )
        with self.assertRaisesRegex(RuntimeError, "No existe un motor compatible"):
            self.registry.select(
                route="en-es",
                candidates=[candidate],
                installed_runtimes={"google-cloud"},
                allow_cloud=False,
            )
        selected = self.registry.select(
            route="en-es",
            candidates=[candidate],
            installed_runtimes={"google-cloud"},
            allow_cloud=True,
        )
        self.assertEqual(selected.candidate.id, "chirp")

    def test_cpu_fallback_remains_selectable_without_gpu(self):
        selected = self.registry.select(
            route="en-es",
            candidates=[
                EngineCandidate(
                    id="cpu-lite",
                    engine_id="cpu-lite",
                    ram_mb=860,
                    vram_mb=0,
                    quality_score=0.80,
                    benchmark=BenchmarkSample(rtf=0.65, p95_ms=1100),
                    backends=("cpu",),
                )
            ],
            installed_runtimes={"builtin"},
            available_backends={"cpu"},
        )
        self.assertEqual(selected.backend, "cpu")

    def test_route_and_runtime_are_enforced(self):
        with self.assertRaisesRegex(RuntimeError, "No existe un motor compatible"):
            self.registry.select(
                route="zh-es",
                candidates=[
                    EngineCandidate(
                        id="cpu-lite",
                        engine_id="cpu-lite",
                        ram_mb=800,
                        vram_mb=0,
                        quality_score=0.8,
                        benchmark=BenchmarkSample(rtf=0.5, p95_ms=900),
                    )
                ],
                installed_runtimes={"builtin"},
            )


if __name__ == "__main__":
    unittest.main()
