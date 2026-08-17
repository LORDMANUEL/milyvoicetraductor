[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InstallRoot
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$env:HF_HUB_DISABLE_TELEMETRY = '1'

$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$BootstrapRoot = Join-Path $InstallRoot 'resources\bootstrap'
$RuntimeZip = Join-Path $BootstrapRoot 'runtime\milyvoice-python-runtime.zip'
$RuntimeHash = Join-Path $BootstrapRoot 'runtime\milyvoice-python-runtime.zip.sha256'
$EngineSource = Join-Path $BootstrapRoot 'ai'
$ExtensionSource = Join-Path $BootstrapRoot 'extension'
$BridgeSource = Join-Path $BootstrapRoot 'bridge\milyvoice-bridge.exe'
$RegisterScript = Join-Path $BootstrapRoot 'register-native-host.ps1'
$NativeTemplate = Join-Path $BootstrapRoot 'native-host-template.json'

$AppRoot = Join-Path $env:LOCALAPPDATA 'MilyVoiceTraductor'
$RuntimeParent = Join-Path $AppRoot 'runtime'
$RuntimeRoot = Join-Path $RuntimeParent 'python'
$RuntimeNext = Join-Path $RuntimeParent 'python.next'
$EngineApp = Join-Path $AppRoot 'engine\app'
$ExtensionRoot = Join-Path $AppRoot 'extension'
$BridgeRoot = Join-Path $AppRoot 'bridge'
$BridgeTarget = Join-Path $BridgeRoot 'milyvoice-bridge.exe'
$NativeManifest = Join-Path $BridgeRoot 'com.milyvoice.traductor.json'
$ConfigRoot = Join-Path $AppRoot 'config'
$CacheRoot = Join-Path $AppRoot 'cache'
$ModelsRoot = Join-Path $AppRoot 'models'
$BootstrapStateRoot = Join-Path $AppRoot 'bootstrap'
$StatusPath = Join-Path $BootstrapStateRoot 'status.json'

function Write-Step([string]$Text) {
    Write-Host "[MilyVoiceTraductor] $Text"
}

function Write-BootstrapStatus([string]$State, [string]$Code, [string]$Message) {
    New-Item -ItemType Directory -Force -Path $BootstrapStateRoot | Out-Null
    [ordered]@{
        schemaVersion = 2
        state = $State
        code = $Code
        message = $Message
        updatedAt = (Get-Date).ToUniversalTime().ToString('o')
    } | ConvertTo-Json -Depth 4 | Set-Content -Path $StatusPath -Encoding UTF8
}

function Assert-File([string]$Path, [string]$Code) {
    if (-not (Test-Path $Path)) { throw "$Code|Falta un componente incluido en el instalador." }
}

try {
    Write-BootstrapStatus 'installing' 'BOOTSTRAP_START' 'Preparando componentes locales.'
    foreach ($required in @(
        @{ Path = $RuntimeZip; Code = 'RUNTIME_ARCHIVE_MISSING' },
        @{ Path = $RuntimeHash; Code = 'RUNTIME_HASH_MISSING' },
        @{ Path = (Join-Path $EngineSource 'main.py'); Code = 'ENGINE_MISSING' },
        @{ Path = (Join-Path $ExtensionSource 'manifest.json'); Code = 'EXTENSION_MISSING' },
        @{ Path = $BridgeSource; Code = 'BRIDGE_MISSING' },
        @{ Path = $RegisterScript; Code = 'BRIDGE_REGISTER_MISSING' },
        @{ Path = $NativeTemplate; Code = 'NATIVE_MANIFEST_MISSING' }
    )) {
        Assert-File $required.Path $required.Code
    }

    Write-Step 'Verificando runtime Python privado.'
    $expectedRuntimeHash = ((Get-Content $RuntimeHash -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
    $actualRuntimeHash = (Get-FileHash $RuntimeZip -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($expectedRuntimeHash -ne $actualRuntimeHash) {
        throw 'RUNTIME_HASH_MISMATCH|El runtime incluido no pasó la verificación de integridad.'
    }

    New-Item -ItemType Directory -Force -Path $AppRoot,$RuntimeParent,$ConfigRoot,$CacheRoot,$ModelsRoot,$BridgeRoot | Out-Null
    Remove-Item $RuntimeNext -Recurse -Force -ErrorAction SilentlyContinue
    Expand-Archive -Path $RuntimeZip -DestinationPath $RuntimeNext -Force
    $nextPython = Join-Path $RuntimeNext 'python.exe'
    $runtimeManifestPath = Join-Path $RuntimeNext 'runtime-manifest.json'
    Assert-File $nextPython 'RUNTIME_PYTHON_MISSING'
    Assert-File $runtimeManifestPath 'RUNTIME_MANIFEST_MISSING'

    $runtimeManifest = Get-Content $runtimeManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $pythonHash = (Get-FileHash $nextPython -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($pythonHash -ne ([string]$runtimeManifest.pythonSha256).ToLowerInvariant()) {
        throw 'RUNTIME_PYTHON_HASH_MISMATCH|python.exe no coincide con el manifiesto del runtime.'
    }
    & $nextPython -c "import fastapi,uvicorn,numpy,faster_whisper,transformers,torch,huggingface_hub; print('MILY_RUNTIME_OK')"
    if ($LASTEXITCODE -ne 0) {
        throw 'RUNTIME_IMPORT_FAILED|El runtime privado no pudo cargar sus dependencias.'
    }

    Write-Step 'Activando runtime y motor.'
    if (Test-Path $RuntimeRoot) { Remove-Item $RuntimeRoot -Recurse -Force }
    Move-Item $RuntimeNext $RuntimeRoot
    if (Test-Path $EngineApp) { Remove-Item $EngineApp -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $EngineApp | Out-Null
    Copy-Item (Join-Path $EngineSource '*') $EngineApp -Recurse -Force
    Remove-Item (Join-Path $EngineApp 'mily_ai\__pycache__') -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $EngineApp 'tests\__pycache__') -Recurse -Force -ErrorAction SilentlyContinue

    Write-Step 'Instalando extensión y puente local.'
    if (Test-Path $ExtensionRoot) { Remove-Item $ExtensionRoot -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $ExtensionRoot | Out-Null
    Copy-Item (Join-Path $ExtensionSource '*') $ExtensionRoot -Recurse -Force
    Copy-Item $BridgeSource $BridgeTarget -Force

    & $RegisterScript -BridgePath $BridgeTarget -ManifestTemplate $NativeTemplate -ManifestOutput $NativeManifest
    if ($LASTEXITCODE -ne 0) {
        throw 'NATIVE_HOST_REGISTER_FAILED|No se pudo registrar el puente con los navegadores Chromium.'
    }

    Write-Step 'Ejecutando diagnóstico local.'
    $embeddedPython = Join-Path $RuntimeRoot 'python.exe'
    & $embeddedPython (Join-Path $EngineApp 'main.py') diagnose `
        --data-dir $AppRoot `
        --config-dir $ConfigRoot `
        --cache-dir $CacheRoot `
        --models-dir $ModelsRoot
    if ($LASTEXITCODE -ne 0) {
        throw 'ENGINE_DIAGNOSE_FAILED|El motor incluido no pasó su diagnóstico local.'
    }

    $modelState = if (Test-Path (Join-Path $ModelsRoot 'current.json')) { 'ready' } else { 'model-pending' }
    $message = if ($modelState -eq 'ready') {
        'Runtime, motor, extensión y bridge preparados.'
    } else {
        'Runtime, motor, extensión y bridge preparados. El modelo se descargará desde la aplicación.'
    }
    Write-BootstrapStatus $modelState 'BOOTSTRAP_OK' $message
    Write-Step 'Preparación local completada sin depender de Python del sistema.'
    exit 0
} catch {
    $raw = [string]$_.Exception.Message
    $parts = $raw.Split('|', 2)
    $code = if ($parts.Count -eq 2) { $parts[0] } else { 'BOOTSTRAP_FAILED' }
    $message = if ($parts.Count -eq 2) { $parts[1] } else { 'La preparación local no terminó correctamente.' }
    Write-BootstrapStatus 'failed' $code $message
    Write-Error "$code`: $message"
    exit 1
}
