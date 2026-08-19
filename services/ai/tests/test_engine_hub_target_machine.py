import json
import unittest
from pathlib import Path

from mily_ai.engine_registry import (
    BenchmarkSample,
    EngineCandidate,
    EngineRegistry,
    load_engine_descriptors,
)
from mily_ai.pipeline import TranslationRequest
from mily_ai.provider_factory import ASR_BUILDERS, TRANSLATION_BUILDERS
from mily_ai.queueing import CoalescingTranslationQueue
from mily_ai.resource_governor import (
    ResourceGovernor,
    ResourceLimits,
    RuntimeFootprint,
)
from mily_ai.telemetry import LatencyController


class TargetMachineBudgetTests(unittest.TestCase):
    """Simula la máquina objetivo de 8 GiB sin confundir RAM host con RAM MilyVoice."""

    HOST_MB = 8192
    WINDOWS_MB = 4096
    MILYVOICE_MB = 2048
    CHROME_MB = 1024
    FREE_MB = 1024

    def setUp(self):
        self.limits = ResourceLimits()
        self.governor = ResourceGovernor(self.limits)

    def test_8gb_host_budget_keeps_one_gib_free(self):
        self.assertEqual(
            self.WINDOWS_MB
            + self.MILYVOICE_MB
            + self.CHROME_MB
            + self.FREE_MB,
            self.HOST_MB,
        )
        self.assertEqual(self.limits.hard_process_mb, self.MILYVOICE_MB)

    def test_complete_product_is_allowed_at_2gib_and_rejected_one_mib_over(self):
        exact = RuntimeFootprint(
            process_mb=1200,
            desktop_mb=256,
            bridge_mb=64,
            child_process_mb=272,
            shared_gpu_mb=256,
            dedicated_vram_mb=384,
        )
        decision = self.governor.evaluate(exact)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.effective_process_mb, 2048)
        self.assertEqual(decision.vram_headroom_mb, 0)

        over = self.governor.evaluate(
            RuntimeFootprint(
                process_mb=1201,
                desktop_mb=256,
                bridge_mb=64,
                child_process_mb=272,
                shared_gpu_mb=256,
                dedicated_vram_mb=384,
            )
        )
        self.assertFalse(over.allowed)
        self.assertEqual(over.reason, "PROCESS_MEMORY_LIMIT")

    def test_512mb_vram_class_reserves_128mb_for_windows_and_browser(self):
        self.assertEqual(512 - self.limits.vram_budget_mb, 128)
        accepted = self.governor.evaluate(
            RuntimeFootprint(process_mb=900, dedicated_vram_mb=384)
        )
        rejected = self.governor.evaluate(
            RuntimeFootprint(process_mb=900, dedicated_vram_mb=385)
        )
        self.assertTrue(accepted.allowed)
        self.assertFalse(rejected.allowed)
        self.assertEqual(rejected.reason, "VRAM_LIMIT")


class EngineHubCoverageTests(unittest.TestCase):
    def setUp(self):
        self.governor = ResourceGovernor(ResourceLimits())
        self.descriptors = load_engine_descriptors()
        self.registry = EngineRegistry(
            self.governor,
            descriptors=self.descriptors,
        )

    def test_all_approved_engine_adapters_are_registered(self):
        engine_ids = {item.id for item in self.descriptors}
        self.assertTrue(
            {
                "local-ct2-lite",
                "local-ct2-quality",
                "moonshine-local",
                "sherpa-onnx-local",
                "whisper-cpp-local",
                "vosk-local",
                "google-chirp",
            }.issubset(engine_ids)
        )
        self.assertTrue(
            {
                "faster-whisper",
                "moonshine",
                "sherpa-onnx",
                "whisper-cpp",
                "vosk",
                "google-chirp",
            }.issubset(ASR_BUILDERS)
        )
        self.assertTrue(
            {"m2m100-ct2", "marian-ct2"}.issubset(TRANSLATION_BUILDERS)
        )

    def test_catalog_has_two_local_lite_paths_and_rejects_quality_on_2gib(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "mily_ai"
            / "model-packs.json"
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
        packs = {item["id"]: item for item in payload["packs"]}
        self.assertLessEqual(packs["fast-moonshine-en-es"]["ramMb"], 1200)
        self.assertLessEqual(packs["lite-en-es"]["ramMb"], 1200)
        quality = self.governor.preflight_model(
            model_ram_mb=packs["realtime-m2m100"]["ramMb"],
            dedicated_vram_mb=packs["realtime-m2m100"]["vramMb"],
        )
        self.assertFalse(quality.allowed)

    def test_auto_selection_chooses_fast_local_engine_and_rejects_cloud_and_heavy(self):
        candidates = [
            EngineCandidate(
                id="moonshine-lite",
                engine_id="moonshine-local",
                ram_mb=780,
                vram_mb=0,
                quality_score=0.84,
                benchmark=BenchmarkSample(rtf=0.35, p50_ms=330, p95_ms=520),
                backends=("cpu",),
            ),
            EngineCandidate(
                id="whisper-tiny-lite",
                engine_id="local-ct2-lite",
                ram_mb=950,
                vram_mb=0,
                quality_score=0.82,
                benchmark=BenchmarkSample(rtf=0.58, p50_ms=600, p95_ms=900),
                backends=("cpu", "cuda"),
            ),
            EngineCandidate(
                id="sherpa-external",
                engine_id="sherpa-onnx-local",
                ram_mb=820,
                vram_mb=0,
                quality_score=0.82,
                benchmark=BenchmarkSample(rtf=0.45, p50_ms=470, p95_ms=680),
                backends=("cpu",),
            ),
            EngineCandidate(
                id="whispercpp-external",
                engine_id="whisper-cpp-local",
                ram_mb=900,
                vram_mb=300,
                quality_score=0.84,
                benchmark=BenchmarkSample(rtf=0.50, p50_ms=520, p95_ms=720),
                backends=("cpu", "vulkan"),
            ),
            EngineCandidate(
                id="vosk-legacy",
                engine_id="vosk-local",
                ram_mb=520,
                vram_mb=0,
                quality_score=0.70,
                benchmark=BenchmarkSample(rtf=0.55, p50_ms=590, p95_ms=850),
                backends=("cpu",),
            ),
            EngineCandidate(
                id="quality-heavy",
                engine_id="local-ct2-quality",
                ram_mb=2300,
                vram_mb=1600,
                quality_score=0.95,
                benchmark=BenchmarkSample(rtf=0.15, p50_ms=260, p95_ms=350),
                backends=("cuda", "cpu"),
            ),
            EngineCandidate(
                id="google-cloud",
                engine_id="google-chirp",
                ram_mb=120,
                vram_mb=0,
                quality_score=0.96,
                benchmark=BenchmarkSample(rtf=0.08, p50_ms=120, p95_ms=200),
                backends=("cloud",),
            ),
        ]
        selected = self.registry.select(
            route="en-es",
            candidates=candidates,
            installed_runtimes={
                "builtin",
                "moonshine",
                "sherpa-onnx",
                "whisper-cpp",
                "vosk",
                "google-cloud",
            },
            available_backends={"cpu", "vulkan", "cloud"},
            allow_cloud=False,
        )
        self.assertEqual(selected.candidate.id, "moonshine-lite")
        self.assertEqual(selected.backend, "cpu")
        self.assertEqual(
            selected.rejected["quality-heavy"], "PROCESS_MEMORY_LIMIT"
        )
        self.assertEqual(
            selected.rejected["google-cloud"], "CLOUD_CONSENT_REQUIRED"
        )

    def test_pressure_controller_degrades_and_recovers_with_hysteresis(self):
        controller = LatencyController(
            memory_provider=lambda: 0.0,
            product_reserve_mb=0.0,
            recovery_samples=2,
        )
        self.assertEqual(controller.classify(0, 0, 0.40, process_memory_mb=800), "healthy")
        self.assertEqual(controller.classify(500, 3, 0.90, process_memory_mb=1250), "pressure")
        self.assertEqual(controller.classify(1200, 6, 1.30, process_memory_mb=1650), "catch_up")
        self.assertEqual(controller.classify(2400, 8, 1.90, process_memory_mb=1920), "rescue")
        self.assertFalse(controller.allow_partial_asr("rescue"))
        self.assertFalse(controller.allow_partial_translation("rescue"))
        self.assertFalse(controller.allow_speaker_detection("rescue"))
        self.assertFalse(controller.allow_tts("rescue"))

        expected = ["rescue", "catch_up", "catch_up", "pressure", "pressure", "healthy"]
        recovered = [
            controller.classify(0, 0, 0.30, process_memory_mb=700)
            for _ in expected
        ]
        self.assertEqual(recovered, expected)


class TenMinuteBacklogSimulationTests(unittest.IsolatedAsyncioTestCase):
    async def test_ten_minutes_of_fast_speech_do_not_accumulate_final_backlog(self):
        now = [10.0]
        queue = CoalescingTranslationQueue(
            maxsize=8,
            partial_ttl_seconds=0.75,
            clock=lambda: now[0],
        )
        events: list[tuple[float, TranslationRequest]] = []
        utterances = 500  # 500 x 1.2 s = 10 minutes.
        for index in range(utterances):
            base = 10.0 + index * 1.2
            utterance_id = f"u-{index}"
            for offset, text in (
                (0.30, "partial one"),
                (0.60, "partial one two"),
                (0.90, "partial one two three"),
            ):
                created = base + offset
                events.append(
                    (
                        created,
                        TranslationRequest(
                            type="translation.partial",
                            start=base,
                            end=created,
                            original=text,
                            language="en",
                            utterance_id=utterance_id,
                            created_at=created,
                        ),
                    )
                )
            final_at = base + 1.0
            events.append(
                (
                    final_at,
                    TranslationRequest(
                        type="translation.final",
                        start=base,
                        end=final_at,
                        original="final sentence",
                        language="en",
                        utterance_id=utterance_id,
                        created_at=final_at,
                    ),
                )
            )

        worker_free_at = 10.0
        max_depth = 0
        max_start_age = 0.0
        final_results = 0
        last_event_at = events[-1][0]

        async def process_one() -> None:
            nonlocal worker_free_at, max_start_age, final_results
            item = await queue.get()
            self.assertIsNotNone(item)
            assert item is not None
            started_at = max(worker_free_at, item.created_at)
            max_start_age = max(max_start_age, started_at - item.created_at)
            worker_free_at = started_at + (0.45 if item.final else 0.28)
            if item.final:
                final_results += 1
            queue.task_done()

        for event_at, request in events:
            while not queue.empty() and worker_free_at <= event_at:
                now[0] = worker_free_at
                await process_one()
            now[0] = event_at
            self.assertTrue(await queue.put(request))
            max_depth = max(max_depth, queue.qsize())

        while not queue.empty():
            now[0] = max(now[0], worker_free_at)
            await process_one()
        await queue.join()

        self.assertEqual(final_results, utterances)
        self.assertLessEqual(max_depth, 2)
        self.assertLessEqual(max_start_age, 0.70)
        self.assertLessEqual(worker_free_at - last_event_at, 0.70)
        self.assertTrue(queue.empty())


if __name__ == "__main__":
    unittest.main()
