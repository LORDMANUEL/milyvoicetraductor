"""Benchmark Tier 1 que reutiliza el medidor estable con audio por idioma."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Sequence

from . import engine_benchmark as base_benchmark
from .models import InstalledPack


_ROUTE_SAMPLES = {
    "en-es": ("en", "Please confirm order 1038 and do not cancel it."),
    "zh-es": ("zh", "请确认订单一零三八，不要取消。"),
    "es-en": ("es", "Confirme el pedido 1038 y no lo cancele."),
    "es-zh": ("es", "Confirme el pedido 1038 y no lo cancele."),
}


def _sample_for_route(route: str) -> tuple[str, str]:
    return _ROUTE_SAMPLES.get(str(route).strip().lower(), _ROUTE_SAMPLES["en-es"])


def _windows_sapi_fixture(source_language: str) -> list[float]:
    if os.name != "nt":
        raise base_benchmark.BenchmarkExecutionError(
            "El benchmark ASR requiere audio real o Windows SAPI"
        )
    language = source_language if source_language in {"es", "en", "zh"} else "en"
    text = {
        "en": "Good morning. Please confirm order one zero three eight and do not cancel it. The meeting starts at nine.",
        "es": "Buenos días. Confirme el pedido uno cero tres ocho y no lo cancele. La reunión empieza a las nueve.",
        "zh": "早上好。请确认订单一零三八，不要取消。会议九点开始。",
    }[language]
    prefix = {"en": "en", "es": "es", "zh": "zh"}[language]

    with tempfile.TemporaryDirectory(prefix="mily-tier1-benchmark-") as temp:
        root = Path(temp)
        wave_path = root / f"benchmark-{language}.wav"
        script_path = root / "generate-fixture.ps1"
        script_path.write_text(
            "param([Parameter(Mandatory=$true)][string]$OutputPath,"
            "[Parameter(Mandatory=$true)][string]$Text,"
            "[Parameter(Mandatory=$true)][string]$CulturePrefix)\n"
            "$ErrorActionPreference='Stop'\n"
            "Add-Type -AssemblyName System.Speech\n"
            "$s=[System.Speech.Synthesis.SpeechSynthesizer]::new()\n"
            "try {\n"
            "  $v=$s.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like ($CulturePrefix + '-*') } | Select-Object -First 1\n"
            "  if (-not $v) { $v=$s.GetInstalledVoices() | Where-Object { $_.Enabled } | Select-Object -First 1 }\n"
            "  if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }\n"
            "  $s.Rate=0\n"
            "  $s.SetOutputToWaveFile($OutputPath)\n"
            "  $s.Speak($Text)\n"
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
                    "-Text",
                    text,
                    "-CulturePrefix",
                    prefix,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=45,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise base_benchmark.BenchmarkExecutionError(
                f"Windows SAPI no pudo generar audio Tier 1 para {language}"
            ) from exc
        if not wave_path.is_file():
            raise base_benchmark.BenchmarkExecutionError(
                "Windows SAPI no produjo el WAV Tier 1 esperado"
            )
        return base_benchmark._read_wave_mono_16k(wave_path)


def benchmark_installed_pack(
    pack: InstalledPack,
    definition: dict[str, Any],
    *,
    compute_profile: str = "cpu",
    repeats: int = 3,
    audio_samples: Sequence[float] | None = None,
) -> dict[str, Any]:
    routes = tuple(str(item) for item in definition.get("routes", ("en-es",)))
    route = routes[0] if routes else "en-es"
    source_language, _fallback = _sample_for_route(route)
    audio = (
        [float(value) for value in audio_samples]
        if audio_samples is not None
        else _windows_sapi_fixture(source_language)
    )

    # El benchmark estable usa una función global para resolver la muestra de
    # ruta. La sustituimos sólo durante esta llamada secuencial y la restauramos
    # siempre; toda la medición, límites de memoria y backend siguen siendo los
    # mismos que en el gate histórico.
    original_sample_for_route = base_benchmark._sample_for_route
    base_benchmark._sample_for_route = _sample_for_route
    try:
        return base_benchmark.benchmark_installed_pack(
            pack,
            definition,
            compute_profile=compute_profile,
            repeats=repeats,
            audio_samples=audio,
        )
    finally:
        base_benchmark._sample_for_route = original_sample_for_route
