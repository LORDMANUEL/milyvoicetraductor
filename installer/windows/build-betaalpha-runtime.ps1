[CmdletBinding()]
param(
    [string]$PythonVersion = '3.13.13',
    [string]$ExpectedSha256 = '142666a4a9079507815d395b9bfb73546ec391003d385beb559a9d68fb240062'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$BuildRoot = Join-Path $Root '.build\python-runtime-betaalpha'
$Stage = Join-Path $BuildRoot 'python'
$ZipPath = Join-Path $BuildRoot "python-$PythonVersion-embeddable-amd64.zip"
$OutputRoot = Join-Path $Root 'dist\runtime'
$RuntimeZip = Join-Path $OutputRoot 'milyvoice-python-runtime.zip'
$RuntimeHash = "$RuntimeZip.sha256"
$DownloadUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embeddable-amd64.zip"
$Requirements = Join-Path $Root 'services\ai\requirements.lite.txt'

Write-Host "[BetaAlpha] Preparando runtime Lite Python $PythonVersion..." -ForegroundColor Cyan
Remove-Item $BuildRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $BuildRoot,$Stage,$OutputRoot | Out-Null

Invoke-WebRequest -Uri $DownloadUrl -OutFile $ZipPath -UseBasicParsing
$actual = (Get-FileHash $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $ExpectedSha256.ToLowerInvariant()) {
    throw "El Python oficial no coincide con el SHA-256 fijado. Esperado=$ExpectedSha256 obtenido=$actual"
}
Expand-Archive -Path $ZipPath -DestinationPath $Stage -Force

$sitePackages = Join-Path $Stage 'Lib\site-packages'
New-Item -ItemType Directory -Force -Path $sitePackages | Out-Null
$pth = Get-ChildItem $Stage -Filter 'python*._pth' | Select-Object -First 1
if (-not $pth) { throw 'El paquete embebido no contiene archivo _pth.' }
@(
    'python313.zip',
    '.',
    'Lib',
    'Lib\site-packages',
    'import site'
) | Set-Content -Path $pth.FullName -Encoding ascii

# Solo se instala el conjunto de dependencias definido por el canal Lite.
python -m pip install --disable-pip-version-check --no-input --target $sitePackages -r $Requirements
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron preparar las dependencias BetaAlpha Lite.' }

$embeddedPython = Join-Path $Stage 'python.exe'
$runtimeSmoke = @'
import ctranslate2
import fastapi
import huggingface_hub
import moonshine_voice
import numpy
import pyaudiowpatch
import sentencepiece
import sherpa_onnx
import uvicorn
from faster_whisper import WhisperModel
print('MILY_BETAALPHA_LITE_RUNTIME_OK')
'@
& $embeddedPython -c $runtimeSmoke
if ($LASTEXITCODE -ne 0) {
    throw 'El runtime BetaAlpha Lite no pudo importar sus motores realtime.'
}

# Quality no debe filtrarse al runtime Lite. El helper tolera que ni siquiera
# exista el paquete padre de un módulo con nombre punteado.
$qualityProbe = @'
import importlib.util

def available(name):
    try:
        return importlib.util.find_spec(name) is not None
    except (ModuleNotFoundError, AttributeError, ValueError):
        return False

blocked = ('torch', 'transformers', 'google.cloud.speech_v2')
for name in blocked:
    if available(name):
        raise SystemExit('QUALITY_DEPENDENCY_LEAK:' + name)
print('BETAALPHA_QUALITY_SPLIT_OK')
'@
& $embeddedPython -c $qualityProbe
if ($LASTEXITCODE -ne 0) {
    throw 'El runtime BetaAlpha Lite contiene dependencias Quality no autorizadas.'
}

$metadata = [ordered]@{
    schemaVersion = 2
    channel = 'betaalpha-lite'
    pythonVersion = $PythonVersion
    source = $DownloadUrl
    sourceSha256 = $ExpectedSha256.ToLowerInvariant()
    pythonSha256 = (Get-FileHash $embeddedPython -Algorithm SHA256).Hash.ToLowerInvariant()
    architecture = 'x86_64'
    windowsLoopback = 'PyAudioWPatch-0.2.12.8'
    engineHubRuntimes = @(
        'faster-whisper',
        'moonshine-voice',
        'sherpa-onnx',
        'ctranslate2'
    )
    qualityDependenciesBundled = $false
}
$metadata | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $Stage 'runtime-manifest.json') -Encoding UTF8

Remove-Item $RuntimeZip,$RuntimeHash -Force -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $Stage '*') -DestinationPath $RuntimeZip -CompressionLevel Optimal
$zipHash = (Get-FileHash $RuntimeZip -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -Path $RuntimeHash -Encoding ascii -Value "$zipHash *milyvoice-python-runtime.zip"

Write-Host "BetaAlpha Lite runtime listo: $RuntimeZip" -ForegroundColor Green
