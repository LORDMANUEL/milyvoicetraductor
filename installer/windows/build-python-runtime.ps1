[CmdletBinding()]
param(
    [string]$PythonVersion = '3.13.13',
    [string]$ExpectedSha256 = '142666a4a9079507815d395b9bfb73546ec391003d385beb559a9d68fb240062'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$BuildRoot = Join-Path $Root '.build\python-runtime'
$Stage = Join-Path $BuildRoot 'python'
$ZipPath = Join-Path $BuildRoot "python-$PythonVersion-embeddable-amd64.zip"
$OutputRoot = Join-Path $Root 'dist\runtime'
$RuntimeZip = Join-Path $OutputRoot 'milyvoice-python-runtime.zip'
$RuntimeHash = "$RuntimeZip.sha256"
$DownloadUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embeddable-amd64.zip"

# CTranslate2 y otros wheels nativos de Windows dependen del Visual C++ Runtime.
# Para que el runtime sea privado/autónomo, copiamos el CRT al lado de python.exe.
$RequiredAppLocalVisualCppDlls = @(
    'concrt140.dll',
    'msvcp140.dll',
    'vcruntime140.dll',
    'vcruntime140_1.dll'
)
$OptionalAppLocalVisualCppDlls = @(
    'msvcp140_1.dll',
    'msvcp140_2.dll',
    'msvcp140_atomic_wait.dll',
    'msvcp140_codecvt_ids.dll'
)

$RequiredRuntimeModules = @(
    'fastapi',
    'uvicorn',
    'numpy',
    'faster_whisper',
    'ctranslate2',
    'huggingface_hub',
    'sentencepiece'
)
$OptionalRuntimeModules = @(
    'transformers',
    'torch',
    'moonshine_voice',
    'sherpa_onnx',
    'onnxruntime',
    'vosk',
    'google.cloud.speech_v2',
    'pyaudiowpatch'
)

Write-Host "[MilyVoice] Preparando Python $PythonVersion privado..." -ForegroundColor Cyan
Remove-Item $BuildRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $BuildRoot,$Stage,$OutputRoot | Out-Null

Invoke-WebRequest -Uri $DownloadUrl -OutFile $ZipPath -UseBasicParsing
$actual = (Get-FileHash $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $ExpectedSha256.ToLowerInvariant()) {
    throw "El paquete oficial de Python no coincide con el SHA-256 fijado. Esperado=$ExpectedSha256 obtenido=$actual"
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

# requirements.runtime.txt contiene solo versiones exactas. No se usa --upgrade:
# una reconstrucción debe reproducir el conjunto validado, no resolver rangos nuevos.
python -m pip install --disable-pip-version-check --no-input --target $sitePackages -r (Join-Path $Root 'services\ai\requirements.runtime.txt')
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron preparar las dependencias del runtime privado.' }

$systemRoot = if ([string]::IsNullOrWhiteSpace($env:SystemRoot)) { 'C:\Windows' } else { $env:SystemRoot }
$system32 = Join-Path $systemRoot 'System32'
$appLocalVisualCppRuntime = @()
foreach ($dllName in @($RequiredAppLocalVisualCppDlls + $OptionalAppLocalVisualCppDlls)) {
    $source = Join-Path $system32 $dllName
    $destination = Join-Path $Stage $dllName
    if (-not (Test-Path $source -PathType Leaf)) {
        if ($RequiredAppLocalVisualCppDlls -contains $dllName) {
            throw "El runner Windows no contiene la DLL obligatoria del Visual C++ Runtime: $dllName"
        }
        continue
    }
    Copy-Item -LiteralPath $source -Destination $destination -Force
    $copied = Get-Item -LiteralPath $destination
    $appLocalVisualCppRuntime += [ordered]@{
        file = $dllName
        sha256 = (Get-FileHash $destination -Algorithm SHA256).Hash.ToLowerInvariant()
        fileVersion = [string]$copied.VersionInfo.FileVersion
    }
}

$embeddedPython = Join-Path $Stage 'python.exe'
foreach ($module in @($RequiredRuntimeModules + $OptionalRuntimeModules)) {
    $probe = "import importlib; importlib.import_module('$module'); print('MILY_RUNTIME_MODULE_OK')"
    & $embeddedPython -c $probe
    if ($LASTEXITCODE -ne 0) {
        throw "El Python embebido no pudo importar el módulo empaquetado '$module' durante el build."
    }
}

# Registrar el inventario efectivo, no solo el requirements de entrada. Esto deja
# evidencia exacta de todas las dependencias transitivas incluidas en el ZIP.
$inventoryProbe = @'
import importlib.metadata
import json
packages = []
for dist in importlib.metadata.distributions():
    name = dist.metadata.get("Name")
    if name:
        packages.append({"Name": name, "Version": dist.version})
packages.sort(key=lambda item: (item["Name"].lower(), item["Version"]))
print(json.dumps(packages, separators=(",", ":")))
'@
$inventoryJson = & $embeddedPython -c $inventoryProbe
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($inventoryJson)) {
    throw 'No se pudo inventariar el conjunto exacto de paquetes del runtime privado.'
}
$installedPackages = @($inventoryJson | ConvertFrom-Json)
if ($installedPackages.Count -lt 10) {
    throw "Inventario de paquetes incompleto: $($installedPackages.Count) entradas."
}

# Mantener schemaVersion 3 por compatibilidad. installedPackages es un campo
# aditivo que consumidores antiguos pueden ignorar sin migración de esquema.
$metadata = [ordered]@{
    schemaVersion = 3
    pythonVersion = $PythonVersion
    source = $DownloadUrl
    sourceSha256 = $ExpectedSha256.ToLowerInvariant()
    pythonSha256 = (Get-FileHash $embeddedPython -Algorithm SHA256).Hash.ToLowerInvariant()
    architecture = 'x86_64'
    windowsLoopback = 'PyAudioWPatch-0.2.12.8'
    requiredModules = $RequiredRuntimeModules
    optionalModules = $OptionalRuntimeModules
    installedPackages = $installedPackages
    appLocalVisualCppRuntime = $appLocalVisualCppRuntime
    engineHubRuntimes = @(
        'faster-whisper',
        'moonshine-voice',
        'sherpa-onnx',
        'vosk',
        'ctranslate2',
        'transformers',
        'google-cloud-speech'
    )
}
$metadata | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $Stage 'runtime-manifest.json') -Encoding UTF8

Remove-Item $RuntimeZip,$RuntimeHash -Force -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $Stage '*') -DestinationPath $RuntimeZip -CompressionLevel Optimal
$zipHash = (Get-FileHash $RuntimeZip -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -Path $RuntimeHash -Encoding ascii -Value "$zipHash *milyvoice-python-runtime.zip"

Write-Host "Runtime privado listo: $RuntimeZip" -ForegroundColor Green
