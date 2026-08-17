[CmdletBinding()]
param(
    [ValidateSet('business-qwen','lite-nllb','none')]
    [string]$ModelPack = 'business-qwen',
    [switch]$SkipModelDownload,
    [switch]$InstallPythonIfMissing
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Write-Step([string]$Text) { Write-Host "`n[MilyVoice] $Text" -ForegroundColor Cyan }
function Get-Python313 {
    $commands = @(
        @{Exe='py'; Args=@('-3.13')},
        @{Exe='python'; Args=@()},
        @{Exe=(Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'); Args=@()}
    )
    foreach ($candidate in $commands) {
        try {
            if (-not (Get-Command $candidate.Exe -ErrorAction SilentlyContinue) -and -not (Test-Path $candidate.Exe)) { continue }
            $version = & $candidate.Exe @($candidate.Args) -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($LASTEXITCODE -eq 0 -and $version.Trim() -eq '3.13') { return $candidate }
        } catch { }
    }
    return $null
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$AppRoot = Join-Path $env:LOCALAPPDATA 'MilyVoiceTraductor'
$EngineRoot = Join-Path $AppRoot 'engine'
$PythonRoot = Join-Path $EngineRoot 'python'
$EngineApp = Join-Path $EngineRoot 'app'
$ExtensionRoot = Join-Path $AppRoot 'extension'

Write-Step 'Comprobando Python 3.13'
$Python = Get-Python313
if (-not $Python -and $InstallPythonIfMissing) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'No se encontró Python 3.13 ni winget. Instala Python 3.13 x64 y vuelve a ejecutar.'
    }
    Write-Step 'Instalando Python 3.13 para el usuario actual mediante winget'
    winget install --id Python.Python.3.13 --exact --scope user --accept-package-agreements --accept-source-agreements
    $Python = Get-Python313
}
if (-not $Python) {
    throw 'Python 3.13 no está disponible. Repite con -InstallPythonIfMissing o instala Python 3.13 x64.'
}

Write-Step 'Preparando carpetas privadas de la aplicación'
New-Item -ItemType Directory -Force -Path $AppRoot,$EngineRoot,$ExtensionRoot | Out-Null
if (Test-Path $EngineApp) { Remove-Item $EngineApp -Recurse -Force }
Copy-Item (Join-Path $RepoRoot 'services\ai') $EngineApp -Recurse -Force
Remove-Item (Join-Path $EngineApp 'mily_ai\__pycache__') -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $EngineApp 'tests\__pycache__') -Recurse -Force -ErrorAction SilentlyContinue
if (Test-Path $ExtensionRoot) { Remove-Item $ExtensionRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $ExtensionRoot | Out-Null
Copy-Item (Join-Path $RepoRoot 'apps\extension\*') $ExtensionRoot -Recurse -Force

Write-Step 'Creando runtime Python aislado'
if (-not (Test-Path (Join-Path $PythonRoot 'Scripts\python.exe'))) {
    & $Python.Exe @($Python.Args) -m venv $PythonRoot
}
$VenvPython = Join-Path $PythonRoot 'Scripts\python.exe'
& $VenvPython -m pip install --disable-pip-version-check --upgrade pip
& $VenvPython -m pip install --disable-pip-version-check $EngineApp

Write-Step 'Validando motor local'
& $VenvPython (Join-Path $EngineApp 'main.py') diagnose `
    --data-dir $AppRoot `
    --config-dir (Join-Path $AppRoot 'config') `
    --cache-dir (Join-Path $AppRoot 'cache') `
    --models-dir (Join-Path $AppRoot 'models')
if ($LASTEXITCODE -ne 0) { throw 'El diagnóstico del motor local falló.' }

if (-not $SkipModelDownload -and $ModelPack -ne 'none') {
    Write-Step "Descargando pack de modelos: $ModelPack"
    & $VenvPython (Join-Path $EngineApp 'main.py') models `
        --data-dir $AppRoot `
        --config-dir (Join-Path $AppRoot 'config') `
        --cache-dir (Join-Path $AppRoot 'cache') `
        --models-dir (Join-Path $AppRoot 'models') `
        install $ModelPack
    if ($LASTEXITCODE -ne 0) { throw 'La descarga del pack de modelos no terminó correctamente.' }
}

Write-Step 'Runtime listo'
Write-Host "Extensión Chromium: $ExtensionRoot" -ForegroundColor Green
Write-Host 'En Chrome/Edge: Extensiones > Modo desarrollador > Cargar descomprimida > selecciona esa carpeta.' -ForegroundColor Green
Write-Host 'Los permisos de captura se solicitan al navegador y el audio solo se captura después de pulsar Iniciar traducción.' -ForegroundColor Green
