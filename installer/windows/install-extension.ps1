[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Target=Join-Path $env:LOCALAPPDATA 'MilyVoiceTraductor\extension'
New-Item -ItemType Directory -Force -Path $Target | Out-Null
Remove-Item (Join-Path $Target '*') -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item (Join-Path $Root 'apps\extension\*') $Target -Recurse -Force
Write-Host "Extensión preparada en: $Target"
Write-Host 'Abre chrome://extensions o edge://extensions, activa Modo desarrollador y usa Cargar descomprimida.'
