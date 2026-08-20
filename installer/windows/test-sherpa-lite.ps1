[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$env:HF_HUB_DISABLE_TELEMETRY = '1'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$FixtureRoot = Join-Path $Root '.build\sherpa-lite-smoke'
$AppRoot = Join-Path $FixtureRoot 'MilyVoiceTraductor'
$RuntimeRoot = Join-Path $AppRoot 'runtime\python'
$EngineApp = Join-Path $AppRoot 'engine\app'
$ConfigRoot = Join-Path $AppRoot 'config'
$CacheRoot = Join-Path $AppRoot 'cache'
$ModelsRoot = Join-Path $AppRoot 'models'
$RuntimeZip = Join-Path $Root 'dist\runtime\milyvoice-python-runtime.zip'
$ReportPath = Join-Path $Root 'dist\performance\MilyVoiceTraductor-2.1.0-SherpaLiteBench.json'
$Pack = 'sherpa-zipformer-en-es'
$PackVersion = '1.0.0'

Remove-Item $FixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $RuntimeRoot,$EngineApp,$ConfigRoot,$CacheRoot,$ModelsRoot,(Split-Path $ReportPath) | Out-Null
Remove-Item $ReportPath -Force -ErrorAction SilentlyContinue

try {
    Expand-Archive -Path $RuntimeZip -DestinationPath $RuntimeRoot -Force
    Copy-Item (Join-Path $Root 'services\ai\*') $EngineApp -Recurse -Force

    $Python = Join-Path $RuntimeRoot 'python.exe'
    $EngineMain = Join-Path $EngineApp 'main.py'
    if (-not (Test-Path $Python -PathType Leaf)) { throw 'El runtime privado no contiene python.exe.' }

    & $Python -c "import sherpa_onnx, ctranslate2, sentencepiece; print('SHERPA_RUNTIME_OK')"
    if ($LASTEXITCODE -ne 0) { throw 'El runtime privado no contiene Sherpa/CTranslate2/SentencePiece.' }

    Write-Host '[SHERPA-LITE] Descargando pack Zipformer EN→ES fijado...'
    & $Python $EngineMain models `
        --data-dir $AppRoot `
        --config-dir $ConfigRoot `
        --cache-dir $CacheRoot `
        --models-dir $ModelsRoot `
        install $Pack --download-only | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar el pack Sherpa Lite.' }

    & $Python $EngineMain models `
        --data-dir $AppRoot `
        --config-dir $ConfigRoot `
        --cache-dir $CacheRoot `
        --models-dir $ModelsRoot `
        verify $Pack $PackVersion | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'Sherpa Lite no pasó integridad.' }

    & $Python $EngineMain models `
        --data-dir $AppRoot `
        --config-dir $ConfigRoot `
        --cache-dir $CacheRoot `
        --models-dir $ModelsRoot `
        activate $Pack $PackVersion | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo activar Sherpa Lite.' }

    $Probe = Join-Path $FixtureRoot 'benchmark_sherpa.py'
    @'
from pathlib import Path
import json
import sys

engine_app = Path(sys.argv[1])
models_root = Path(sys.argv[2])
fixture_root = Path(sys.argv[3])
report_path = Path(sys.argv[4])
sys.path.insert(0, str(engine_app))

from huggingface_hub import snapshot_download
from mily_ai.engine_benchmark import _read_wave_mono_16k, benchmark_installed_pack
from mily_ai.models import ModelCatalog

catalog = ModelCatalog(models_root)
pack = catalog.active_pack()
if pack is None or pack.id != 'sherpa-zipformer-en-es' or pack.version != '1.0.0':
    raise SystemExit('SHERPA_LITE_PACK_NOT_ACTIVE')
definition = catalog.definition(pack.id)
asr = definition['components']['asr']
audio_root = fixture_root / 'audio'
snapshot_download(
    repo_id=asr['repoId'],
    revision=asr['revision'],
    local_dir=audio_root,
    allow_patterns=['test_wavs/*.wav'],
)
waves = sorted(audio_root.glob('test_wavs/*.wav'))
if not waves:
    raise SystemExit('SHERPA_LITE_REAL_AUDIO_MISSING')
audio = _read_wave_mono_16k(waves[0])
report = benchmark_installed_pack(
    pack,
    definition,
    compute_profile='cpu',
    repeats=3,
    audio_samples=audio,
)
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('SHERPA_LITE_ASR_P95_MS', report['asrP95Ms'])
print('SHERPA_LITE_E2E_P95_MS', report['endToEndP95Ms'])
print('SHERPA_LITE_RTF_P95', report['combinedRtfP95'])
print('SHERPA_LITE_TOTAL_PRODUCT_MB', report['totalProductWorkingSetMb'])
print('SHERPA_LITE_FAILURES', ','.join(report['failures']))
if not report['passed']:
    raise SystemExit('SHERPA_LITE_REAL_GATE_FAILED:' + ','.join(report['failures']))
if float(report['totalProductWorkingSetMb']) > 1536.0:
    raise SystemExit('SHERPA_LITE_MEMORY_LIMIT')
if float(report['combinedRtfP95']) >= 0.80:
    raise SystemExit('SHERPA_LITE_RTF_LIMIT')
if float(report['endToEndP95Ms']) > 1500.0:
    raise SystemExit('SHERPA_LITE_LATENCY_LIMIT')
print('SHERPA_LITE_GATE_OK')
'@ | Set-Content -Path $Probe -Encoding UTF8

    & $Python $Probe $EngineApp $ModelsRoot $FixtureRoot $ReportPath
    if ($LASTEXITCODE -ne 0) { throw 'Sherpa Lite no pasó benchmark real de memoria/RTF/latencia.' }
    if (-not (Test-Path $ReportPath -PathType Leaf)) { throw 'Sherpa Lite no produjo reporte JSON.' }

    Write-Host "SHERPA LITE OK: $ReportPath" -ForegroundColor Green
}
finally {
    Remove-Item $FixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
}
