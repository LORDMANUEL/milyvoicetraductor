"""Microbenchmark local para elegir un pack sin adivinar por marca de hardware."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from typing import Any, Sequence

from .benchmarking import percentile
from .cpu_budget import detect_cpu_budget
from .models import InstalledPack
from .process_memory import process_tree_memory_snapshot_mb
from .provider_factory import (
    build_asr_provider,
    build_translation_provider,
    normalize_backend,
)
from .resource_governor import (
    ResourceGovernor,
    ResourceLimits,
    RuntimeFootprint,
)


class BenchmarkExecutionError(RuntimeError):
    pass


def process_memory_snapshot_mb() -> tuple[float, float]:
    """Working set actual/pico del motor y todos sus sidecars descendientes."""

    snapshot = process_tree_memory_snapshot_mb()
    return snapshot.current_mb, snapshot.peak_mb


def process_working_set_mb() -> float:
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
        raise BenchmarkExecutionError(
            "NumPy no está disponible para MegaBench"
        ) from exc
    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        width = source.getsampwidth()
        rate = source.getframerate()
        raw = source.readframes(source.getnframes())
    if width == 1:
        samples = (
            np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0
        ) / 128.0
    elif width == 2:
        samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif width == 4:
        samples = (
            np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
        )
    else:
        raise BenchmarkExecutionError(
            "El WAV de benchmark usa un ancho no soportado"
        )
    if channels > 1:
        usable = samples[: samples.size - (samples.size % channels)]
        samples = usable.reshape(-1, channels).mean(axis=1)
    if rate != 16000:
        target_length = max(1, round(samples.size * 16000 / rate))
        source_positions = np.linspace(
            0.0, 1.0, num=samples.size, endpoint=False
        )
        target_positions = np.linspace(
            0.0, 1.0, num=target_length, endpoint=False
        )
        samples = np.interp(
            target_positions, source_positions, samples
        ).astype(np.float32)
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
            raise BenchmarkExecutionError(
                "Windows SAPI no produjo el WAV esperado"
            )
        return _read_wave_mono_16k(wave_path)


def _provider_device(provider: Any, default: str) -> str:
    value = str(getattr(provider, "selected_device", "") or "").strip().lower()
    if value == "gpu":
        value = "cuda"
    allowed = {
        "cpu",
        "cuda",
        "vulkan",
        "openvino",
        "directml",
        "windowsml",
        "cloud",
    }
    return value if value in allowed else default


def _backend_verified(requested: str, asr_backend: str, mt_backend: str) -> bool:
    if requested == "auto":
        return True
    if requested == "cpu":
        return asr_backend == "cpu" and mt_backend == "cpu"
    if requested == "cloud":
        return asr_backend == "cloud"
    if requested == "cuda":
        return "cuda" in {asr_backend, mt_backend}
    if requested in {"vulkan", "openvino", "directml", "windowsml"}:
        return asr_backend == requested
    return False


def _benchmark_output_path(pack: InstalledPack, backend: str) -> Path:
    safe = "".join(character for character in backend if character.isalnum() or character in "-_")
    return pack.path / f"benchmark-{safe or 'auto'}.json"


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

    requested_backend = normalize_backend(compute_profile)
    routes = tuple(str(item) for item in definition.get("routes", ("en-es",)))
    route = routes[0] if routes else "en-es"
    source_language, fallback_text = _sample_for_route(route)
    budget = detect_cpu_budget("light")
    asr = build_asr_provider(
        components["asr"],
        pack.path / "components" / "asr",
        requested_backend,
        budget,
        False,
    )
    translator = build_translation_provider(
        components["translation"],
        pack.path / "components" / "translation",
        requested_backend,
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
    peak_engine_working_set = max(current, peak)
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
        peak_engine_working_set = max(
            peak_engine_working_set, current, measured_peak
        )

        for _ in range(repeats):
            started = time.perf_counter()
            segments = asr.transcribe(audio, source_language)
            asr_elapsed = (time.perf_counter() - started) * 1000.0
            original = " ".join(
                str(segment.text).strip()
                for segment in segments
                if str(getattr(segment, "text", "")).strip()
            ).strip()
            finish_utterance = getattr(asr, "finish_utterance", None)
            if callable(finish_utterance):
                finish_utterance()
            if not original:
                empty_asr += 1
            current, measured_peak = process_memory_snapshot_mb()
            peak_engine_working_set = max(
                peak_engine_working_set, current, measured_peak
            )

            started = time.perf_counter()
            translated = translator.translate(
                original or fallback_text, source_language
            )
            mt_elapsed = (time.perf_counter() - started) * 1000.0
            if not str(translated).strip():
                empty_translation += 1
            current, measured_peak = process_memory_snapshot_mb()
            peak_engine_working_set = max(
                peak_engine_working_set, current, measured_peak
            )

            asr_ms.append(asr_elapsed)
            mt_ms.append(mt_elapsed)
            e2e_ms.append(asr_elapsed + mt_elapsed)
    except Exception as exc:
        raise BenchmarkExecutionError(
            f"El pack {pack.id} no completó su microbenchmark: "
            f"{exc.__class__.__name__}"
        ) from exc
    finally:
        for provider in (translator, asr):
            unload = getattr(provider, "unload", None)
            if callable(unload):
                unload()

    default_asr = "cloud" if requested_backend == "cloud" else "cpu"
    default_mt = "cuda" if requested_backend == "cuda" else "cpu"
    asr_backend = _provider_device(asr, default_asr)
    translation_backend = _provider_device(translator, default_mt)
    verified = _backend_verified(
        requested_backend, asr_backend, translation_backend
    )
    verified_backend = requested_backend if verified else "unverified"

    asr_p50 = percentile(asr_ms, 50)
    asr_p95 = percentile(asr_ms, 95)
    mt_p50 = percentile(mt_ms, 50)
    mt_p95 = percentile(mt_ms, 95)
    e2e_p50 = percentile(e2e_ms, 50)
    e2e_p95 = percentile(e2e_ms, 95)
    asr_rtf_p95 = asr_p95 / (audio_seconds * 1000.0)
    combined_rtf_p95 = e2e_p95 / (audio_seconds * 1000.0)

    limits = ResourceLimits()
    governor = ResourceGovernor(limits)
    shared_gpu_mb = float(definition.get("sharedGpuMb", 0.0) or 0.0)
    dedicated_vram_mb = float(definition.get("vramMb", 0.0) or 0.0)
    product_footprint = RuntimeFootprint(
        process_mb=peak_engine_working_set,
        desktop_mb=limits.desktop_reserve_mb,
        bridge_mb=limits.bridge_reserve_mb,
        shared_gpu_mb=shared_gpu_mb,
        dedicated_vram_mb=dedicated_vram_mb,
    )
    product_decision = governor.evaluate(product_footprint)
    declared_decision = governor.preflight_model(
        model_ram_mb=float(definition.get("ramMb", 0.0) or 0.0),
        shared_gpu_mb=shared_gpu_mb,
        dedicated_vram_mb=dedicated_vram_mb,
    )
    total_product_working_set = product_decision.effective_process_mb

    failures: list[str] = []
    if not verified:
        failures.append("BACKEND_MISMATCH")
    if empty_asr:
        failures.append("EMPTY_ASR")
    if empty_translation:
        failures.append("EMPTY_TRANSLATION")
    if asr_rtf_p95 >= 0.80:
        failures.append("ASR_RTF")
    if e2e_p95 > 1500.0:
        failures.append("E2E_LATENCY")
    if not product_decision.allowed:
        failures.append(
            "VRAM_HARD_LIMIT"
            if product_decision.reason == "VRAM_LIMIT"
            else "RAM_HARD_LIMIT"
        )
    if (
        str(definition.get("tier", "")).lower() == "lite"
        and total_product_working_set > limits.lite_peak_mb
    ):
        failures.append("LITE_PEAK_LIMIT")
    if not declared_decision.allowed:
        failures.append(
            "DECLARED_VRAM_LIMIT"
            if declared_decision.reason == "VRAM_LIMIT"
            else "DECLARED_RAM_LIMIT"
        )

    report = {
        "schemaVersion": 2,
        "packId": pack.id,
        "packVersion": pack.version,
        "route": route,
        "requestedBackend": requested_backend,
        "backend": verified_backend,
        "asrBackend": asr_backend,
        "translationBackend": translation_backend,
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
        "workingSetMb": round(peak_engine_working_set, 1),
        "peakWorkingSetMb": round(peak_engine_working_set, 1),
        "engineWorkingSetMb": round(peak_engine_working_set, 1),
        "enginePeakWorkingSetMb": round(peak_engine_working_set, 1),
        "productReserveMb": round(float(limits.product_reserve_mb), 1),
        "sharedGpuMb": round(shared_gpu_mb, 1),
        "dedicatedVramMb": round(dedicated_vram_mb, 1),
        "totalProductWorkingSetMb": round(total_product_working_set, 1),
        "productMemoryMode": product_decision.mode,
        "productMemoryHeadroomMb": round(product_decision.process_headroom_mb, 1),
        "emptyAsrResults": empty_asr,
        "emptyTranslationResults": empty_translation,
        "failures": list(dict.fromkeys(failures)),
        "passed": not failures,
    }
    outputs = (
        _benchmark_output_path(pack, requested_backend),
        pack.path / "benchmark.json",
    )
    for output in outputs:
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False),
            encoding="utf-8",
        )
        temporary.replace(output)
    return report
