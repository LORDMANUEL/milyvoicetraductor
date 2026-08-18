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

# Las dependencias se resuelven en el runner de build. En el equipo del usuario
# no se ejecuta pip ni se consulta Internet para preparar el runtime.
python -m pip install --disable-pip-version-check --no-input --target $sitePackages -r (Join-Path $Root 'services\ai\requirements.runtime.txt')
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron preparar las dependencias del runtime privado.' }

$embeddedPython = Join-Path $Stage 'python.exe'
& $embeddedPython -c "import fastapi, uvicorn, numpy, faster_whisper, transformers, torch, huggingface_hub; print('MILY_RUNTIME_OK')"
if ($LASTEXITCODE -ne 0) { throw 'El Python embebido no pudo importar todas las dependencias requeridas.' }

$metadata = [ordered]@{
    schemaVersion = 1
    pythonVersion = $PythonVersion
    source = $DownloadUrl
    sourceSha256 = $ExpectedSha256.ToLowerInvariant()
    pythonSha256 = (Get-FileHash $embeddedPython -Algorithm SHA256).Hash.ToLowerInvariant()
    architecture = 'x86_64'
}
$metadata | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $Stage 'runtime-manifest.json') -Encoding UTF8

Remove-Item $RuntimeZip,$RuntimeHash -Force -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $Stage '*') -DestinationPath $RuntimeZip -CompressionLevel Optimal
$zipHash = (Get-FileHash $RuntimeZip -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -Path $RuntimeHash -Encoding ascii -Value "$zipHash *milyvoice-python-runtime.zip"

Write-Host "Runtime privado listo: $RuntimeZip" -ForegroundColor Green
