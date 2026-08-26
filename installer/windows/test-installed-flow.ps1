[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$FixtureRoot = Join-Path $Root '.build\installed-flow'
$InstallRoot = Join-Path $FixtureRoot 'install'
$FakeLocalAppData = Join-Path $FixtureRoot 'localappdata'
$Bootstrap = Join-Path $InstallRoot 'bootstrap'
$AppRoot = Join-Path $FakeLocalAppData 'MilyVoiceTraductor'
$StatusPath = Join-Path $AppRoot 'bootstrap\status.json'
$OriginalLocalAppData = $env:LOCALAPPDATA
$WindowsPowerShell = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'

function Assert-File([string]$Path, [string]$Message) {
    if (-not (Test-Path $Path -PathType Leaf)) { throw $Message }
}

Assert-File $WindowsPowerShell 'El runner Windows no tiene Windows PowerShell 5.1.'
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
    $SetupScript = Join-Path $Bootstrap 'setup-installed.ps1'
    & $WindowsPowerShell `
        -NoProfile `
        -NonInteractive `
        -ExecutionPolicy Bypass `
        -File $SetupScript `
        -InstallRoot $InstallRoot `
        -AppRoot $AppRoot
    if ($LASTEXITCODE -ne 0) {
        if (Test-Path $StatusPath -PathType Leaf) {
            $failed = Get-Content $StatusPath -Raw -Encoding UTF8 | ConvertFrom-Json
            throw "setup-installed.ps1 (Windows PowerShell 5.1) falló: $($failed.code) / $($failed.message)"
        }
        throw 'setup-installed.ps1 falló en Windows PowerShell 5.1 sin status.json.'
    }

    $Python = Join-Path $AppRoot 'runtime\python\python.exe'
    $EngineMain = Join-Path $AppRoot 'engine\app\main.py'
    $EnginePackage = Join-Path $AppRoot 'engine\app\mily_ai\__init__.py'
    $ExtensionManifest = Join-Path $AppRoot 'extension\manifest.json'
    $Bridge = Join-Path $AppRoot 'bridge\milyvoice-bridge.exe'
    $NativeManifest = Join-Path $AppRoot 'bridge\com.milyvoice.traductor.json'
    $NativeCredential = Join-Path $AppRoot 'config\native-credential.json'

    Assert-File (Join-Path $Bootstrap 'setup-installed.ps1') 'El fixture no replica el bootstrap al lado del ejecutable.'
    Assert-File $Python 'El flujo instalado no dejó python.exe privado.'
    Assert-File $EngineMain 'El flujo instalado no dejó main.py del motor.'
    Assert-File $EnginePackage 'El flujo instalado perdió el paquete mily_ai del motor.'
    Assert-File $ExtensionManifest 'El flujo instalado no dejó la extensión.'
    Assert-File $Bridge 'El flujo instalado no dejó el bridge Native Messaging.'
    Assert-File $NativeManifest 'El flujo instalado no generó el manifiesto Native Messaging.'
    Assert-File $StatusPath 'El flujo instalado no generó status.json.'

    $status = Get-Content $StatusPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($status.state -notin @('model-pending', 'ready')) {
        throw "Estado bootstrap inesperado: $($status.state) / $($status.code)"
    }
    if ($status.code -ne 'BOOTSTRAP_OK') {
        throw "El bootstrap no terminó con BOOTSTRAP_OK: $($status.code) / $($status.message)"
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

    & $Python $EngineMain diagnose `
        --data-dir $AppRoot `
        --config-dir (Join-Path $AppRoot 'config') `
        --cache-dir (Join-Path $AppRoot 'cache') `
        --models-dir (Join-Path $AppRoot 'models') | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'El motor instalado no pasó diagnose.' }

    Remove-Item $NativeCredential -Force -ErrorAction SilentlyContinue
    $Probe = Join-Path $FixtureRoot 'probe_native.py'
    $ProbePort = Join-Path $FixtureRoot 'native-engine-port.txt'
    @'
import asyncio
import json
import struct
import subprocess
import sys
import time
from pathlib import Path

bridge, origin, port_output = sys.argv[1], sys.argv[2], Path(sys.argv[3])
proc = subprocess.Popen(
    [bridge, origin],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)


def exchange(kind: str):
    payload = json.dumps({"protocol": 1, "type": kind}, separators=(",", ":")).encode("utf-8")
    proc.stdin.write(struct.pack("<I", len(payload)) + payload)
    proc.stdin.flush()
    raw_len = proc.stdout.read(4)
    if len(raw_len) != 4:
        raise SystemExit(f"El bridge no devolvió cabecera Native Messaging para {kind}")
    length = struct.unpack("<I", raw_len)[0]
    body = proc.stdout.read(length)
    return json.loads(body.decode("utf-8"))

status = exchange("status")
if status.get("type") != "bridge.ready" or status.get("desktop") != "ready":
    raise SystemExit(f"Respuesta bridge status inesperada: {status}")
if "credential" in status or "expiresAt" in status:
    raise SystemExit("Una consulta status no debe emitir credenciales efímeras")
print("NATIVE_BRIDGE_PASSIVE_STATUS_OK")

hello = exchange("hello")
if hello.get("type") != "bridge.ready" or hello.get("engine") != "ready":
    raise SystemExit(f"Respuesta bridge hello inesperada: {hello}")
credential = hello.get("credential")
port = int(hello.get("port") or 0)
expires_at = int(hello.get("expiresAt") or 0)
if not credential or len(credential) < 32 or not (1024 <= port <= 65535):
    raise SystemExit("hello no devolvió credencial/puerto válidos")
if expires_at <= int(time.time()):
    raise SystemExit("hello devolvió una credencial ya expirada")
port_output.write_text(str(port), encoding="ascii")

async def verify_live_engine():
    try:
        import websockets
    except Exception as exc:
        raise SystemExit(f"El runtime privado no contiene soporte WebSocket: {exc}")
    uri = f"ws://127.0.0.1:{port}/ws?token={credential}"
    async with websockets.connect(uri, origin=origin.rstrip("/"), open_timeout=5, close_timeout=2) as ws:
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        payload = json.loads(raw)
        if payload.get("type") != "engine.ready":
            raise SystemExit(f"El motor real no confirmó engine.ready: {payload}")

asyncio.run(verify_live_engine())
print("NATIVE_BRIDGE_HELLO_WEBSOCKET_OK")

proc.terminate()
proc.wait(timeout=5)
'@ | Set-Content -Path $Probe -Encoding UTF8

    & $Python $Probe $Bridge 'chrome-extension://edcpjonegaempcifgodcmgejbcpdpddm/' $ProbePort
    if ($LASTEXITCODE -ne 0) { throw 'El bridge instalado no completó status + hello + WebSocket real.' }
    Assert-File $NativeCredential 'hello no generó native-credential.json.'
    Assert-File $ProbePort 'El probe no registró el puerto real devuelto por hello.'

    # El engine arrancado por Native Messaging hereda el PID del bridge. Tras cerrar
    # el probe debe apagarse solo y no dejar procesos huérfanos/archivos bloqueados.
    Start-Sleep -Seconds 4
    $port = [int]((Get-Content $ProbePort -Raw -Encoding ASCII).Trim())
    $stillOpen = $false
    try {
        $client = [System.Net.Sockets.TcpClient]::new()
        $async = $client.BeginConnect('127.0.0.1', $port, $null, $null)
        if ($async.AsyncWaitHandle.WaitOne(600)) {
            $client.EndConnect($async)
            $stillOpen = $client.Connected
        }
        $client.Dispose()
    } catch {
        $stillOpen = $false
    }
    if ($stillOpen) {
        throw 'El motor iniciado por Native Messaging quedó huérfano después de cerrar el bridge.'
    }

    Write-Host 'INSTALLED FLOW + EXTENSION BRIDGE + WINDOWS POWERSHELL 5.1 OK' -ForegroundColor Green
}
finally {
    try {
        & (Join-Path $Bootstrap 'register-native-host.ps1') `
            -BridgePath (Join-Path $AppRoot 'bridge\milyvoice-bridge.exe') `
            -ManifestTemplate (Join-Path $Bootstrap 'native-host-template.json') `
            -ManifestOutput (Join-Path $AppRoot 'bridge\com.milyvoice.traductor.json') `
            -Unregister | Out-Null
    } catch {}
    $env:LOCALAPPDATA = $OriginalLocalAppData
    Remove-Item $FixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
}
