[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$PerformanceRoot = Join-Path $Root 'dist\performance'
$ReportPath = Join-Path $PerformanceRoot 'MilyVoiceTraductor-2.0.1-QualityPolicy.json'
$Probe = Join-Path $env:RUNNER_TEMP 'milyvoice-quality-policy.py'

New-Item -ItemType Directory -Force -Path $PerformanceRoot | Out-Null
Remove-Item $ReportPath,$Probe -Force -ErrorAction SilentlyContinue

@'
from __future__ import annotations

import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
report_path = Path(sys.argv[2])
sys.path.insert(0, str(root / "services" / "ai"))

from mily_ai.models import ModelCatalog
from mily_ai.resource_governor import ResourceGovernor, ResourceLimits

catalog = ModelCatalog(root / ".build" / "quality-policy-models")
definitions = {item["id"]: item for item in catalog.definitions()}
quality = definitions["realtime-m2m100"]
moonshine = definitions["fast-moonshine-en-es"]
whisper_tiny = definitions["lite-en-es"]

governor = ResourceGovernor(ResourceLimits())


def decide(definition: dict):
    return governor.preflight_model(
        model_ram_mb=float(definition.get("ramMb", 0)),
        shared_gpu_mb=float(definition.get("sharedGpuMb", 0)),
        dedicated_vram_mb=float(definition.get("vramMb", 0)),
    )


quality_decision = decide(quality)
moonshine_decision = decide(moonshine)
whisper_tiny_decision = decide(whisper_tiny)

if quality_decision.allowed:
    raise SystemExit("QUALITY_PACK_MUST_NOT_FIT_2_GIB")
if quality_decision.reason != "PROCESS_MEMORY_LIMIT":
    raise SystemExit(
        "QUALITY_PACK_WRONG_REJECTION:" + quality_decision.reason
    )
if not moonshine_decision.allowed:
    raise SystemExit("MOONSHINE_LITE_REJECTED:" + moonshine_decision.reason)
if not whisper_tiny_decision.allowed:
    raise SystemExit("WHISPER_TINY_LITE_REJECTED:" + whisper_tiny_decision.reason)

host = {
    "totalMb": 8192,
    "windowsMb": 4096,
    "milyVoiceBudgetMb": 2048,
    "chromeMb": 1024,
    "freeMb": 1024,
}
if sum(host[key] for key in ("windowsMb", "milyVoiceBudgetMb", "chromeMb", "freeMb")) != host["totalMb"]:
    raise SystemExit("HOST_BUDGET_INVALID")

report = {
    "schemaVersion": 1,
    "productVersion": "2.0.1-enginehub-pruebas",
    "policy": "2-gib-hard-product-envelope",
    "hostSimulation": host,
    "gpuClass": {
        "physicalVramMb": 512,
        "milyVoiceBudgetMb": governor.limits.vram_budget_mb,
        "systemBrowserReserveMb": 512 - governor.limits.vram_budget_mb,
    },
    "requiredLiteProfiles": {
        moonshine["id"]: {
            "allowed": moonshine_decision.allowed,
            "estimatedTotalProductMb": moonshine_decision.effective_process_mb,
            "headroomMb": moonshine_decision.process_headroom_mb,
        },
        whisper_tiny["id"]: {
            "allowed": whisper_tiny_decision.allowed,
            "estimatedTotalProductMb": whisper_tiny_decision.effective_process_mb,
            "headroomMb": whisper_tiny_decision.process_headroom_mb,
        },
    },
    "optionalQualityProfiles": {
        quality["id"]: {
            "allowed": quality_decision.allowed,
            "reason": quality_decision.reason,
            "estimatedTotalProductMb": quality_decision.effective_process_mb,
            "processHeadroomMb": quality_decision.process_headroom_mb,
            "dedicatedVramMb": quality_decision.dedicated_vram_mb,
        }
    },
    "passed": True,
    "notes": [
        "El perfil Quality permanece en catálogo, pero no puede ser el baseline de un producto limitado a 2 GiB.",
        "Los pesos Quality no se descargan durante este gate; el rechazo ocurre antes de reservar memoria o red.",
        "Moonshine Lite y Whisper Tiny Lite continúan como candidatos locales medibles.",
    ],
}
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print("ENGINEHUB_HOST_8_4_2_1_1_OK")
print("ENGINEHUB_VRAM_512_384_OK")
print("QUALITY_PACK_REJECTED", quality_decision.reason)
print("QUALITY_POLICY_REPORT", report_path)
'@ | Set-Content -Path $Probe -Encoding UTF8

try {
    python $Probe $Root $ReportPath
    if ($LASTEXITCODE -ne 0) {
        throw 'La política de modelos no respetó el límite completo de 2 GiB.'
    }
    if (-not (Test-Path $ReportPath -PathType Leaf)) {
        throw 'La política de modelos no produjo reporte JSON.'
    }
    $report = Get-Content $ReportPath -Raw | ConvertFrom-Json
    if (-not $report.passed) { throw 'El reporte de política no quedó aprobado.' }
    if ($report.optionalQualityProfiles.'realtime-m2m100'.reason -ne 'PROCESS_MEMORY_LIMIT') {
        throw 'El perfil Quality no fue rechazado por PROCESS_MEMORY_LIMIT.'
    }
    Write-Host "ENGINE HUB QUALITY POLICY OK: $ReportPath" -ForegroundColor Green
}
finally {
    Remove-Item $Probe -Force -ErrorAction SilentlyContinue
}
