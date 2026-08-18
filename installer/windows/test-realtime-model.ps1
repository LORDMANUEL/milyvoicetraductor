[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$env:HF_HUB_DISABLE_TELEMETRY = '1'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$FixtureRoot = Join-Path $Root '.build\realtime-model-smoke'
$AppRoot = Join-Path $FixtureRoot 'MilyVoiceTraductor'
$RuntimeRoot = Join-Path $AppRoot 'runtime\python'
$EngineApp = Join-Path $AppRoot 'engine\app'
$ConfigRoot = Join-Path $AppRoot 'config'
$CacheRoot = Join-Path $AppRoot 'cache'
$ModelsRoot = Join-Path $AppRoot 'models'
$RuntimeZip = Join-Path $Root 'dist\runtime\milyvoice-python-runtime.zip'

Remove-Item $FixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $RuntimeRoot,$EngineApp,$ConfigRoot,$CacheRoot,$ModelsRoot | Out-Null

try {
    Expand-Archive -Path $RuntimeZip -DestinationPath $RuntimeRoot -Force
    Copy-Item (Join-Path $Root 'services\ai\*') $EngineApp -Recurse -Force

    $Python = Join-Path $RuntimeRoot 'python.exe'
    $EngineMain = Join-Path $EngineApp 'main.py'
    if (-not (Test-Path $Python -PathType Leaf)) { throw 'El runtime privado no contiene python.exe.' }
    if (-not (Test-Path $EngineMain -PathType Leaf)) { throw 'El fixture no contiene main.py.' }

    Write-Host '[MODEL-SMOKE] Instalando pack real realtime-m2m100...'
    & $Python $EngineMain models `
        --data-dir $AppRoot `
        --config-dir $ConfigRoot `
        --cache-dir $CacheRoot `
        --models-dir $ModelsRoot `
        install realtime-m2m100 | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo descargar/convertir realtime-m2m100.' }

    & $Python $EngineMain models `
        --data-dir $AppRoot `
        --config-dir $ConfigRoot `
        --cache-dir $CacheRoot `
        --models-dir $ModelsRoot `
        verify realtime-m2m100 1.0.0 | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'El pack realtime-m2m100 no pasó verify.' }

    $Probe = Join-Path $FixtureRoot 'probe_realtime.py'
    @'
from pathlib import Path
import sys

engine_app = Path(sys.argv[1])
models_root = Path(sys.argv[2])
sys.path.insert(0, str(engine_app))

from mily_ai.models import ModelCatalog
from mily_ai.providers import FasterWhisperAsr, M2M100CTranslate2Translator

pack = ModelCatalog(models_root).active_pack()
if pack is None or pack.id != "realtime-m2m100":
    raise SystemExit("El pack realtime no quedó activo")

asr = FasterWhisperAsr(pack.path / "components" / "asr", "cpu")
asr._load()
translator = M2M100CTranslate2Translator(pack.path / "components" / "translation", "cpu")

en = translator.translate("Good morning, the meeting starts at nine.", "en")
zh = translator.translate("你好，会议九点开始。", "zh")
if not en.strip() or en.strip().casefold() == "good morning, the meeting starts at nine.".casefold():
    raise SystemExit(f"Traducción EN→ES inválida: {en!r}")
if not zh.strip() or zh.strip() == "你好，会议九点开始。":
    raise SystemExit(f"Traducción ZH→ES inválida: {zh!r}")

print("REALTIME_MODEL_LOAD_OK")
print("EN_ES_OK", en)
print("ZH_ES_OK", zh)
'@ | Set-Content -Path $Probe -Encoding UTF8

    & $Python $Probe $EngineApp $ModelsRoot
    if ($LASTEXITCODE -ne 0) { throw 'El pack real no pudo cargar ASR/traductor o traducir las frases de humo.' }

    Write-Host 'REALTIME MODEL SMOKE OK' -ForegroundColor Green
}
finally {
    Remove-Item $FixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
}
