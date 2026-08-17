[CmdletBinding()]
param([switch]$SkipRuntimeSetup)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Push-Location $Root
try {
    if (Test-Path 'package-lock.json') { npm ci } else { npm install --no-audit --no-fund }
    npm run typecheck
    npm test
    npm run build
    cargo test --workspace
    cargo clippy --workspace --all-targets -- -D warnings
    npm run tauri -- build
    if (-not $SkipRuntimeSetup) {
        Write-Host 'El instalador Tauri se generó. El runtime IA se prepara en el primer equipo con installer/windows/setup-source.ps1.' -ForegroundColor Green
    }
} finally { Pop-Location }
