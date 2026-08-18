[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$FixtureRoot = Join-Path $Root '.build\installed-flow'
$InstallRoot = Join-Path $FixtureRoot 'install'
$FakeLocalAppData = Join-Path $FixtureRoot 'localappdata'
$Bootstrap = Join-Path $InstallRoot 'resources\bootstrap'
$OriginalLocalAppData = $env:LOCALAPPDATA

function Assert-File([string]$Path, [string]$Message) {
    if (-not (Test-Path $Path -PathType Leaf)) { throw $Message }
}

function Assert-Directory([string]$Path, [string]$Message) {
    if (-not (Test-Path $Path -PathType Container)) { throw $Message }
}

Remove-Item $FixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path `
    $Bootstrap, `
    (Join-Path $Bootstrap 'runtime'), `
    (Join-Path $Bootstrap 'bridge'), `
    $FakeLocalAppData | Out-Null

Copy-Item (Join-Path $Root 'services\ai') (Join-Path $Bootstrap 'ai') -Recurse -Force
Copy-Item (Join-Path $Root 'apps\extension') (Join-Path $Bootstrap 'extension') -Recurse -Force
Copy-Item (Join-Path $Root 'dist\runtime\milyvoice-python-runtime.zip') (Join-Path $Bootstrap 'runtime\milyvoice-python-runtime.zip') -Force
Copy-Item (Join-Path $Root 'dist\runtime\milyvoice-python-runtime.zip.sha256') (Join-Path $Bootstrap 'runtime\milyvoice-python-runtime.zip.sha256') -Force
Copy-Item (Join-Path $Root 'target\release\milyvoice-bridge.exe') (Join-Path $Bootstrap 'bridge\milyvoice-bridge.exe') -Force
Copy-Item (Join-Path $Root 'installer\windows\setup-installed.ps1') (Join-Path $Bootstrap 'setup-installed.ps1') -Force
Copy-Item (Join-Path $Root 'installer\windows\register-native-host.ps1') (Join-Path $Bootstrap 'register-native-host.ps1') -Force
Copy-Item (Join-Path $Root 'installer\windows\native-host-template.json') (Join-Path $Bootstrap 'native-host-template.json') -Force

try {
    $env:LOCALAPPDATA = $FakeLocalAppData
    & (Join-Path $Bootstrap 'setup-installed.ps1') -InstallRoot $InstallRoot
    if ($LASTEXITCODE -ne 0) { throw 'setup-installed.ps1 devolvió error.' }

    $AppRoot = Join-Path $FakeLocalAppData 'MilyVoiceTraductor'
    $Python = Join-Path $AppRoot 'runtime\python\python.exe'
    $EngineMain = Join-Path $AppRoot 'engine\app\main.py'
    $ExtensionManifest = Join-Path $AppRoot 'extension\manifest.json'
    $Bridge = Join-Path $AppRoot 'bridge\milyvoice-bridge.exe'
    $NativeManifest = Join-Path $AppRoot 'bridge\com.milyvoice.traductor.json'
    $StatusPath = Join-Path $AppRoot 'bootstrap\status.json'
    $NativeCredential = Join-Path $AppRoot 'config\native-credential.json'

    Assert-File $Python 'El flujo instalado no dejó python.exe privado.'
    Assert-File $EngineMain 'El flujo instalado no dejó el motor Python.'
    Assert-File $ExtensionManifest 'El flujo instalado no dejó la extensión.'
    Assert-File $Bridge 'El flujo instalado no dejó el bridge Native Messaging.'
    Assert-File $NativeManifest 'El flujo instalado no generó el manifiesto Native Messaging.'
    Assert-File $StatusPath 'El flujo instalado no generó status.json.'

    $status = Get-Content $StatusPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($status.state -notin @('model-pending', 'ready')) {
        throw "Estado bootstrap inesperado: $($status.state) / $($status.code)"
    }

    foreach ($key in @(
        'HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.milyvoice.traductor',
        'HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\com.milyvoice.traductor',
        'HKCU:\Software\BraveSoftware\Brave-Browser\NativeMessagingHosts\com.milyvoice.traductor'
    )) {
        if (-not (Test-Path $key)) { throw "No se registró Native Messaging: $key" }
        $registered = [string](Get-Item $key).GetValue('')
        if ([System.IO.Path]::GetFullPath($registered) -ne [System.IO.Path]::GetFullPath($NativeManifest)) {
            throw "Native Messaging apunta a un manifiesto incorrecto: $key"
        }
    }

    # Ejecuta el Python que irá en el equipo del usuario, no el Python del runner.
    & $Python $EngineMain diagnose `
        --data-dir $AppRoot `
        --config-dir (Join-Path $AppRoot 'config') `
        --cache-dir (Join-Path $AppRoot 'cache') `
        --models-dir (Join-Path $AppRoot 'models') | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'El motor instalado no pasó diagnose.' }

    # Prueba el framing Native Messaging contra el binario real instalado. Una consulta
    # `status` debe ser completamente pasiva: nunca devuelve ni escribe credenciales.
    Remove-Item $NativeCredential -Force -ErrorAction SilentlyContinue
    $Probe = Join-Path $FixtureRoot 'probe_native.py'
    @'
import json
import struct
import subprocess
import sys

bridge, origin = sys.argv[1], sys.argv[2]
proc = subprocess.Popen([bridge, origin], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
payload = json.dumps({"protocol": 1, "type": "status"}, separators=(",", ":")).encode("utf-8")
proc.stdin.write(struct.pack("<I", len(payload)) + payload)
proc.stdin.flush()
raw_len = proc.stdout.read(4)
if len(raw_len) != 4:
    raise SystemExit("El bridge no devolvió cabecera Native Messaging")
length = struct.unpack("<I", raw_len)[0]
body = proc.stdout.read(length)
reply = json.loads(body.decode("utf-8"))
if reply.get("type") != "bridge.ready" or reply.get("desktop") != "ready":
    raise SystemExit(f"Respuesta bridge inesperada: {reply}")
if "credential" in reply or "expiresAt" in reply:
    raise SystemExit("Una consulta status no debe emitir credenciales efímeras")
proc.terminate()
proc.wait(timeout=5)
print("NATIVE_BRIDGE_PASSIVE_STATUS_OK")
'@ | Set-Content -Path $Probe -Encoding UTF8

    & python $Probe $Bridge 'chrome-extension://edcpjonegaempcifgodcmgejbcpdpddm/'
    if ($LASTEXITCODE -ne 0) { throw 'El bridge instalado no respondió correctamente a Native Messaging.' }
    if (Test-Path $NativeCredential) {
        throw 'La consulta status escribió native-credential.json sin iniciar captura.'
    }

    Write-Host 'INSTALLED FLOW OK' -ForegroundColor Green
}
finally {
    try {
        & (Join-Path $Bootstrap 'register-native-host.ps1') `
            -BridgePath (Join-Path $FakeLocalAppData 'MilyVoiceTraductor\bridge\milyvoice-bridge.exe') `
            -ManifestTemplate (Join-Path $Bootstrap 'native-host-template.json') `
            -ManifestOutput (Join-Path $FakeLocalAppData 'MilyVoiceTraductor\bridge\com.milyvoice.traductor.json') `
            -Unregister | Out-Null
    } catch {}
    $env:LOCALAPPDATA = $OriginalLocalAppData
    Remove-Item $FixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
}
