[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$FixtureRoot = Join-Path $Root '.build\runtime-import-diagnostics'
$RuntimeSource = Join-Path $FixtureRoot 'runtime-source'
$InstallRoot = Join-Path $FixtureRoot 'install'
$Bootstrap = Join-Path $InstallRoot 'bootstrap'
$AppRoot = Join-Path $FixtureRoot 'localappdata\MilyVoiceTraductor'
$StatusPath = Join-Path $AppRoot 'bootstrap\status.json'
$RuntimeZipSource = Join-Path $Root 'dist\runtime\milyvoice-python-runtime.zip'
$BridgeSource = Join-Path $Root 'target\release\milyvoice-bridge.exe'
$SetupSource = Join-Path $Root 'installer\windows\setup-installed.ps1'
$RegisterSource = Join-Path $Root 'installer\windows\register-native-host.ps1'
$TemplateSource = Join-Path $Root 'installer\windows\native-host-template.json'
$WindowsPowerShell = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'

function Assert-File([string]$Path, [string]$Message) {
    if (-not (Test-Path $Path -PathType Leaf)) { throw $Message }
}

function Get-Sha256Hex([string]$Path) {
    return (Get-FileHash $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

foreach ($required in @($RuntimeZipSource, $BridgeSource, $SetupSource, $RegisterSource, $TemplateSource, $WindowsPowerShell)) {
    Assert-File $required "Falta fixture requerido: $required"
}

Remove-Item $FixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path `
    $RuntimeSource, `
    (Join-Path $Bootstrap 'runtime'), `
    (Join-Path $Bootstrap 'bridge'), `
    (Join-Path $Bootstrap 'ai\mily_ai'), `
    (Join-Path $Bootstrap 'extension') | Out-Null

Expand-Archive -Path $RuntimeZipSource -DestinationPath $RuntimeSource -Force
$manifestPath = Join-Path $RuntimeSource 'runtime-manifest.json'
$pythonPath = Join-Path $RuntimeSource 'python.exe'
Assert-File $manifestPath 'El runtime real no contiene runtime-manifest.json.'
Assert-File $pythonPath 'El runtime real no contiene python.exe.'

$manifest = Get-Content $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$manifest.requiredModules = @('milyvoice_missing_fixture')
$manifest.optionalModules = @()
$manifest | ConvertTo-Json -Depth 8 | Set-Content $manifestPath -Encoding UTF8

$fixtureRuntimeZip = Join-Path $Bootstrap 'runtime\milyvoice-python-runtime.zip'
Compress-Archive -Path (Join-Path $RuntimeSource '*') -DestinationPath $fixtureRuntimeZip -CompressionLevel Optimal
$fixtureHash = Get-Sha256Hex $fixtureRuntimeZip
Set-Content -Path "$fixtureRuntimeZip.sha256" -Encoding ascii -Value "$fixtureHash *milyvoice-python-runtime.zip"

Set-Content -Path (Join-Path $Bootstrap 'ai\main.py') -Encoding UTF8 -Value "print('fixture')"
Set-Content -Path (Join-Path $Bootstrap 'ai\mily_ai\__init__.py') -Encoding UTF8 -Value ""
Set-Content -Path (Join-Path $Bootstrap 'extension\manifest.json') -Encoding UTF8 -Value '{}'
Copy-Item $BridgeSource (Join-Path $Bootstrap 'bridge\milyvoice-bridge.exe') -Force
Copy-Item $SetupSource (Join-Path $Bootstrap 'setup-installed.ps1') -Force
Copy-Item $RegisterSource (Join-Path $Bootstrap 'register-native-host.ps1') -Force
Copy-Item $TemplateSource (Join-Path $Bootstrap 'native-host-template.json') -Force

$setup = Join-Path $Bootstrap 'setup-installed.ps1'
& $WindowsPowerShell `
    -NoProfile `
    -NonInteractive `
    -ExecutionPolicy Bypass `
    -File $setup `
    -InstallRoot $InstallRoot `
    -AppRoot $AppRoot 2>$null | Out-Null
$exitCode = $LASTEXITCODE
if ($exitCode -eq 0) {
    throw 'El fixture de módulo faltante debía fallar en RUNTIME_IMPORT.'
}
Assert-File $StatusPath 'El bootstrap fallido no escribió status.json.'

$status = Get-Content $StatusPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($status.state -ne 'failed') { throw "Estado inesperado: $($status.state)" }
if ($status.code -ne 'RUNTIME_IMPORT_FAILED') { throw "Código inesperado: $($status.code)" }
if ($status.stage -ne 'RUNTIME_IMPORT') { throw "Etapa inesperada: $($status.stage)" }
if ($status.message -notmatch 'milyvoice_missing_fixture') {
    throw "El mensaje no identifica el módulo fallido: $($status.message)"
}

$failures = @($status.runtimeImportFailures)
if ($failures.Count -ne 1) {
    throw "status.json debe incluir exactamente un runtimeImportFailures; obtuvo $($failures.Count)."
}
$failure = $failures[0]
if ($failure.module -ne 'milyvoice_missing_fixture') { throw "Módulo diagnóstico inesperado: $($failure.module)" }
if ([int]$failure.exitCode -eq 0) { throw 'El diagnóstico debe conservar exitCode no-cero.' }
if ([string]::IsNullOrWhiteSpace([string]$failure.summary)) { throw 'El diagnóstico debe conservar un resumen del import fallido.' }
if (([string]$failure.summary).Contains($env:USERPROFILE)) { throw 'El diagnóstico no debe filtrar USERPROFILE.' }
if (([string]$failure.summary).Contains($Root)) { throw 'El diagnóstico no debe filtrar GITHUB_WORKSPACE/ruta del repo.' }

Write-Host 'RUNTIME IMPORT DIAGNOSTICS GATE OK' -ForegroundColor Green
Remove-Item $FixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
