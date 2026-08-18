[CmdletBinding()]
param([switch]$RequireRuntime)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$SetupPath = Join-Path $Root 'installer\windows\setup-installed.ps1'
$RegisterPath = Join-Path $Root 'installer\windows\register-native-host.ps1'
$TemplatePath = Join-Path $Root 'installer\windows\native-host-template.json'

function Get-Sha256Hex([string]$Path) {
    $stream = $null
    $sha = $null
    try {
        $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
        $sha = [System.Security.Cryptography.SHA256]::Create()
        $bytes = $sha.ComputeHash($stream)
        return ([System.BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
    } finally {
        if ($sha -ne $null) { $sha.Dispose() }
        if ($stream -ne $null) { $stream.Dispose() }
    }
}

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
if ($setup.Contains('Get-FileHash $RuntimeZip') -or $setup.Contains('Get-FileHash $nextPython')) {
    throw 'El bootstrap instalado no debe depender de Get-FileHash para verificar el runtime.'
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
    $hashText = [System.IO.File]::ReadAllText($hashPath).Trim()
    $expected = ($hashText -split '\s+')[0].Trim().ToLowerInvariant()
    if ($expected -notmatch '^[0-9a-f]{64}$') { throw 'El SHA-256 del runtime privado tiene formato inválido.' }
    $actual = Get-Sha256Hex $runtimeZip
    if ($expected -ne $actual) { throw 'El runtime privado no coincide con su SHA-256.' }
}

Write-Host 'BOOTSTRAP POLICY OK' -ForegroundColor Green
