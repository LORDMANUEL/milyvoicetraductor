[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Installer = Get-ChildItem (Join-Path $Root 'target\release\bundle\nsis\*-setup.exe') -File | Select-Object -First 1
if (-not $Installer) { throw 'No se encontró el instalador NSIS generado.' }

$FailureRoot = Join-Path $env:RUNNER_TEMP 'MilyVoiceTraductor-NSIS-Bootstrap-Failure'
$InstallRoot = Join-Path $FailureRoot 'install'
$AppRoot = Join-Path $env:LOCALAPPDATA 'MilyVoiceTraductor'

Get-Process -Name 'MilyVoiceTraductor' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Remove-Item $FailureRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $AppRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $AppRoot -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $FailureRoot | Out-Null

# El bootstrap necesita crear LOCALAPPDATA\MilyVoiceTraductor como directorio.
# Un archivo con ese mismo nombre fuerza una falla determinista antes de que el
# runtime pueda considerarse listo y permite probar el camino negativo del NSIS.
Set-Content -Path $AppRoot -Encoding ascii -Value 'blocks-directory-creation'

$process = $null
try {
    $start = [System.Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $Installer.FullName
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    [void]$start.ArgumentList.Add('/S')
    [void]$start.ArgumentList.Add("/D=$InstallRoot")

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $start
    if (-not $process.Start()) {
        throw 'No se pudo iniciar el instalador NSIS para la prueba de fallo.'
    }
    if (-not $process.WaitForExit(300000)) {
        try { $process.Kill($true) } catch {}
        throw 'El instalador NSIS excedió el tiempo permitido en la prueba de fallo.'
    }

    $exitCode = [int]$process.ExitCode
    if ($exitCode -eq 0) {
        throw 'El NSIS devolvió éxito aunque bootstrap debía fallar.'
    }

    Write-Host "NSIS BOOTSTRAP FAILURE GATE OK: ExitCode=$exitCode" -ForegroundColor Green
}
finally {
    if ($process -ne $null) { $process.Dispose() }
    Remove-Item $AppRoot -Force -ErrorAction SilentlyContinue
    Remove-Item $AppRoot -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $FailureRoot -Recurse -Force -ErrorAction SilentlyContinue
}
