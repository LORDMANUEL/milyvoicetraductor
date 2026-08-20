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

    $expanded = Join-Path $Root '.build\bootstrap-runtime-contract'
    Remove-Item $expanded -Recurse -Force -ErrorAction SilentlyContinue
    try {
        Expand-Archive -Path $runtimeZip -DestinationPath $expanded -Force
        $manifestPath = Join-Path $expanded 'runtime-manifest.json'
        if (-not (Test-Path $manifestPath -PathType Leaf)) { throw 'El runtime privado no contiene runtime-manifest.json.' }
        $manifest = Get-Content $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $crtEntries = @($manifest.appLocalVisualCppRuntime)
        if ($crtEntries.Count -lt 4) { throw 'El runtime privado no declara el Visual C++ Runtime app-local completo.' }

        $requiredCrt = @('concrt140.dll', 'msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll')
        foreach ($dllName in $requiredCrt) {
            $entry = @($crtEntries | Where-Object { ([string]$_.file).ToLowerInvariant() -eq $dllName }) | Select-Object -First 1
            if ($null -eq $entry) { throw "Falta en manifest el Visual C++ Runtime app-local: $dllName" }
            $dllPath = Join-Path $expanded $dllName
            if (-not (Test-Path $dllPath -PathType Leaf)) { throw "Falta en runtime el Visual C++ Runtime app-local: $dllName" }
            $declaredHash = ([string]$entry.sha256).Trim().ToLowerInvariant()
            if ($declaredHash -notmatch '^[0-9a-f]{64}$') { throw "Hash inválido para $dllName en runtime-manifest.json." }
            if ((Get-Sha256Hex $dllPath) -ne $declaredHash) { throw "Hash app-local no coincide para $dllName." }
        }
    } finally {
        Remove-Item $expanded -Recurse -Force -ErrorAction SilentlyContinue
    }

    & (Join-Path $Root 'installer\windows\test-runtime-import-diagnostics.ps1')
    if ($LASTEXITCODE -ne 0) {
        throw 'Falló el gate de diagnóstico de imports del runtime privado.'
    }
}

Write-Host 'BOOTSTRAP POLICY OK' -ForegroundColor Green
