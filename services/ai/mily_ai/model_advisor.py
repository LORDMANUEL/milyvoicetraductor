"""Asesor que benchmarkea packs instalados y activa el ganador seguro."""

from __future__ import annotations

import inspect
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from .engine_benchmark import benchmark_installed_pack
from .engine_registry import (
    BenchmarkSample,
    EngineCandidate,
    EngineRegistry,
    EngineSelection,
    load_engine_descriptors,
)
from .models import HuggingFacePackInstaller, InstalledPack, ModelCatalog
from .provider_factory import normalize_backend
from .resource_governor import (
    ResourceGovernor,
    ResourceLimits,
    RuntimeFootprint,
)
from .runtime_discovery import RuntimeInventory, discover_runtime_inventory

BenchmarkFunction = Callable[..., dict[str, Any]]

_TIER_QUALITY = {
    "lite": 0.80,
    "balanced": 0.87,
    "quality": 0.94,
    "experimental": 0.68,
}


def _finite_non_negative(value: object, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed < 0 or parsed != parsed or parsed in {
        float("inf"),
        float("-inf"),
    }:
        return default
    return parsed


def _supports_compute_profile(benchmarker: BenchmarkFunction) -> bool:
    try:
        parameters = inspect.signature(benchmarker).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(
        parameter.name == "compute_profile"
        or parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters
    )


class ModelAdvisor:
    def __init__(
        self,
        catalog: ModelCatalog,
        installer: HuggingFacePackInstaller,
        *,
        governor: ResourceGovernor | None = None,
        inventory: RuntimeInventory | None = None,
        benchmarker: BenchmarkFunction | None = None,
    ):
        self.catalog = catalog
        self.installer = installer
        self.governor = governor or ResourceGovernor(ResourceLimits())
        self.inventory = inventory or discover_runtime_inventory()
        self.benchmarker = benchmarker or benchmark_installed_pack
        self._benchmarker_supports_profile = _supports_compute_profile(
            self.benchmarker
        )
        self.registry = EngineRegistry(
            self.governor, descriptors=load_engine_descriptors()
        )

    @staticmethod
    def _declared_engine_ram(definition: dict[str, Any]) -> float:
        return _finite_non_negative(definition.get("ramMb", 0), 0.0)

    @staticmethod
    def _engine_ram_from_report(report: dict[str, Any]) -> float:
        return _finite_non_negative(
            report.get(
                "enginePeakWorkingSetMb",
                report.get(
                    "peakWorkingSetMb",
                    report.get("workingSetMb", 0.0),
                ),
            ),
            0.0,
        )

    @staticmethod
    def _shared_gpu(definition: dict[str, Any]) -> float:
        return _finite_non_negative(definition.get("sharedGpuMb", 0), 0.0)

    def _effective_measured_total(
        self,
        definition: dict[str, Any],
        report: dict[str, Any],
    ) -> float:
        total = _finite_non_negative(
            report.get("totalProductWorkingSetMb", 0.0), 0.0
        )
        if total <= 0:
            return 0.0
        if not bool(report.get("totalProductIncludesSharedGpu", False)):
            total += self._shared_gpu(definition)
        return total

    def _declared_decision(self, definition: dict[str, Any]):
        return self.governor.preflight_model(
            model_ram_mb=self._declared_engine_ram(definition),
            shared_gpu_mb=self._shared_gpu(definition),
            dedicated_vram_mb=_finite_non_negative(
                definition.get("vramMb", 0), 0.0
            ),
        )

    def _measured_decision(
        self,
        definition: dict[str, Any],
        report: dict[str, Any],
    ):
        total_product = self._effective_measured_total(definition, report)
        dedicated_vram = _finite_non_negative(
            definition.get("vramMb", 0), 0.0
        )
        if total_product > 0:
            return self.governor.evaluate(
                RuntimeFootprint(
                    process_mb=total_product,
                    dedicated_vram_mb=dedicated_vram,
                )
            )
        return self.governor.preflight_model(
            model_ram_mb=max(
                self._declared_engine_ram(definition),
                self._engine_ram_from_report(report),
            ),
            shared_gpu_mb=self._shared_gpu(definition),
            dedicated_vram_mb=dedicated_vram,
        )

    def describe_catalog(self) -> list[dict[str, Any]]:
        installed = {
            f"{item.id}@{item.version}": item
            for item in self.catalog.installed()
        }
        active_backend = getattr(self.catalog, "active_backend", lambda: "auto")()
        output: list[dict[str, Any]] = []
        for definition in self.catalog.definitions():
            ref = f"{definition['id']}@{definition['version']}"
            decision = self._declared_decision(definition)
            item = dict(definition)
            current = installed.get(ref)
            item["installed"] = current is not None
            item["active"] = bool(current and current.active)
            item["activeBackend"] = active_backend if item["active"] else None
            item["resourceAllowed"] = decision.allowed
            item["resourceMode"] = decision.mode
            item["resourceReason"] = decision.reason
            item["estimatedTotalProductMb"] = round(
                decision.effective_process_mb, 1
            )
            item["productReserveMb"] = self.governor.limits.product_reserve_mb
            if current is not None:
                report = self._load_report(
                    current, active_backend if current.active else None
                )
                item["benchmark"] = report
                if report is not None:
                    measured_engine = self._engine_ram_from_report(report)
                    measured_total = self._effective_measured_total(
                        definition, report
                    )
                    measured_decision = self._measured_decision(
                        definition, report
                    )
                    if measured_total <= 0:
                        measured_total = measured_decision.effective_process_mb
                    item["measuredEngineRamMb"] = measured_engine
                    item["measuredTotalProductMb"] = measured_total
                    item["measuredRamMb"] = measured_total
                    item["resourceAllowed"] = measured_decision.allowed
                    item["resourceMode"] = measured_decision.mode
                    item["resourceReason"] = measured_decision.reason
            output.append(item)
        return output

    @staticmethod
    def _report_path(pack: InstalledPack, backend: str | None) -> Path:
        if not backend or backend == "auto":
            return pack.path / "benchmark.json"
        safe = "".join(
            character
            for character in normalize_backend(backend)
            if character.isalnum() or character in "-_"
        )
        return pack.path / f"benchmark-{safe}.json"

    @classmethod
    def _load_report(
        cls,
        pack: InstalledPack,
        backend: str | None = None,
    ) -> dict[str, Any] | None:
        paths = [cls._report_path(pack, backend)]
        generic = pack.path / "benchmark.json"
        if generic not in paths:
            paths.append(generic)
        for path in paths:
            if not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if payload.get("packId") != pack.id:
                continue
            if backend and backend != "auto":
                report_backend = normalize_backend(payload.get("backend"))
                if report_backend != normalize_backend(backend):
                    continue
            return payload
        return None

    @staticmethod
    def _store_selected_report(pack: InstalledPack, report: dict[str, Any]) -> None:
        output = pack.path / "benchmark.json"
        temporary = output.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False),
            encoding="utf-8",
        )
        temporary.replace(output)

    @staticmethod
    def _failed_benchmark_report(
        pack: InstalledPack,
        backend: str | None,
        error: BaseException,
    ) -> dict[str, Any]:
        requested = normalize_backend(backend or "cpu")
        return {
            "schemaVersion": 2,
            "packId": pack.id,
            "packVersion": pack.version,
            "requestedBackend": requested,
            "backend": "unverified",
            "passed": False,
            "failures": ["BENCHMARK_EXECUTION_ERROR"],
            "errorType": error.__class__.__name__,
        }

    def _candidate(
        self,
        pack: InstalledPack,
        definition: dict[str, Any],
        report: dict[str, Any],
        *,
        candidate_id: str | None = None,
    ) -> EngineCandidate:
        tier = str(definition.get("tier", "experimental"))
        declared_ram = self._declared_engine_ram(definition)
        measured_ram = self._engine_ram_from_report(report)
        measured_total_product = self._effective_measured_total(
            definition, report
        )
        combined_rtf = _finite_non_negative(
            report.get(
                "combinedRtfP95", report.get("asrRtfP95", 99.0)
            ),
            99.0,
        )
        end_to_end_p50 = _finite_non_negative(
            report.get(
                "endToEndP50Ms", report.get("translationP50Ms", 0.0)
            ),
            0.0,
        )
        end_to_end_p95 = _finite_non_negative(
            report.get(
                "endToEndP95Ms",
                report.get("translationP95Ms", 99999.0),
            ),
            99999.0,
        )
        supported_backends = tuple(
            normalize_backend(item)
            for item in definition.get("supportedBackends", ("cpu",))
        )
        reported_backend = normalize_backend(report.get("backend", "cpu"))
        measured_backend = (
            reported_backend
            if reported_backend in supported_backends
            else "unverified"
        )
        return EngineCandidate(
            id=candidate_id or pack.id,
            engine_id=str(definition.get("engine", "")),
            ram_mb=max(declared_ram, measured_ram),
            vram_mb=_finite_non_negative(
                definition.get("vramMb", 0), 0.0
            ),
            shared_gpu_mb=(
                0.0
                if measured_total_product > 0
                else self._shared_gpu(definition)
            ),
            total_product_mb=measured_total_product,
            quality_score=_TIER_QUALITY.get(tier, 0.65),
            benchmark=BenchmarkSample(
                rtf=combined_rtf,
                p50_ms=end_to_end_p50,
                p95_ms=end_to_end_p95,
                stable=bool(report.get("passed", False)),
            ),
            backends=(measured_backend,),
        )

    def _benchmark_backends(
        self,
        definition: dict[str, Any],
        *,
        allow_cloud: bool,
    ) -> tuple[str | None, ...]:
        if not self._benchmarker_supports_profile:
            return (None,)
        available = set(self.inventory.backends)
        output: list[str] = []
        for value in definition.get("supportedBackends", ("cpu",)):
            backend = normalize_backend(value)
            if backend == "cloud" and not allow_cloud:
                continue
            if backend in available and backend not in output:
                output.append(backend)
        return tuple(output)

    def _run_benchmark(
        self,
        pack: InstalledPack,
        definition: dict[str, Any],
        backend: str | None,
    ) -> dict[str, Any]:
        if self._benchmarker_supports_profile and backend is not None:
            return self.benchmarker(
                pack,
                definition,
                compute_profile=backend,
            )
        return self.benchmarker(pack, definition)

    def optimize(
        self,
        route: str,
        *,
        allow_cloud: bool = False,
        force_benchmark: bool = False,
    ) -> tuple[EngineSelection, dict[str, dict[str, Any]]]:
        definitions = {
            str(item["id"]): item for item in self.catalog.definitions()
        }
        candidates: list[EngineCandidate] = []
        reports: dict[str, dict[str, Any]] = {}
        candidate_packs: dict[str, InstalledPack] = {}
        candidate_reports: dict[str, dict[str, Any]] = {}
        candidate_backends: dict[str, str] = {}
        benchmark_rejected: dict[str, str] = {}

        for pack in self.catalog.installed():
            definition = definitions.get(pack.id)
            if not definition or route not in definition.get("routes", ()):
                continue
            backends = self._benchmark_backends(
                definition, allow_cloud=allow_cloud
            )
            for backend in backends:
                variant_backend = backend or "legacy"
                variant_id = f"{pack.id}@{variant_backend}"
                candidate_packs[variant_id] = pack
                report = (
                    None
                    if force_benchmark
                    else self._load_report(pack, backend)
                )
                if report is None:
                    try:
                        report = self._run_benchmark(
                            pack, definition, backend
                        )
                    except Exception as exc:
                        report = self._failed_benchmark_report(
                            pack, backend, exc
                        )
                        reports[variant_id] = report
                        benchmark_rejected[
                            variant_id
                        ] = "BENCHMARK_EXECUTION_ERROR"
                        continue
                measured_backend = normalize_backend(
                    report.get("backend", backend or "cpu")
                )
                variant_backend = backend or measured_backend
                variant_id = f"{pack.id}@{variant_backend}"
                reports[variant_id] = report
                candidate_packs[variant_id] = pack
                candidate_reports[variant_id] = report
                candidate_backends[variant_id] = variant_backend
                candidates.append(
                    self._candidate(
                        pack,
                        definition,
                        report,
                        candidate_id=variant_id,
                    )
                )

        raw_selection = self.registry.select(
            route=route,
            candidates=candidates,
            installed_runtimes=set(self.inventory.runtimes),
            available_backends=set(self.inventory.backends),
            allow_cloud=allow_cloud,
        )
        variant_id = raw_selection.candidate.id
        selected_pack = candidate_packs[variant_id]
        selected_report = candidate_reports[variant_id]
        selected_backend = candidate_backends[variant_id]
        self._store_selected_report(selected_pack, selected_report)
        reports[selected_pack.id] = selected_report

        normalized_rejected: dict[str, str] = dict(benchmark_rejected)
        for rejected_id, reason in raw_selection.rejected.items():
            pack_id = candidate_packs.get(rejected_id)
            if pack_id is not None:
                normalized_rejected.setdefault(pack_id.id, reason)
            normalized_rejected[rejected_id] = reason

        selection = EngineSelection(
            candidate=replace(raw_selection.candidate, id=selected_pack.id),
            backend=selected_backend,
            score=raw_selection.score,
            rejected=normalized_rejected,
        )
        activate_selection = getattr(self.installer, "activate_selection", None)
        if callable(activate_selection):
            activate_selection(
                selected_pack.id,
                selected_pack.version,
                selected_backend,
            )
        elif not selected_pack.active:
            self.installer.activate(selected_pack.id, selected_pack.version)
        return selection, reports
