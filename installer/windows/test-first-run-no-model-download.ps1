[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Installer = Get-ChildItem (Join-Path $Root 'target\release\bundle\nsis\*-setup.exe') -File | Select-Object -First 1
if (-not $Installer) { throw 'No se encontró el instalador NSIS generado.' }

$InstallRoot = Join-Path $env:RUNNER_TEMP 'MilyVoiceTraductor-FirstRun-NoModel'
$AppRoot = Join-Path $env:LOCALAPPDATA 'MilyVoiceTraductor'
$StatusPath = Join-Path $AppRoot 'bootstrap\status.json'
$ModelsRoot = Join-Path $AppRoot 'models'
$CurrentModel = Join-Path $ModelsRoot 'current.json'

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

function Get-ModelSnapshot([string]$Path) {
    if (-not (Test-Path $Path -PathType Container)) { return @() }
    return @(
        Get-ChildItem $Path -Recurse -File -Force -ErrorAction SilentlyContinue |
            Sort-Object FullName |
            ForEach-Object {
                $relative = $_.FullName.Substring($Path.Length).TrimStart('\')
                "$relative|$($_.Length)|$($_.LastWriteTimeUtc.Ticks)"
            }
    )
}

function Assert-FirstRunStartsWithoutModelDownload([string]$DesktopExe) {
    if (-not (Test-Path $StatusPath -PathType Leaf)) {
        throw 'El instalador no generó bootstrap/status.json.'
    }
    $status = Get-Content $StatusPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($status.state -ne 'model-pending') {
        throw "Primer arranque limpio esperaba model-pending, recibió $($status.state) / $($status.code)."
    }
    if (Test-Path $CurrentModel -PathType Leaf) {
        throw 'Una instalación limpia ya tiene current.json antes de que el usuario elija un modelo.'
    }

    $before = @(Get-ModelSnapshot $ModelsRoot)
    $process = Start-Process -FilePath $DesktopExe -PassThru
    try {
        $windowReady = $false
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            Start-Sleep -Milliseconds 500
            if ($process.HasExited) {
                throw "MilyVoiceTraductor.exe terminó durante el primer arranque con código $($process.ExitCode)."
            }
            $process.Refresh()
            if ($process.MainWindowHandle -ne 0) {
                $windowReady = $true
                break
            }
        }
        if (-not $windowReady) {
            throw 'El EXE instalado no creó una ventana visible en el primer arranque.'
        }

        # Da tiempo suficiente para detectar el antiguo onMount -> prepareModel().
        Start-Sleep -Seconds 5
        $process.Refresh()
        if ($process.HasExited) {
            throw "MilyVoiceTraductor.exe terminó después de abrirse con código $($process.ExitCode)."
        }
        if (Test-Path $CurrentModel -PathType Leaf) {
            throw 'El primer arranque activó un modelo sin intervención del usuario (current.json).'
        }

        $after = @(Get-ModelSnapshot $ModelsRoot)
        $diff = @(Compare-Object -ReferenceObject $before -DifferenceObject $after)
        if ($diff.Count -gt 0) {
            $details = ($diff | ForEach-Object { "$($_.SideIndicator) $($_.InputObject)" }) -join '; '
            throw "Se detectó descarga o preparación implícita de modelos durante el primer arranque: $details"
        }

        Write-Host "FIRST RUN NO MODEL DOWNLOAD OK: PID=$($process.Id) HWND=$($process.MainWindowHandle)" -ForegroundColor Green
    }
    finally {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            $process.WaitForExit(10000) | Out-Null
        }
    }
}

Get-Process -Name 'MilyVoiceTraductor' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Remove-Item $InstallRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $AppRoot -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Instalando NSIS para first-run sin modelos: $($Installer.FullName)" -ForegroundColor Cyan
Run-ProcessChecked $Installer.FullName @('/S', "/D=$InstallRoot") 300000

$DesktopExe = Join-Path $InstallRoot 'MilyVoiceTraductor.exe'
if (-not (Test-Path $DesktopExe -PathType Leaf)) {
    throw 'NSIS no dejó MilyVoiceTraductor.exe para el gate de primer arranque.'
}

Assert-FirstRunStartsWithoutModelDownload $DesktopExe
