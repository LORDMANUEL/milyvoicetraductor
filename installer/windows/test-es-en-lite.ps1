[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$env:HF_HUB_DISABLE_TELEMETRY = '1'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$FixtureRoot = Join-Path $Root '.build\es-en-lite-smoke'
$AppRoot = Join-Path $FixtureRoot 'MilyVoiceTraductor'
$RuntimeRoot = Join-Path $AppRoot 'runtime\python'
$EngineApp = Join-Path $AppRoot 'engine\app'
$ConfigRoot = Join-Path $AppRoot 'config'
$CacheRoot = Join-Path $AppRoot 'cache'
$ModelsRoot = Join-Path $AppRoot 'models'
$RuntimeZip = Join-Path $Root 'dist\runtime\milyvoice-python-runtime.zip'
$ReportPath = Join-Path $Root 'dist\performance\MilyVoiceTraductor-2.1.0-EsEnLiteBench.json'

Remove-Item $FixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $RuntimeRoot,$EngineApp,$ConfigRoot,$CacheRoot,$ModelsRoot,(Split-Path $ReportPath) | Out-Null
Remove-Item $ReportPath -Force -ErrorAction SilentlyContinue

try {
    Expand-Archive -Path $RuntimeZip -DestinationPath $RuntimeRoot -Force
    Copy-Item (Join-Path $Root 'services\ai\*') $EngineApp -Recurse -Force

    $Python = Join-Path $RuntimeRoot 'python.exe'
    $EngineMain = Join-Path $EngineApp 'main.py'
    if (-not (Test-Path $Python -PathType Leaf)) { throw 'El runtime privado no contiene python.exe.' }

    Write-Host '[ES-EN-LITE] Descargando Whisper Tiny + Marian ES→EN sin activarlo...'
    & $Python $EngineMain models `
        --data-dir $AppRoot `
        --config-dir $ConfigRoot `
        --cache-dir $CacheRoot `
        --models-dir $ModelsRoot `
        install lite-es-en --download-only | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar lite-es-en.' }

    & $Python $EngineMain models `
        --data-dir $AppRoot `
        --config-dir $ConfigRoot `
        --cache-dir $CacheRoot `
        --models-dir $ModelsRoot `
        verify lite-es-en 1.0.0 | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'El pack ES→EN Lite no pasó verify.' }

    & $Python $EngineMain models `
        --data-dir $AppRoot `
        --config-dir $ConfigRoot `
        --cache-dir $CacheRoot `
        --models-dir $ModelsRoot `
        activate lite-es-en 1.0.0 | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo activar lite-es-en.' }

    $Probe = Join-Path $FixtureRoot 'benchmark_es_en.py'
    @'
from pathlib import Path
import json
import sys

engine_app = Path(sys.argv[1])
models_root = Path(sys.argv[2])
report_path = Path(sys.argv[3])
sys.path.insert(0, str(engine_app))

from mily_ai import tier1_cli
tier1_cli._install_tier1_provider_hooks()
from mily_ai.tier1_engine_benchmark import benchmark_installed_pack as benchmark_tier1_installed_pack
from mily_ai.models import ModelCatalog

catalog = ModelCatalog(models_root)
pack = catalog.active_pack()
if pack is None or pack.id != 'lite-es-en':
    raise SystemExit('El pack ES→EN Lite no quedó activo')
definition = catalog.definition(pack.id)
report = benchmark_tier1_installed_pack(pack, definition, compute_profile='cpu', repeats=3)
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('ES_EN_LITE_PACK', f'{pack.id}@{pack.version}')
print('ES_EN_ROUTE', report['route'])
print('ES_EN_ASR_P95_MS', report['asrP95Ms'])
print('ES_EN_E2E_P95_MS', report['endToEndP95Ms'])
print('ES_EN_RTF_P95', report['combinedRtfP95'])
print('ES_EN_ENGINE_PEAK_MB', report['enginePeakWorkingSetMb'])
print('ES_EN_TOTAL_PRODUCT_MB', report['totalProductWorkingSetMb'])
if report['route'] != 'es-en':
    raise SystemExit('ES_EN_ROUTE_MISMATCH')
if report['totalProductWorkingSetMb'] > 1536.0:
    raise SystemExit('ES_EN_LITE_PRODUCT_MEMORY_LIMIT')
if report['combinedRtfP95'] >= 0.80:
    raise SystemExit('ES_EN_LITE_RTF_LIMIT')
if report['endToEndP95Ms'] > 1500.0:
    raise SystemExit('ES_EN_LITE_LATENCY_LIMIT')
if not report['passed']:
    raise SystemExit('ES_EN_LITE_GATE_FAILED: ' + ','.join(report['failures']))
print('ES_EN_LITE_GATE_OK')
'@ | Set-Content -Path $Probe -Encoding UTF8

    & $Python $Probe $EngineApp $ModelsRoot $ReportPath
    if ($LASTEXITCODE -ne 0) { throw 'ES→EN Lite no pasó benchmark realtime/memoria total.' }
    if (-not (Test-Path $ReportPath -PathType Leaf)) { throw 'ES→EN Lite no produjo reporte JSON.' }

    Write-Host "ES→EN LITE OK: $ReportPath" -ForegroundColor Green
}
finally {
    Remove-Item $FixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
}
