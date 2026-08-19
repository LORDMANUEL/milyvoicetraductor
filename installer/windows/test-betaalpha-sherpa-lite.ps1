[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$env:HF_HUB_DISABLE_TELEMETRY = '1'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$FixtureRoot = Join-Path $Root '.build\betaalpha-sherpa-smoke'
$AppRoot = Join-Path $FixtureRoot 'MilyVoiceTraductor'
$RuntimeRoot = Join-Path $AppRoot 'runtime\python'
$EngineApp = Join-Path $AppRoot 'engine\app'
$ConfigRoot = Join-Path $AppRoot 'config'
$CacheRoot = Join-Path $AppRoot 'cache'
$ModelsRoot = Join-Path $AppRoot 'models'
$RuntimeZip = Join-Path $Root 'dist\runtime\milyvoice-python-runtime.zip'
$ReportPath = Join-Path $Root 'dist\performance\MilyVoiceTraductor-2.0.1-BetaAlphaSherpaBench.json'

Remove-Item $FixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $RuntimeRoot,$EngineApp,$ConfigRoot,$CacheRoot,$ModelsRoot,(Split-Path $ReportPath) | Out-Null
Remove-Item $ReportPath -Force -ErrorAction SilentlyContinue

try {
    Expand-Archive -Path $RuntimeZip -DestinationPath $RuntimeRoot -Force
    Copy-Item (Join-Path $Root 'services\ai\*') $EngineApp -Recurse -Force

    $Python = Join-Path $RuntimeRoot 'python.exe'
    $EngineMain = Join-Path $EngineApp 'main.py'
    if (-not (Test-Path $Python -PathType Leaf)) { throw 'El runtime privado no contiene python.exe.' }
    if (-not (Test-Path $EngineMain -PathType Leaf)) { throw 'El fixture BetaAlpha no contiene main.py.' }

    & $Python -c "import sherpa_onnx, ctranslate2, sentencepiece; print('BETAALPHA_RUNTIMES_OK')"
    if ($LASTEXITCODE -ne 0) { throw 'El runtime privado no contiene sherpa-onnx/CTranslate2/SentencePiece.' }

    $Packs = @(
        'betaalpha-zipformer-en-es',
        'betaalpha-zipformer-zh-es',
        'betaalpha-paraformer-zh-es'
    )
    foreach ($Pack in $Packs) {
        Write-Host "[BETAALPHA] Preparando $Pack..."
        & $Python $EngineMain models `
            --data-dir $AppRoot `
            --config-dir $ConfigRoot `
            --cache-dir $CacheRoot `
            --models-dir $ModelsRoot `
            install $Pack --download-only | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "No se pudo descargar $Pack." }

        & $Python $EngineMain models `
            --data-dir $AppRoot `
            --config-dir $ConfigRoot `
            --cache-dir $CacheRoot `
            --models-dir $ModelsRoot `
            verify $Pack 1.0.0 | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "$Pack no pasó integridad." }
    }

    $Probe = Join-Path $FixtureRoot 'benchmark_betaalpha_sherpa.py'
    @'
from __future__ import annotations

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
from mily_ai.models import HuggingFacePackInstaller, ModelCatalog

catalog = ModelCatalog(models_root)
installer = HuggingFacePackInstaller(catalog)
pack_ids = (
    'betaalpha-zipformer-en-es',
    'betaalpha-zipformer-zh-es',
    'betaalpha-paraformer-zh-es',
)
reports = {}
for pack_id in pack_ids:
    definition = catalog.definition(pack_id)
    version = str(definition['version'])
    installer.activate(pack_id, version)
    pack = catalog.active_pack()
    if pack is None or pack.id != pack_id:
        raise SystemExit(f'BETAALPHA_ACTIVATION_FAILED:{pack_id}')

    asr = definition['components']['asr']
    audio_root = fixture_root / 'audio' / pack_id
    snapshot_download(
        repo_id=asr['repoId'],
        revision=asr['revision'],
        local_dir=audio_root,
        allow_patterns=['test_wavs/*.wav'],
    )
    waves = sorted(audio_root.glob('test_wavs/*.wav'))
    if not waves:
        raise SystemExit(f'BETAALPHA_TEST_AUDIO_MISSING:{pack_id}')
    audio = _read_wave_mono_16k(waves[0])
    report = benchmark_installed_pack(
        pack,
        definition,
        compute_profile='cpu',
        repeats=3,
        audio_samples=audio,
    )
    reports[pack_id] = report
    print('BETAALPHA_PACK', pack_id)
    print('  ASR_P95_MS', report['asrP95Ms'])
    print('  E2E_P95_MS', report['endToEndP95Ms'])
    print('  COMBINED_RTF_P95', report['combinedRtfP95'])
    print('  TOTAL_PRODUCT_MB', report['totalProductWorkingSetMb'])
    if not report['passed']:
        raise SystemExit(
            f"BETAALPHA_REAL_GATE_FAILED:{pack_id}:" + ','.join(report['failures'])
        )
    if float(report['totalProductWorkingSetMb']) > 1536.0:
        raise SystemExit(f'BETAALPHA_MEMORY_LIMIT:{pack_id}')
    if float(report['combinedRtfP95']) >= 0.80:
        raise SystemExit(f'BETAALPHA_RTF_LIMIT:{pack_id}')
    if float(report['endToEndP95Ms']) > 1500.0:
        raise SystemExit(f'BETAALPHA_LATENCY_LIMIT:{pack_id}')


def score(item):
    # Lower is better. Latency dominates, then RAM, then RTF.
    return (
        float(item['endToEndP95Ms']) / 1500.0 * 0.50
        + float(item['totalProductWorkingSetMb']) / 1536.0 * 0.30
        + float(item['combinedRtfP95']) / 0.80 * 0.20
    )

route_candidates = {
    'en-es': ['betaalpha-zipformer-en-es'],
    'zh-es': ['betaalpha-zipformer-zh-es', 'betaalpha-paraformer-zh-es'],
}
winners = {}
for route, candidates in route_candidates.items():
    winners[route] = min(candidates, key=lambda value: score(reports[value]))

payload = {
    'schemaVersion': 2,
    'productVersion': '2.0.1',
    'channel': 'betaalpha',
    'engineFamily': 'sherpa-onnx-cpu-ultralight',
    'reports': reports,
    'winners': winners,
    'passed': all(bool(item['passed']) for item in reports.values()),
}
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
print('BETAALPHA_EN_WINNER', winners['en-es'])
print('BETAALPHA_ZH_WINNER', winners['zh-es'])
print('BETAALPHA_SHERPA_GATE_OK')
'@ | Set-Content -Path $Probe -Encoding UTF8

    & $Python $Probe $EngineApp $ModelsRoot $FixtureRoot $ReportPath
    if ($LASTEXITCODE -ne 0) { throw 'BetaAlpha sherpa no pasó benchmark real CPU/RAM/latencia.' }
    if (-not (Test-Path $ReportPath -PathType Leaf)) { throw 'BetaAlpha sherpa no produjo reporte JSON.' }

    Write-Host "BETAALPHA SHERPA OK: $ReportPath" -ForegroundColor Green
}
finally {
    Remove-Item $FixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
}
