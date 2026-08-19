"""Microbenchmark local para elegir un pack sin adivinar por marca de hardware."""

from __future__ import annotations

import ctypes
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from .benchmarking import percentile
from .cpu_budget import detect_cpu_budget
from .models import InstalledPack
from .provider_factory import build_asr_provider, build_translation_provider


class BenchmarkExecutionError(RuntimeError):
    pass


def process_working_set_mb() -> float:
    """Working set del proceso, incluyendo memoria nativa cuando el SO la expone."""

    if os.name == "nt":
        try:
            from ctypes import wintypes

            class ProcessMemoryCounters(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = ProcessMemoryCounters()
            counters.cb = ctypes.sizeof(counters)
            get_current = ctypes.windll.kernel32.GetCurrentProcess
            get_info = ctypes.windll.psapi.GetProcessMemoryInfo
            if get_info(get_current(), ctypes.byref(counters), counters.cb):
                return counters.WorkingSetSize / (1024.0 * 1024.0)
        except (AttributeError, OSError, ValueError):
            pass
    try:
        import resource

        maximum = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        # Linux devuelve KiB; macOS devuelve bytes.
        return maximum / (1024.0 if sys.platform != "darwin" else 1024.0 * 1024.0)
    except (ImportError, OSError, ValueError):
        return 0.0


def _sample_for_route(route: str) -> tuple[str, str]:
    if route == "zh-es":
        return "zh", "请确认订单一零三八，不要取消。"
    if route == "es-en":
        return "es", "Confirme el pedido 1038 y no lo cancele."
    return "en", "Please confirm order 1038 and do not cancel it."


def benchmark_installed_pack(
    pack: InstalledPack,
    definition: dict[str, Any],
    *,
    compute_profile: str = "cpu",
    repeats: int = 3,
) -> dict[str, Any]:
    if repeats < 3:
        raise ValueError("El benchmark requiere al menos tres muestras")
    components = definition.get("components", {})
    if not isinstance(components, dict) or "asr" not in components or "translation" not in components:
        raise BenchmarkExecutionError("El pack no declara ASR y traducción")

    routes = tuple(str(item) for item in definition.get("routes", ("en-es",)))
    route = routes[0] if routes else "en-es"
    source_language, sample_text = _sample_for_route(route)
    budget = detect_cpu_budget("light")
    asr = build_asr_provider(
        components["asr"],
        pack.path / "components" / "asr",
        compute_profile,
        budget,
        False,
    )
    translator = build_translation_provider(
        components["translation"],
        pack.path / "components" / "translation",
        compute_profile,
        budget,
    )
    audio_seconds = 1.0
    audio = [0.0] * 16000
    asr_ms: list[float] = []
    mt_ms: list[float] = []
    memory_before = process_working_set_mb()
    try:
        warm_asr = getattr(asr, "warm_up", None)
        if callable(warm_asr):
            try:
                warm_asr(source_language)
            except TypeError:
                warm_asr()
        warm_mt = getattr(translator, "warm_up", None)
        if callable(warm_mt):
            warm_mt()

        for _ in range(repeats):
            started = time.perf_counter()
            asr.transcribe(audio, source_language)
            asr_ms.append((time.perf_counter() - started) * 1000.0)
            started = time.perf_counter()
            translator.translate(sample_text, source_language)
            mt_ms.append((time.perf_counter() - started) * 1000.0)
    except Exception as exc:
        raise BenchmarkExecutionError(
            f"El pack {pack.id} no completó su microbenchmark: {exc.__class__.__name__}"
        ) from exc
    finally:
        for provider in (translator, asr):
            unload = getattr(provider, "unload", None)
            if callable(unload):
                unload()

    working_set = max(memory_before, process_working_set_mb())
    asr_p50 = percentile(asr_ms, 50)
    asr_p95 = percentile(asr_ms, 95)
    mt_p50 = percentile(mt_ms, 50)
    mt_p95 = percentile(mt_ms, 95)
    asr_rtf_p95 = asr_p95 / (audio_seconds * 1000.0)
    passed = (
        asr_rtf_p95 < 0.80
        and mt_p95 <= 700.0
        and working_set <= 2048.0
    )
    report = {
        "schemaVersion": 1,
        "packId": pack.id,
        "packVersion": pack.version,
        "route": route,
        "backend": compute_profile,
        "samples": repeats,
        "asrP50Ms": round(asr_p50, 3),
        "asrP95Ms": round(asr_p95, 3),
        "asrRtfP95": round(asr_rtf_p95, 4),
        "translationP50Ms": round(mt_p50, 3),
        "translationP95Ms": round(mt_p95, 3),
        "workingSetMb": round(working_set, 1),
        "passed": passed,
    }
    output = pack.path / "benchmark.json"
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(output)
    return report
