"""Asesor que benchmarkea packs instalados y activa el ganador seguro."""

from __future__ import annotations

import json
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
from .resource_governor import (
    ResourceGovernor,
    ResourceLimits,
    RuntimeFootprint,
)
from .runtime_discovery import RuntimeInventory, discover_runtime_inventory

BenchmarkFunction = Callable[[InstalledPack, dict[str, Any]], dict[str, Any]]

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

    def _declared_decision(self, definition: dict[str, Any]):
        return self.governor.preflight_model(
            model_ram_mb=self._declared_engine_ram(definition),
            shared_gpu_mb=_finite_non_negative(
                definition.get("sharedGpuMb", 0), 0.0
            ),
            total_product_mb=measured_total_product,
            dedicated_vram_mb=_finite_non_negative(
                definition.get("vramMb", 0), 0.0
            ),
        )

    def _measured_decision(
        self,
        definition: dict[str, Any],
        report: dict[str, Any],
    ):
        total_product = _finite_non_negative(
            report.get("totalProductWorkingSetMb", 0.0), 0.0
        )
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
            shared_gpu_mb=_finite_non_negative(
                definition.get("sharedGpuMb", 0), 0.0
            ),
            dedicated_vram_mb=dedicated_vram,
        )

    def describe_catalog(self) -> list[dict[str, Any]]:
        installed = {
            f"{item.id}@{item.version}": item
            for item in self.catalog.installed()
        }
        output: list[dict[str, Any]] = []
        for definition in self.catalog.definitions():
            ref = f"{definition['id']}@{definition['version']}"
            decision = self._declared_decision(definition)
            item = dict(definition)
            current = installed.get(ref)
            item["installed"] = current is not None
            item["active"] = bool(current and current.active)
            item["resourceAllowed"] = decision.allowed
            item["resourceMode"] = decision.mode
            item["resourceReason"] = decision.reason
            item["estimatedTotalProductMb"] = round(
                decision.effective_process_mb, 1
            )
            item["productReserveMb"] = self.governor.limits.product_reserve_mb
            if current is not None:
                report = self._load_report(current)
                item["benchmark"] = report
                if report is not None:
                    measured_engine = self._engine_ram_from_report(report)
                    measured_total = _finite_non_negative(
                        report.get("totalProductWorkingSetMb", 0.0), 0.0
                    )
                    measured_decision = self._measured_decision(
                        definition, report
                    )
                    if measured_total <= 0:
                        measured_total = measured_decision.effective_process_mb
                    item["measuredEngineRamMb"] = measured_engine
                    item["measuredTotalProductMb"] = measured_total
                    # Compatibilidad de UI: measuredRamMb ahora representa el
                    # producto completo, no únicamente el Python padre.
                    item["measuredRamMb"] = measured_total
                    item["resourceAllowed"] = measured_decision.allowed
                    item["resourceMode"] = measured_decision.mode
                    item["resourceReason"] = measured_decision.reason
            output.append(item)
        return output

    @staticmethod
    def _load_report(pack: InstalledPack) -> dict[str, Any] | None:
        path = pack.path / "benchmark.json"
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if payload.get("packId") == pack.id else None

    def _candidate(
        self,
        pack: InstalledPack,
        definition: dict[str, Any],
        report: dict[str, Any],
    ) -> EngineCandidate:
        tier = str(definition.get("tier", "experimental"))
        declared_ram = self._declared_engine_ram(definition)
        measured_ram = self._engine_ram_from_report(report)
        measured_total_product = _finite_non_negative(
            report.get("totalProductWorkingSetMb", 0.0), 0.0
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
        return EngineCandidate(
            id=pack.id,
            engine_id=str(definition.get("engine", "")),
            ram_mb=max(declared_ram, measured_ram),
            vram_mb=_finite_non_negative(
                definition.get("vramMb", 0), 0.0
            ),
            shared_gpu_mb=_finite_non_negative(
                definition.get("sharedGpuMb", 0), 0.0
            ),
            total_product_mb=measured_total_product,
            quality_score=_TIER_QUALITY.get(tier, 0.65),
            benchmark=BenchmarkSample(
                rtf=combined_rtf,
                p50_ms=end_to_end_p50,
                p95_ms=end_to_end_p95,
                stable=bool(report.get("passed", False)),
            ),
            backends=tuple(
                str(item)
                for item in definition.get(
                    "supportedBackends", ("cpu",)
                )
            ),
        )

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
        for pack in self.catalog.installed():
            definition = definitions.get(pack.id)
            if not definition or route not in definition.get("routes", ()):
                continue
            report = None if force_benchmark else self._load_report(pack)
            if report is None:
                report = self.benchmarker(pack, definition)
            reports[pack.id] = report
            candidates.append(self._candidate(pack, definition, report))
        selection = self.registry.select(
            route=route,
            candidates=candidates,
            installed_runtimes=set(self.inventory.runtimes),
            available_backends=set(self.inventory.backends),
            allow_cloud=allow_cloud,
        )
        selected_pack = next(
            item
            for item in self.catalog.installed()
            if item.id == selection.candidate.id
        )
        if not selected_pack.active:
            self.installer.activate(selected_pack.id, selected_pack.version)
        return selection, reports
