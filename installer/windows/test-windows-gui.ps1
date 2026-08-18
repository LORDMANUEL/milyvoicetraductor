[CmdletBinding()]
param(
    [string]$Executable = "target\release\MilyVoiceTraductor.exe",
    [string]$BridgeExecutable = "target\release\milyvoice-bridge.exe"
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$IMAGE_SUBSYSTEM_WINDOWS_GUI = 2

function Resolve-RepoPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }
    return (Join-Path $Root $Path)
}

function Get-PeSubsystem {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path $Path -PathType Leaf)) {
        throw "No se encontró el ejecutable Windows Release: $Path"
    }

    $bytes = [System.IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -lt 256) {
        throw "El ejecutable es demasiado pequeño para contener un encabezado PE válido: $Path"
    }
    if ($bytes[0] -ne 0x4D -or $bytes[1] -ne 0x5A) {
        throw "El ejecutable no contiene una cabecera DOS MZ válida: $Path"
    }

    $peOffset = [System.BitConverter]::ToInt32($bytes, 0x3C)
    if ($peOffset -lt 0 -or ($peOffset + 96) -ge $bytes.Length) {
        throw "El offset PE del ejecutable es inválido: $Path"
    }
    if ($bytes[$peOffset] -ne 0x50 -or $bytes[$peOffset + 1] -ne 0x45 -or $bytes[$peOffset + 2] -ne 0 -or $bytes[$peOffset + 3] -ne 0) {
        throw "El ejecutable no contiene una firma PE válida: $Path"
    }

    $optionalHeader = $peOffset + 24
    $magic = [System.BitConverter]::ToUInt16($bytes, $optionalHeader)
    if ($magic -ne 0x10B -and $magic -ne 0x20B) {
        throw ('Formato de Optional Header PE no reconocido en {0}: 0x{1:X4}' -f $Path, $magic)
    }

    # IMAGE_OPTIONAL_HEADER32/64 ubica Subsystem a +68 bytes.
    return [System.BitConverter]::ToUInt16($bytes, $optionalHeader + 68)
}

function Assert-WindowsGuiSubsystem {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $subsystem = Get-PeSubsystem -Path $Path
    if ($subsystem -ne $IMAGE_SUBSYSTEM_WINDOWS_GUI) {
        throw "$Label usa Subsystem=$subsystem. Se esperaba WINDOWS_GUI=2; una build de consola puede abrir la ventana negra reportada por el usuario."
    }
    Write-Host "WINDOWS GUI SUBSYSTEM OK: $Label" -ForegroundColor Green
}

$ExePath = Resolve-RepoPath -Path $Executable
$BridgePath = Resolve-RepoPath -Path $BridgeExecutable
Assert-WindowsGuiSubsystem -Path $ExePath -Label 'MilyVoiceTraductor.exe'
Assert-WindowsGuiSubsystem -Path $BridgePath -Label 'milyvoice-bridge.exe'

# La reparación invoca PowerShell desde el Desktop. El proceso hijo debe crearse
# sin consola para evitar el flash de cmd/PowerShell durante reparar/onboarding.
$RepairSource = Join-Path $Root 'apps\desktop\src-tauri\src\repair.rs'
$repairText = Get-Content -Raw -Path $RepairSource
if ($repairText -notmatch 'CREATE_NO_WINDOW' -or $repairText -notmatch 'creation_flags\(CREATE_NO_WINDOW\)') {
    throw 'repair.rs no aplica CREATE_NO_WINDOW al PowerShell de reparación.'
}

Write-Host 'WINDOWS NO-CONSOLE POLICY OK: Desktop, bridge y reparación están protegidos.' -ForegroundColor Green
