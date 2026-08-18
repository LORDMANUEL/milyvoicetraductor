[CmdletBinding()]
param([switch]$RequireRuntime)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$SetupPath = Join-Path $Root 'installer\windows\setup-installed.ps1'
$RegisterPath = Join-Path $Root 'installer\windows\register-native-host.ps1'
$TemplatePath = Join-Path $Root 'installer\windows\native-host-template.json'

foreach ($script in @($SetupPath, $RegisterPath)) {
    $tokens = $null
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile($script, [ref]$tokens, [ref]$errors) | Out-Null
    if ($errors.Count -gt 0) { throw "PowerShell inválido: $script :: $($errors[0].Message)" }
}

$setup = Get-Content $SetupPath -Raw -Encoding UTF8
$prohibited = @('winget install', '-m venv', '-m pip install', 'models `')
foreach ($pattern in $prohibited) {
    if ($setup.Contains($pattern)) { throw "El instalador normal todavía contiene una dependencia online prohibida: $pattern" }
}

$template = Get-Content $TemplatePath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($template.name -ne 'com.milyvoice.traductor') { throw 'Host Native Messaging inesperado.' }
if (@($template.allowed_origins).Count -ne 1) { throw 'allowed_origins debe contener exactamente una extensión.' }
if ($template.allowed_origins[0] -ne 'chrome-extension://edcpjonegaempcifgodcmgejbcpdpddm/') {
    throw 'El ID permitido no coincide con el ID fijado de la extensión.'
}

if ($RequireRuntime) {
    $runtimeZip = Join-Path $Root 'dist\runtime\milyvoice-python-runtime.zip'
    $hashPath = "$runtimeZip.sha256"
    if (-not (Test-Path $runtimeZip) -or -not (Test-Path $hashPath)) { throw 'Falta el runtime privado preconstruido.' }
    $expected = ((Get-Content $hashPath -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
    $actual = (Get-FileHash $runtimeZip -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($expected -ne $actual) { throw 'El runtime privado no coincide con su SHA-256.' }
}

Write-Host 'BOOTSTRAP POLICY OK' -ForegroundColor Green
