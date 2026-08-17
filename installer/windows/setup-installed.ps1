[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InstallRoot,
    [ValidateSet('business-qwen','lite-nllb','none')]
    [string]$ModelPack = 'business-qwen',
    [switch]$SkipModelDownload
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
$env:HF_HUB_DISABLE_TELEMETRY = '1'

function Write-Step([string]$Text) {
    Write-Host "[MilyVoiceTraductor] $Text"
}

function Get-Python313 {
    $commands = @(
        @{ Exe = 'py'; Args = @('-3.13') },
        @{ Exe = 'python'; Args = @() },
        @{ Exe = (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'); Args = @() }
    )
    foreach ($candidate in $commands) {
        try {
            if (-not (Get-Command $candidate.Exe -ErrorAction SilentlyContinue) -and -not (Test-Path $candidate.Exe)) {
                continue
            }
            $version = & $candidate.Exe @($candidate.Args) -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($LASTEXITCODE -eq 0 -and $version.Trim() -eq '3.13') {
                return $candidate
            }
        } catch { }
    }
    return $null
}

$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$BootstrapRoot = Join-Path $InstallRoot 'resources\bootstrap'
$EngineSource = Join-Path $BootstrapRoot 'ai'
$ExtensionSource = Join-Path $BootstrapRoot 'extension'
$AppRoot = Join-Path $env:LOCALAPPDATA 'MilyVoiceTraductor'
$EngineRoot = Join-Path $AppRoot 'engine'
$PythonRoot = Join-Path $EngineRoot 'python'
$EngineApp = Join-Path $EngineRoot 'app'
$ExtensionRoot = Join-Path $AppRoot 'extension'
$ConfigRoot = Join-Path $AppRoot 'config'
$CacheRoot = Join-Path $AppRoot 'cache'
$ModelsRoot = Join-Path $AppRoot 'models'
$BootstrapStateRoot = Join-Path $AppRoot 'bootstrap'
$StatusPath = Join-Path $BootstrapStateRoot 'status.json'

function Write-BootstrapStatus([string]$State, [string]$Message) {
    New-Item -ItemType Directory -Force -Path $BootstrapStateRoot | Out-Null
    $payload = [ordered]@{
        schemaVersion = 1
        state = $State
        message = $Message
        modelPack = $ModelPack
        updatedAt = (Get-Date).ToUniversalTime().ToString('o')
    }
    $payload | ConvertTo-Json -Depth 4 | Set-Content -Path $StatusPath -Encoding UTF8
}

try {
    Write-BootstrapStatus 'installing' 'Preparando runtime local.'

    if (-not (Test-Path (Join-Path $EngineSource 'main.py'))) {
        throw "No se encontró el motor empaquetado en $EngineSource"
    }
    if (-not (Test-Path (Join-Path $ExtensionSource 'manifest.json'))) {
        throw "No se encontró la extensión empaquetada en $ExtensionSource"
    }

    Write-Step 'Comprobando Python 3.13.'
    $Python = Get-Python313
    if (-not $Python) {
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
            throw 'Python 3.13 no está instalado y winget no está disponible. Instala Python 3.13 x64 y vuelve a ejecutar el instalador.'
        }
        Write-Step 'Instalando Python 3.13 para el usuario actual.'
        & winget install --id Python.Python.3.13 --exact --scope user --silent --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) {
            throw "winget no pudo instalar Python 3.13 (código $LASTEXITCODE)."
        }
        $Python = Get-Python313
        if (-not $Python) {
            throw 'Python 3.13 fue solicitado a winget, pero todavía no está disponible para el instalador.'
        }
    }

    Write-Step 'Preparando carpetas privadas de la aplicación.'
    New-Item -ItemType Directory -Force -Path $AppRoot,$EngineRoot,$ConfigRoot,$CacheRoot,$ModelsRoot,$ExtensionRoot | Out-Null

    if (Test-Path $EngineApp) {
        Remove-Item $EngineApp -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $EngineApp | Out-Null
    Copy-Item (Join-Path $EngineSource '*') $EngineApp -Recurse -Force
    Remove-Item (Join-Path $EngineApp 'mily_ai\__pycache__') -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $EngineApp 'tests\__pycache__') -Recurse -Force -ErrorAction SilentlyContinue

    if (Test-Path $ExtensionRoot) {
        Remove-Item $ExtensionRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $ExtensionRoot | Out-Null
    Copy-Item (Join-Path $ExtensionSource '*') $ExtensionRoot -Recurse -Force

    Write-Step 'Creando runtime Python aislado.'
    $VenvPython = Join-Path $PythonRoot 'Scripts\python.exe'
    if (-not (Test-Path $VenvPython)) {
        if (Test-Path $PythonRoot) {
            Remove-Item $PythonRoot -Recurse -Force
        }
        & $Python.Exe @($Python.Args) -m venv $PythonRoot
        if ($LASTEXITCODE -ne 0) {
            throw 'No se pudo crear el entorno Python aislado.'
        }
    }

    & $VenvPython -m pip install --disable-pip-version-check --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw 'No se pudo actualizar pip dentro del runtime local.'
    }
    & $VenvPython -m pip install --disable-pip-version-check --upgrade $EngineApp
    if ($LASTEXITCODE -ne 0) {
        throw 'No se pudieron instalar las dependencias del motor local.'
    }

    Write-Step 'Validando motor local.'
    & $VenvPython (Join-Path $EngineApp 'main.py') diagnose `
        --data-dir $AppRoot `
        --config-dir $ConfigRoot `
        --cache-dir $CacheRoot `
        --models-dir $ModelsRoot
    if ($LASTEXITCODE -ne 0) {
        throw 'El diagnóstico del motor local falló.'
    }

    if (-not $SkipModelDownload -and $ModelPack -ne 'none') {
        Write-Step "Descargando y verificando pack de modelos: $ModelPack."
        & $VenvPython (Join-Path $EngineApp 'main.py') models `
            --data-dir $AppRoot `
            --config-dir $ConfigRoot `
            --cache-dir $CacheRoot `
            --models-dir $ModelsRoot `
            install $ModelPack
        if ($LASTEXITCODE -ne 0) {
            Write-BootstrapStatus 'runtime-ready-model-pending' 'Motor y extensión instalados; la descarga del modelo quedó pendiente y puede reintentarse desde Modelos.'
            Write-Warning 'Motor instalado, pero el pack de modelos no terminó de descargarse. Puede reintentarse desde la aplicación.'
            exit 2
        }
    }

    Write-BootstrapStatus 'ready' 'Runtime, extensión y modelo recomendados preparados.'
    Write-Step 'Instalación local completa.'
    Write-Host "Extensión Chromium: $ExtensionRoot"
    exit 0
} catch {
    $safeMessage = $_.Exception.Message
    Write-BootstrapStatus 'failed' $safeMessage
    Write-Error $safeMessage
    exit 1
}
