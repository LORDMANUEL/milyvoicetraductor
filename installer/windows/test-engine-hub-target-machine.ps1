[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$env:PYTHONPATH = Join-Path $Root 'services\ai'
$PerformanceRoot = Join-Path $Root 'dist\performance'
$ReportPath = Join-Path $PerformanceRoot 'MilyVoiceTraductor-2.0.1-TargetMachineSimulation.json'
New-Item -ItemType Directory -Force $PerformanceRoot | Out-Null
Remove-Item $ReportPath -Force -ErrorAction SilentlyContinue

python (Join-Path $Root 'services\ai\tests\test_engine_hub_target_machine.py')
if ($LASTEXITCODE -ne 0) { throw 'Falló la simulación de máquina objetivo.' }

@'
from pathlib import Path
import json
import sys

out = Path(sys.argv[1])
report = {
    'schemaVersion': 1,
    'productVersion': '2.0.1',
    'scenario': {
        'hostRamMb': 8192,
        'windowsMb': 4096,
        'milyVoiceBudgetMb': 2048,
        'chromeMb': 1024,
        'freeMb': 1024,
        'physicalCores': 2,
        'logicalThreads': 4,
        'gpuClassMb': 512,
        'milyVoiceVramBudgetMb': 384,
    },
    'gates': {
        'completeProductMaxMb': 2048,
        'liteStableMb': 1200,
        'litePeakMb': 1536,
        'rescueMb': 700,
        'queueStartAgeMaxMs': 700,
        'endToEndMaxMs': 1500,
        'combinedRtfP95Max': 0.80,
        'continuousMinutes': 10,
        'finalsLost': 0,
        'queueGrowth': 0,
    },
    'passed': True,
    'notes': [
        'La simulación ejecuta el contrato de 8 GiB: Windows 4 GiB + MilyVoice 2 GiB + Chrome 1 GiB + 1 GiB libre.',
        'La memoria compartida de iGPU cuenta contra el presupuesto de MilyVoice.',
        'El perfil de 512 MiB VRAM reserva 128 MiB y limita MilyVoice a 384 MiB.',
        'El test de cola genera 500 frases durante 10 minutos y exige cero finales perdidos.'
    ],
}
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('TARGET_MACHINE_SIMULATION_OK', out)
'@ | python - $ReportPath

if ($LASTEXITCODE -ne 0) { throw 'No se pudo generar el reporte de simulación.' }
if (-not (Test-Path $ReportPath -PathType Leaf)) { throw 'No se generó el reporte de simulación.' }
Write-Host "ENGINE HUB TARGET MACHINE OK: $ReportPath" -ForegroundColor Green
