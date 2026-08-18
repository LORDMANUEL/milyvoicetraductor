[CmdletBinding()]
param(
    [string]$Executable = "target\release\MilyVoiceTraductor.exe"
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$ExePath = if ([System.IO.Path]::IsPathRooted($Executable)) {
    $Executable
} else {
    Join-Path $Root $Executable
}

if (-not (Test-Path $ExePath -PathType Leaf)) {
    throw "No se encontró el ejecutable Windows Release: $ExePath"
}

$bytes = [System.IO.File]::ReadAllBytes($ExePath)
if ($bytes.Length -lt 256) {
    throw 'El ejecutable es demasiado pequeño para contener un encabezado PE válido.'
}
if ($bytes[0] -ne 0x4D -or $bytes[1] -ne 0x5A) {
    throw 'El ejecutable no contiene una cabecera DOS MZ válida.'
}

$peOffset = [System.BitConverter]::ToInt32($bytes, 0x3C)
if ($peOffset -lt 0 -or ($peOffset + 96) -ge $bytes.Length) {
    throw 'El offset PE del ejecutable es inválido.'
}
if ($bytes[$peOffset] -ne 0x50 -or $bytes[$peOffset + 1] -ne 0x45 -or $bytes[$peOffset + 2] -ne 0 -or $bytes[$peOffset + 3] -ne 0) {
    throw 'El ejecutable no contiene una firma PE válida.'
}

$optionalHeader = $peOffset + 24
$magic = [System.BitConverter]::ToUInt16($bytes, $optionalHeader)
if ($magic -ne 0x10B -and $magic -ne 0x20B) {
    throw ('Formato de Optional Header PE no reconocido: 0x{0:X4}' -f $magic)
}

# IMAGE_OPTIONAL_HEADER32/64 ubica Subsystem a +68 bytes.
$subsystem = [System.BitConverter]::ToUInt16($bytes, $optionalHeader + 68)
$IMAGE_SUBSYSTEM_WINDOWS_GUI = 2
if ($subsystem -ne $IMAGE_SUBSYSTEM_WINDOWS_GUI) {
    throw "MilyVoiceTraductor.exe usa Subsystem=$subsystem. Se esperaba WINDOWS_GUI=2; una build de consola puede abrir la ventana negra reportada por el usuario."
}

Write-Host 'WINDOWS GUI SUBSYSTEM OK: MilyVoiceTraductor.exe no es una aplicación de consola.' -ForegroundColor Green
