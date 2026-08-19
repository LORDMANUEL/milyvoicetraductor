"""Microbenchmark local para elegir un pack sin adivinar por marca de hardware."""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path
from typing import Any, Sequence

from .benchmarking import percentile
from .cpu_budget import detect_cpu_budget
from .models import InstalledPack
from .provider_factory import build_asr_provider, build_translation_provider


class BenchmarkExecutionError(RuntimeError):
    pass


def process_memory_snapshot_mb() -> tuple[float, float]:
    """Devuelve working set actual y pico del proceso en MiB."""

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
                divisor = 1024.0 * 1024.0
                return (
                    counters.WorkingSetSize / divisor,
                    counters.PeakWorkingSetSize / divisor,
                )
        except (AttributeError, OSError, ValueError):
            pass

    status = Path("/proc/self/status")
    if status.is_file():
        try:
            values: dict[str, float] = {}
            for line in status.read_text(encoding="utf-8").splitlines():
                if line.startswith(("VmRSS:", "VmHWM:")):
                    name, raw = line.split(":", 1)
                    values[name] = float(raw.strip().split()[0]) / 1024.0
            current = values.get("VmRSS", 0.0)
            peak = max(current, values.get("VmHWM", current))
            return current, peak
        except (OSError, ValueError, IndexError):
            pass

    try:
        import resource

        maximum = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        peak = maximum / (
            1024.0 * 1024.0 if sys.platform == "darwin" else 1024.0
        )
        return peak, peak
    except (ImportError, OSError, ValueError):
        return 0.0, 0.0


def process_working_set_mb() -> float:
    """Compatibilidad con consumidores 2.0.1: working set actual."""

    return process_memory_snapshot_mb()[0]


def _sample_for_route(route: str) -> tuple[str, str]:
    if route == "zh-es":
        return "zh", "请确认订单一零三八，不要取消。"
    if route == "es-en":
        return "es", "Confirme el pedido 1038 y no lo cancele."
    return "en", "Please confirm order 1038 and do not cancel it."


def _read_wave_mono_16k(path: Path) -> list[float]:
    try:
        import numpy as np
    except ImportError as exc:
        raise BenchmarkExecutionError("NumPy no está disponible para MegaBench") from exc
    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        width = source.getsampwidth()
        rate = source.getframerate()
        raw = source.readframes(source.getnframes())
    if width == 1:
        samples = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif width == 2:
        samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif width == 4:
        samples = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise BenchmarkExecutionError("El WAV de benchmark usa un ancho no soportado")
    if channels > 1:
        usable = samples[: samples.size - (samples.size % channels)]
        samples = usable.reshape(-1, channels).mean(axis=1)
    if rate != 16000:
        target_length = max(1, round(samples.size * 16000 / rate))
        source_positions = np.linspace(0.0, 1.0, num=samples.size, endpoint=False)
        target_positions = np.linspace(0.0, 1.0, num=target_length, endpoint=False)
        samples = np.interp(target_positions, source_positions, samples).astype(
            np.float32
        )
    return [float(value) for value in samples]


def _windows_sapi_fixture() -> list[float]:
    if os.name != "nt":
        raise BenchmarkExecutionError(
            "El benchmark ASR requiere audio real o Windows SAPI"
        )
    with tempfile.TemporaryDirectory(prefix="mily-benchmark-") as temp:
        root = Path(temp)
        wave_path = root / "benchmark-en.wav"
        script_path = root / "generate-fixture.ps1"
        script_path.write_text(
            "param([Parameter(Mandatory=$true)][string]$OutputPath)\n"
            "$ErrorActionPreference='Stop'\n"
            "Add-Type -AssemblyName System.Speech\n"
            "$s=[System.Speech.Synthesis.SpeechSynthesizer]::new()\n"
            "try {\n"
            "  $v=$s.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'en-*' } | Select-Object -First 1\n"
            "  if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }\n"
            "  $s.Rate=0\n"
            "  $s.SetOutputToWaveFile($OutputPath)\n"
            "  $s.Speak('Good morning. Please confirm order one zero three eight and do not cancel it. The meeting starts at nine.')\n"
            "} finally { $s.Dispose() }\n",
            encoding="utf-8",
        )
        try:
            subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script_path),
                    "-OutputPath",
                    str(wave_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=45,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise BenchmarkExecutionError(
                "Windows SAPI no pudo generar el audio local de benchmark"
            ) from exc
        if not wave_path.is_file():
            raise BenchmarkExecutionError("Windows SAPI no produjo el WAV esperado")
        return _read_wave_mono_16k(wave_path)


def benchmark_installed_pack(
    pack: InstalledPack,
    definition: dict[str, Any],
    *,
    compute_profile: str = "cpu",
    repeats: int = 3,
    audio_samples: Sequence[float] | None = None,
) -> dict[str, Any]:
    if repeats < 3:
        raise ValueError("El benchmark requiere al menos tres muestras")
    components = definition.get("components", {})
    if (
        not isinstance(components, dict)
        or "asr" not in components
        or "translation" not in components
    ):
        raise BenchmarkExecutionError("El pack no declara ASR y traducción")

    routes = tuple(str(item) for item in definition.get("routes", ("en-es",)))
    route = routes[0] if routes else "en-es"
    source_language, fallback_text = _sample_for_route(route)
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
    audio = (
        [float(value) for value in audio_samples]
        if audio_samples is not None
        else _windows_sapi_fixture()
    )
    if len(audio) < 1600:
        raise BenchmarkExecutionError("El audio de benchmark es demasiado corto")
    audio_seconds = len(audio) / 16000.0
    asr_ms: list[float] = []
    mt_ms: list[float] = []
    e2e_ms: list[float] = []
    empty_asr = 0
    empty_translation = 0
    current, peak = process_memory_snapshot_mb()
    peak_working_set = max(current, peak)
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
        current, measured_peak = process_memory_snapshot_mb()
        peak_working_set = max(peak_working_set, current, measured_peak)

        for _ in range(repeats):
            started = time.perf_counter()
            segments = asr.transcribe(audio, source_language)
            asr_elapsed = (time.perf_counter() - started) * 1000.0
            original = " ".join(
                str(segment.text).strip()
                for segment in segments
                if str(getattr(segment, "text", "")).strip()
            ).strip()
            if not original:
                empty_asr += 1
            current, measured_peak = process_memory_snapshot_mb()
            peak_working_set = max(peak_working_set, current, measured_peak)

            started = time.perf_counter()
            translated = translator.translate(original or fallback_text, source_language)
            mt_elapsed = (time.perf_counter() - started) * 1000.0
            if not str(translated).strip():
                empty_translation += 1
            current, measured_peak = process_memory_snapshot_mb()
            peak_working_set = max(peak_working_set, current, measured_peak)

            asr_ms.append(asr_elapsed)
            mt_ms.append(mt_elapsed)
            e2e_ms.append(asr_elapsed + mt_elapsed)
    except Exception as exc:
        raise BenchmarkExecutionError(
            f"El pack {pack.id} no completó su microbenchmark: {exc.__class__.__name__}"
        ) from exc
    finally:
        for provider in (translator, asr):
            unload = getattr(provider, "unload", None)
            if callable(unload):
                unload()

    asr_p50 = percentile(asr_ms, 50)
    asr_p95 = percentile(asr_ms, 95)
    mt_p50 = percentile(mt_ms, 50)
    mt_p95 = percentile(mt_ms, 95)
    e2e_p50 = percentile(e2e_ms, 50)
    e2e_p95 = percentile(e2e_ms, 95)
    asr_rtf_p95 = asr_p95 / (audio_seconds * 1000.0)
    combined_rtf_p95 = e2e_p95 / (audio_seconds * 1000.0)

    failures: list[str] = []
    if empty_asr:
        failures.append("EMPTY_ASR")
    if empty_translation:
        failures.append("EMPTY_TRANSLATION")
    if asr_rtf_p95 >= 0.80:
        failures.append("ASR_RTF")
    if e2e_p95 > 1500.0:
        failures.append("E2E_LATENCY")
    if peak_working_set > 2048.0:
        failures.append("RAM_HARD_LIMIT")
    if float(definition.get("ramMb", 0.0) or 0.0) > 2048.0:
        failures.append("DECLARED_RAM_LIMIT")

    report = {
        "schemaVersion": 2,
        "packId": pack.id,
        "packVersion": pack.version,
        "route": route,
        "backend": compute_profile,
        "samples": repeats,
        "audioSeconds": round(audio_seconds, 3),
        "asrP50Ms": round(asr_p50, 3),
        "asrP95Ms": round(asr_p95, 3),
        "asrRtfP95": round(asr_rtf_p95, 4),
        "translationP50Ms": round(mt_p50, 3),
        "translationP95Ms": round(mt_p95, 3),
        "endToEndP50Ms": round(e2e_p50, 3),
        "endToEndP95Ms": round(e2e_p95, 3),
        "combinedRtfP95": round(combined_rtf_p95, 4),
        "workingSetMb": round(peak_working_set, 1),
        "peakWorkingSetMb": round(peak_working_set, 1),
        "emptyAsrResults": empty_asr,
        "emptyTranslationResults": empty_translation,
        "failures": failures,
        "passed": not failures,
    }
    output = pack.path / "benchmark.json"
    temporary = output.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    temporary.replace(output)
    return report
