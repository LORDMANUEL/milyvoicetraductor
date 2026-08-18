[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Installer = Get-ChildItem (Join-Path $Root 'target\release\bundle\nsis\*-setup.exe') -File | Select-Object -First 1
if (-not $Installer) { throw 'No se encontró el instalador NSIS generado.' }

$InstallRoot = Join-Path $env:RUNNER_TEMP 'MilyVoiceTraductor-NSIS-Test'
$AppRoot = Join-Path $env:LOCALAPPDATA 'MilyVoiceTraductor'
$StatusPath = Join-Path $AppRoot 'bootstrap\status.json'

function Assert-File([string]$Path, [string]$Message) {
    if (-not (Test-Path $Path -PathType Leaf)) { throw $Message }
}

function Run-ProcessChecked([string]$FilePath, [string[]]$Arguments, [int]$TimeoutMs = 300000) {
    $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -PassThru
    if (-not $process.WaitForExit($TimeoutMs)) {
        try { $process.Kill($true) } catch {}
        throw "El proceso excedió el tiempo permitido: $FilePath"
    }
    if ($process.ExitCode -ne 0) {
        throw "El proceso devolvió código $($process.ExitCode): $FilePath"
    }
}

Get-Process -Name 'MilyVoiceTraductor' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Remove-Item $InstallRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $AppRoot -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Instalando NSIS real: $($Installer.FullName)" -ForegroundColor Cyan
Run-ProcessChecked $Installer.FullName @('/S', "/D=$InstallRoot") 300000

$DesktopExe = Join-Path $InstallRoot 'MilyVoiceTraductor.exe'
$BootstrapRoot = Join-Path $InstallRoot 'bootstrap'
$BootstrapScript = Join-Path $BootstrapRoot 'setup-installed.ps1'
$PrivatePython = Join-Path $AppRoot 'runtime\python\python.exe'
$EngineMain = Join-Path $AppRoot 'engine\app\main.py'
$EnginePackage = Join-Path $AppRoot 'engine\app\mily_ai\__init__.py'
$ExtensionManifest = Join-Path $AppRoot 'extension\manifest.json'
$Bridge = Join-Path $AppRoot 'bridge\milyvoice-bridge.exe'
$NativeManifest = Join-Path $AppRoot 'bridge\com.milyvoice.traductor.json'

Assert-File $DesktopExe 'NSIS no dejó MilyVoiceTraductor.exe.'
Assert-File $BootstrapScript 'NSIS no incluyó bootstrap\setup-installed.ps1 junto al ejecutable.'
Assert-File (Join-Path $BootstrapRoot 'register-native-host.ps1') 'NSIS no incluyó el registrador Native Messaging.'
Assert-File (Join-Path $BootstrapRoot 'runtime\milyvoice-python-runtime.zip') 'NSIS no incluyó el runtime privado.'
Assert-File (Join-Path $BootstrapRoot 'bridge\milyvoice-bridge.exe') 'NSIS no incluyó el bridge compilado.'
Assert-File (Join-Path $BootstrapRoot 'ai\mily_ai\__init__.py') 'NSIS no incluyó el paquete mily_ai dentro del bootstrap.'
Assert-File (Join-Path $BootstrapRoot 'extension\manifest.json') 'NSIS no incluyó la extensión dentro del bootstrap.'
Assert-File $PrivatePython 'NSIS/post-install no dejó el runtime Python privado.'
Assert-File $EngineMain 'NSIS/post-install no dejó main.py del motor.'
Assert-File $EnginePackage 'NSIS/post-install perdió el paquete mily_ai.'
Assert-File $ExtensionManifest 'NSIS/post-install no dejó la extensión Chromium.'
Assert-File $Bridge 'NSIS/post-install no dejó el bridge Native Messaging.'
Assert-File $NativeManifest 'NSIS/post-install no generó el manifiesto Native Messaging.'
Assert-File $StatusPath 'NSIS/post-install no dejó estado bootstrap.'

$status = Get-Content $StatusPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($status.state -notin @('model-pending', 'ready')) {
    throw "NSIS dejó bootstrap en estado inválido: $($status.state) / $($status.code) / $($status.message)"
}
if ($status.code -ne 'BOOTSTRAP_OK') {
    throw "NSIS no terminó con BOOTSTRAP_OK: $($status.code)"
}

foreach ($key in @(
    'HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.milyvoice.traductor',
    'HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\com.milyvoice.traductor',
    'HKCU:\Software\BraveSoftware\Brave-Browser\NativeMessagingHosts\com.milyvoice.traductor'
)) {
    if (-not (Test-Path $key)) { throw "NSIS no registró Native Messaging: $key" }
}

Start-Sleep -Seconds 2
Get-Process -Name 'MilyVoiceTraductor' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host 'NSIS INSTALLER FLOW OK' -ForegroundColor Green
