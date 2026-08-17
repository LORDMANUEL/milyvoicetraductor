[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$BuildRoot=Join-Path $Root '.build\ai-sidecar'
$Venv=Join-Path $BuildRoot 'venv'
$Output=Join-Path $Root 'dist\sidecar'
New-Item -ItemType Directory -Force -Path $BuildRoot,$Output | Out-Null

$Py=$null
try { & py -3.13 -c 'import sys; assert sys.version_info[:2]==(3,13)' 2>$null; if($LASTEXITCODE -eq 0){$Py=@('py','-3.13')} } catch {}
if(-not $Py){ throw 'Se requiere Python 3.13 para construir el sidecar.' }
if(-not (Test-Path (Join-Path $Venv 'Scripts\python.exe'))) { & $Py[0] $Py[1] -m venv $Venv }
$Python=Join-Path $Venv 'Scripts\python.exe'
& $Python -m pip install --disable-pip-version-check --upgrade pip
& $Python -m pip install --disable-pip-version-check "$Root\services\ai[build]"
Push-Location (Join-Path $Root 'services\ai')
try {
    & $Python -m nuitka --onefile --assume-yes-for-downloads --include-package-data=mily_ai --output-dir=$Output --output-filename=mily-ai-engine.exe main.py
    if($LASTEXITCODE -ne 0){ throw 'Nuitka no pudo construir el sidecar.' }
} finally { Pop-Location }
Write-Host "Sidecar creado en $Output\mily-ai-engine.exe" -ForegroundColor Green
