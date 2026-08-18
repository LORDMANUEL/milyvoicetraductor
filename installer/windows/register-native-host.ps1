[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BridgePath,
    [Parameter(Mandatory = $true)]
    [string]$ManifestTemplate,
    [Parameter(Mandatory = $true)]
    [string]$ManifestOutput,
    [switch]$Unregister
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$HostName = 'com.milyvoice.traductor'
$AllowedOrigin = 'chrome-extension://edcpjonegaempcifgodcmgejbcpdpddm/'
$RegistryRoots = @(
    "HKCU:\Software\Google\Chrome\NativeMessagingHosts\$HostName",
    "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\$HostName",
    "HKCU:\Software\Chromium\NativeMessagingHosts\$HostName",
    "HKCU:\Software\BraveSoftware\Brave-Browser\NativeMessagingHosts\$HostName"
)

if ($Unregister) {
    foreach ($key in $RegistryRoots) {
        Remove-Item $key -Recurse -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $ManifestOutput -Force -ErrorAction SilentlyContinue
    exit 0
}

$BridgePath = [System.IO.Path]::GetFullPath($BridgePath)
$ManifestTemplate = [System.IO.Path]::GetFullPath($ManifestTemplate)
$ManifestOutput = [System.IO.Path]::GetFullPath($ManifestOutput)
if (-not (Test-Path $BridgePath)) { throw 'No se encontró milyvoice-bridge.exe.' }
if (-not (Test-Path $ManifestTemplate)) { throw 'No se encontró el manifiesto Native Messaging base.' }

$template = Get-Content $ManifestTemplate -Raw -Encoding UTF8 | ConvertFrom-Json
if ($template.name -ne $HostName) { throw 'Nombre de Native Messaging Host inválido.' }
if (@($template.allowed_origins).Count -ne 1 -or $template.allowed_origins[0] -ne $AllowedOrigin) {
    throw 'allowed_origins no coincide con la extensión MilyVoiceTraductor fijada.'
}
if ($template.allowed_origins -contains '*') { throw 'No se permiten wildcards en allowed_origins.' }

$manifestDirectory = Split-Path -Parent $ManifestOutput
New-Item -ItemType Directory -Force -Path $manifestDirectory | Out-Null
$manifest = [ordered]@{
    name = $HostName
    description = [string]$template.description
    path = $BridgePath
    type = 'stdio'
    allowed_origins = @($AllowedOrigin)
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -Path $ManifestOutput -Encoding UTF8

foreach ($key in $RegistryRoots) {
    New-Item -Path $key -Force | Out-Null
    Set-Item -Path $key -Value $ManifestOutput
}

Write-Host 'Native Messaging Host registrado para Chrome/Edge/Chromium/Brave.' -ForegroundColor Green
