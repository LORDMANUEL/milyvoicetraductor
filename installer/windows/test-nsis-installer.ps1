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

function Assert-WindowsPowerShell51Syntax([string]$Path) {
    $windowsRoot = if ([string]::IsNullOrWhiteSpace($env:WINDIR)) { 'C:\Windows' } else { $env:WINDIR }
    $powershell = Join-Path $windowsRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    Assert-File $powershell 'No se encontró Windows PowerShell 5.1 para validar el bootstrap.'
    $escapedPath = $Path.Replace("'", "''")
    $parserProbe = @"
`$tokens = `$null
`$errors = `$null
[System.Management.Automation.Language.Parser]::ParseFile('$escapedPath', [ref]`$tokens, [ref]`$errors) | Out-Null
if (`$errors.Count -gt 0) {
    `$errors | ForEach-Object { [Console]::Error.WriteLine(`$_.Message) }
    exit 1
}
exit 0
"@
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($parserProbe))
    & $powershell -NoProfile -NonInteractive -EncodedCommand $encoded
    if ($LASTEXITCODE -ne 0) {
        throw "Windows PowerShell 5.1 rechazó la sintaxis de $Path"
    }
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

function Assert-BootstrapReady([string]$Path) {
    if (-not (Test-Path $Path -PathType Leaf)) {
        throw 'NSIS/post-install no generó bootstrap\status.json; el hook no completó el bootstrap controlado.'
    }
    $status = Get-Content $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host "Bootstrap NSIS: state=$($status.state) code=$($status.code) message=$($status.message)" -ForegroundColor Cyan
    if ($status.state -eq 'failed') {
        throw "NSIS post-install falló: $($status.code) / $($status.message)"
    }
    if ($status.state -notin @('model-pending', 'ready')) {
        throw "NSIS dejó bootstrap en estado inválido: $($status.state) / $($status.code) / $($status.message)"
    }
    if ($status.code -ne 'BOOTSTRAP_OK') {
        throw "NSIS no terminó con BOOTSTRAP_OK: $($status.code) / $($status.message)"
    }
}

function Assert-DesktopStartsWithWindow([string]$DesktopExe, [string]$Label) {
    Write-Host "Arrancando Desktop instalado ($Label)..." -ForegroundColor Cyan
    $process = Start-Process -FilePath $DesktopExe -PassThru
    try {
        $windowReady = $false
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            Start-Sleep -Milliseconds 500
            if ($process.HasExited) {
                throw "MilyVoiceTraductor.exe terminó durante $Label con código $($process.ExitCode)."
            }
            $process.Refresh()
            if ($process.MainWindowHandle -ne 0) {
                $windowReady = $true
                break
            }
        }
        if (-not $windowReady) {
            throw "MilyVoiceTraductor.exe siguió vivo durante $Label, pero no creó una ventana Windows visible."
        }
        Write-Host "Desktop visible: PID=$($process.Id) HWND=$($process.MainWindowHandle) TITLE='$($process.MainWindowTitle)'" -ForegroundColor Green
    } finally {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            $process.WaitForExit(10000) | Out-Null
        }
    }
}

function Get-ModelFileSnapshot([string]$ModelsRoot) {
    if (-not (Test-Path $ModelsRoot -PathType Container)) { return @() }
    return @(
        Get-ChildItem -LiteralPath $ModelsRoot -File -Recurse -Force -ErrorAction SilentlyContinue |
            Sort-Object FullName |
            ForEach-Object { "$($_.FullName)|$($_.Length)" }
    )
}

function Assert-FirstRunStartsWithoutModelDownload(
    [string]$DesktopExe,
    [string]$ModelsRoot,
    [string]$CurrentModel,
    [string]$StatusPath
) {
    if (Test-Path $CurrentModel -PathType Leaf) {
        throw 'La instalación limpia activó un modelo antes de abrir MilyVoice.'
    }

    $status = Get-Content $StatusPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($status.state -ne 'model-pending') {
        throw "Una instalación limpia sin modelos debe terminar en model-pending, no '$($status.state)'."
    }
    if ($status.code -ne 'BOOTSTRAP_OK') {
        throw "El bootstrap limpio no terminó con BOOTSTRAP_OK: $($status.code)."
    }

    $modelFilesBeforeLaunch = @(Get-ModelFileSnapshot $ModelsRoot)
    Write-Host 'Arrancando Desktop sin modelo para comprobar que Engine Hub conserva el control de descarga...' -ForegroundColor Cyan
    $process = Start-Process -FilePath $DesktopExe -PassThru
    try {
        $windowReady = $false
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            Start-Sleep -Milliseconds 500
            if ($process.HasExited) {
                throw "MilyVoiceTraductor.exe terminó en el primer arranque sin modelo con código $($process.ExitCode)."
            }
            $process.Refresh()
            if ($process.MainWindowHandle -ne 0) {
                $windowReady = $true
                break
            }
        }
        if (-not $windowReady) {
            throw 'MilyVoiceTraductor.exe no creó una ventana visible en el primer arranque sin modelo.'
        }

        # Si quedara cualquier descarga implícita del onboarding anterior, cinco
        # segundos son suficientes para que aparezca staging/current.json o un
        # archivo nuevo bajo models. Sin interacción del usuario no debe ocurrir.
        Start-Sleep -Seconds 5
        $process.Refresh()
        if ($process.HasExited) {
            throw "MilyVoiceTraductor.exe terminó después de abrir Engine Hub con código $($process.ExitCode)."
        }
        if (Test-Path $CurrentModel -PathType Leaf) {
            throw 'El primer arranque activó un modelo automáticamente; la descarga debe iniciarse únicamente desde Engine Hub.'
        }

        $modelFilesAfterLaunch = @(Get-ModelFileSnapshot $ModelsRoot)
        $modelChanges = @(Compare-Object -ReferenceObject $modelFilesBeforeLaunch -DifferenceObject $modelFilesAfterLaunch)
        if ($modelChanges.Count -gt 0) {
            $details = ($modelChanges | ForEach-Object { "$($_.SideIndicator) $($_.InputObject)" }) -join '; '
            throw "El primer arranque modificó la carpeta de modelos sin consentimiento: $details"
        }

        $statusAfterLaunch = Get-Content $StatusPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($statusAfterLaunch.state -ne 'model-pending') {
            throw "El primer arranque cambió model-pending sin que el usuario eligiera un modelo: $($statusAfterLaunch.state)."
        }
        Write-Host "FIRST RUN NO-MODEL OK: visible HWND=$($process.MainWindowHandle), model-pending intacto, cero descargas implícitas." -ForegroundColor Green
    } finally {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            $process.WaitForExit(10000) | Out-Null
        }
    }
}

# Gate explícito del shell que ejecuta NSIS en PCs reales. pwsh y powershell.exe
# no son intercambiables para compatibilidad de parser.
foreach ($bundledScript in @(
    (Join-Path $PSScriptRoot 'setup-installed.ps1'),
    (Join-Path $PSScriptRoot 'register-native-host.ps1')
)) {
    Assert-WindowsPowerShell51Syntax $bundledScript
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
$RuntimeManifest = Join-Path $AppRoot 'runtime\python\runtime-manifest.json'
$EngineMain = Join-Path $AppRoot 'engine\app\main.py'
$EnginePackage = Join-Path $AppRoot 'engine\app\mily_ai\__init__.py'
$ExtensionManifest = Join-Path $AppRoot 'extension\manifest.json'
$Bridge = Join-Path $AppRoot 'bridge\milyvoice-bridge.exe'
$NativeManifest = Join-Path $AppRoot 'bridge\com.milyvoice.traductor.json'
$ModelsRoot = Join-Path $AppRoot 'models'
$CurrentModel = Join-Path $ModelsRoot 'current.json'

Assert-File $DesktopExe 'NSIS no dejó MilyVoiceTraductor.exe.'
Assert-File $BootstrapScript 'NSIS no incluyó bootstrap\setup-installed.ps1 junto al ejecutable.'
Assert-File (Join-Path $BootstrapRoot 'register-native-host.ps1') 'NSIS no incluyó el registrador Native Messaging.'
Assert-File (Join-Path $BootstrapRoot 'runtime\milyvoice-python-runtime.zip') 'NSIS no incluyó el runtime privado.'
Assert-File (Join-Path $BootstrapRoot 'runtime\milyvoice-python-runtime.zip.sha256') 'NSIS no incluyó el SHA-256 del runtime privado.'
Assert-File (Join-Path $BootstrapRoot 'bridge\milyvoice-bridge.exe') 'NSIS no incluyó el bridge compilado.'
Assert-File (Join-Path $BootstrapRoot 'ai\mily_ai\__init__.py') 'NSIS no incluyó el paquete mily_ai dentro del bootstrap.'
Assert-File (Join-Path $BootstrapRoot 'extension\manifest.json') 'NSIS no incluyó la extensión dentro del bootstrap.'

if (-not (Test-Path $StatusPath -PathType Leaf)) {
    Write-Host 'Contenido instalado junto al EXE:' -ForegroundColor Yellow
    Get-ChildItem $InstallRoot -Recurse -Force -ErrorAction SilentlyContinue |
        Select-Object -First 80 -ExpandProperty FullName |
        ForEach-Object { Write-Host "  $_" }
    Write-Host 'Contenido LOCALAPPDATA/MilyVoiceTraductor:' -ForegroundColor Yellow
    if (Test-Path $AppRoot) {
        Get-ChildItem $AppRoot -Recurse -Force -ErrorAction SilentlyContinue |
            Select-Object -First 80 -ExpandProperty FullName |
            ForEach-Object { Write-Host "  $_" }
    } else {
        Write-Host '  <no existe>'
    }
}
Assert-BootstrapReady $StatusPath

Assert-File $PrivatePython 'NSIS/post-install no dejó el runtime Python privado aunque reportó BOOTSTRAP_OK.'
Assert-File $RuntimeManifest 'NSIS/post-install no dejó el manifiesto del runtime privado aunque reportó BOOTSTRAP_OK.'
Assert-File $EngineMain 'NSIS/post-install no dejó main.py del motor aunque reportó BOOTSTRAP_OK.'
Assert-File $EnginePackage 'NSIS/post-install perdió el paquete mily_ai aunque reportó BOOTSTRAP_OK.'
Assert-File $ExtensionManifest 'NSIS/post-install no dejó la extensión Chromium aunque reportó BOOTSTRAP_OK.'
Assert-File $Bridge 'NSIS/post-install no dejó el bridge Native Messaging aunque reportó BOOTSTRAP_OK.'
Assert-File $NativeManifest 'NSIS/post-install no generó el manifiesto Native Messaging aunque reportó BOOTSTRAP_OK.'

$runtimeContract = Get-Content $RuntimeManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$requiredModules = @($runtimeContract.requiredModules)
$optionalModules = @($runtimeContract.optionalModules)
foreach ($module in @('fastapi','uvicorn','numpy','faster_whisper','ctranslate2','huggingface_hub','sentencepiece')) {
    if ($requiredModules -notcontains $module) { throw "El runtime manifest no marca '$module' como requisito base." }
}
foreach ($module in @('torch','transformers','moonshine_voice','sherpa_onnx')) {
    if ($requiredModules -contains $module) { throw "El runtime manifest marcó '$module' como requisito bloqueante." }
    if ($optionalModules -notcontains $module) { throw "El runtime manifest no declara '$module' como adapter opcional." }
}

foreach ($key in @(
    'HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.milyvoice.traductor',
    'HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\com.milyvoice.traductor',
    'HKCU:\Software\BraveSoftware\Brave-Browser\NativeMessagingHosts\com.milyvoice.traductor'
)) {
    if (-not (Test-Path $key)) { throw "NSIS no registró Native Messaging: $key" }
    $registered = [string](Get-Item $key).GetValue('')
    if ([System.IO.Path]::GetFullPath($registered) -ne [System.IO.Path]::GetFullPath($NativeManifest)) {
        throw "NSIS registró Native Messaging hacia una ruta incorrecta: $key -> $registered"
    }
}

# Gate crítico: instalación limpia abre primero la app y NO descarga ni activa
# modelos. La selección/descarga queda exclusivamente dentro de Mily Engine Hub.
Assert-FirstRunStartsWithoutModelDownload $DesktopExe $ModelsRoot $CurrentModel $StatusPath

# Gate de actualización: conserva configuración previa y reinstala encima. El CI 2.0
# borraba LOCALAPPDATA antes de cada prueba y nunca cubría este escenario real.
$ConfigPath = Join-Path $AppRoot 'config\config.json'
New-Item -ItemType Directory -Force -Path (Split-Path $ConfigPath -Parent) | Out-Null
@'
{
  "schemaVersion": 1,
  "sourceLanguage": "zh",
  "computeProfile": "auto",
  "persistTranscripts": false
}
'@ | Set-Content -Path $ConfigPath -Encoding UTF8

# Reproduce el fallo observado en Windows real: una versión anterior puede dejar
# el Python privado vivo y un archivo dentro de runtime\python bloqueado. Se usa
# un script temporal y un handshake explícito; Start-Process + Python -c era
# ambiguo al reconstruir argumentos y podía terminar antes de crear el bloqueo.
$FixtureRoot = Join-Path $env:RUNNER_TEMP 'MilyVoiceRuntimeFixture'
$FixtureScript = Join-Path $FixtureRoot 'hold-private-runtime.py'
$FixtureReady = Join-Path $FixtureRoot 'runtime-fixture-ready'
Remove-Item $FixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $FixtureRoot | Out-Null
@'
from __future__ import annotations

import ctypes
import os
import sys
import time
from ctypes import wintypes
from pathlib import Path

lock_path = Path(sys.argv[1])
ready_path = Path(sys.argv[2])
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HANDLE,
]
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

handle = kernel32.CreateFileW(
    str(lock_path),
    0x80000000,
    0,
    None,
    3,
    0x80,
    None,
)
if handle == wintypes.HANDLE(-1).value:
    raise ctypes.WinError(ctypes.get_last_error())

ready_path.write_text(str(os.getpid()), encoding="utf-8")
try:
    time.sleep(600)
finally:
    kernel32.CloseHandle(handle)
'@ | Set-Content -Path $FixtureScript -Encoding UTF8

$fixtureStart = [System.Diagnostics.ProcessStartInfo]::new()
$fixtureStart.FileName = $PrivatePython
$fixtureStart.UseShellExecute = $false
$fixtureStart.CreateNoWindow = $true
$fixtureStart.RedirectStandardOutput = $true
$fixtureStart.RedirectStandardError = $true
[void]$fixtureStart.ArgumentList.Add($FixtureScript)
[void]$fixtureStart.ArgumentList.Add($RuntimeManifest)
[void]$fixtureStart.ArgumentList.Add($FixtureReady)

$lockedRuntime = [System.Diagnostics.Process]::new()
$lockedRuntime.StartInfo = $fixtureStart
if (-not $lockedRuntime.Start()) {
    throw 'No se pudo iniciar el fixture del runtime privado antes de reinstalar.'
}

$fixtureReadyObserved = $false
for ($attempt = 0; $attempt -lt 100; $attempt++) {
    Start-Sleep -Milliseconds 100
    $lockedRuntime.Refresh()
    if ($lockedRuntime.HasExited) {
        $fixtureError = $lockedRuntime.StandardError.ReadToEnd().Trim()
        throw "El fixture del runtime privado terminó con código $($lockedRuntime.ExitCode): $fixtureError"
    }
    if (Test-Path $FixtureReady -PathType Leaf) {
        $fixtureReadyObserved = $true
        break
    }
}
if (-not $fixtureReadyObserved) {
    Stop-Process -Id $lockedRuntime.Id -Force -ErrorAction SilentlyContinue
    throw 'El fixture no confirmó que el runtime privado estuviera bloqueado antes de reinstalar.'
}
$fixturePid = (Get-Content $FixtureReady -Raw -Encoding UTF8).Trim()
if ($fixturePid -ne [string]$lockedRuntime.Id) {
    Stop-Process -Id $lockedRuntime.Id -Force -ErrorAction SilentlyContinue
    throw "El handshake del fixture reportó PID $fixturePid, pero se esperaba $($lockedRuntime.Id)."
}

$installerStoppedRuntime = $false
try {
    Write-Host 'Reinstalando 2.1.0 Beta sobre estado local existente y runtime privado activo...' -ForegroundColor Cyan
    Run-ProcessChecked $Installer.FullName @('/S', "/D=$InstallRoot") 300000
    $installerStoppedRuntime = $lockedRuntime.WaitForExit(5000)
} finally {
    $lockedRuntime.Refresh()
    if (-not $lockedRuntime.HasExited) {
        Stop-Process -Id $lockedRuntime.Id -Force -ErrorAction SilentlyContinue
        $lockedRuntime.WaitForExit(10000) | Out-Null
    }
    Remove-Item $FixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
}

if (-not $installerStoppedRuntime) {
    throw 'La reinstalación no cerró el runtime privado anterior.'
}
Assert-BootstrapReady $StatusPath
Assert-DesktopStartsWithWindow $DesktopExe 'reinstalación sobre estado existente'

Write-Host 'NSIS INSTALLER FLOW OK: PS5.1 + payload + model-pending first-run + zero implicit model downloads + Native Messaging + visible Desktop + locked-runtime reinstall' -ForegroundColor Green
