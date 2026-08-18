#!/usr/bin/env python3
"""Guardia estática de permisos, privacidad y auto-descubrimiento Chromium."""
from pathlib import Path
import base64
import hashlib
import json
import re

root = Path(__file__).resolve().parents[1]
ext = root / "apps" / "extension"
manifest = json.loads((ext / "manifest.json").read_text(encoding="utf-8"))
popup = (ext / "popup.html").read_text(encoding="utf-8")
background = (ext / "background.js").read_text(encoding="utf-8")
offscreen = (ext / "offscreen.js").read_text(encoding="utf-8")
worklet = (ext / "audio-worklet.js").read_text(encoding="utf-8")
tts = (ext / "tts.js").read_text(encoding="utf-8")
settings = (root / "apps" / "desktop" / "src" / "pages" / "Settings.svelte").read_text(encoding="utf-8")

EXPECTED_EXTENSION_ID = "edcpjonegaempcifgodcmgejbcpdpddm"
EXPECTED_NATIVE_HOST = "com.milyvoice.traductor"

assert manifest["manifest_version"] == 3
assert "<all_urls>" not in json.dumps(manifest)
assert "nativeMessaging" in manifest["permissions"], "Falta nativeMessaging para autoreconocimiento"
assert set(manifest["permissions"]) <= {
    "activeTab", "tabCapture", "offscreen", "storage", "notifications", "nativeMessaging", "scripting", "tts"
}
assert "scripting" in manifest["permissions"], "La inyección bajo demanda requiere scripting"
assert "tts" in manifest["permissions"], "La voz española del navegador requiere permiso tts local"
assert manifest["host_permissions"] == ["http://127.0.0.1/*"]
assert not manifest.get("content_scripts"), "El overlay no debe inyectarse permanentemente en todas las webs"
public_key = manifest.get("key", "")
assert public_key, "La extensión debe fijar un ID estable para allowed_origins"

# Reproduce el cálculo de ID de Chromium a partir de la clave pública.
digest = hashlib.sha256(base64.b64decode(public_key)).digest()[:16]
alphabet = "abcdefghijklmnop"
derived_id = "".join(alphabet[byte >> 4] + alphabet[byte & 15] for byte in digest)
assert derived_id == EXPECTED_EXTENSION_ID, f"ID de extensión inesperado: {derived_id}"

assert 'id="token"' not in popup, "El usuario no debe pegar tokens"
assert 'id="port"' not in popup, "El usuario no debe configurar puertos"
assert "Puerto local" not in settings, "Desktop no debe pedir el puerto del motor al usuario"
assert "bind:value={draft.enginePort}" not in settings, "El puerto debe administrarse internamente"
assert f"const NATIVE_HOST = '{EXPECTED_NATIVE_HOST}'" in background
assert "connectNative(NATIVE_HOST)" in background, "Falta conexión al host nativo"
assert "MEETING_URL" not in background, "La captura no debe limitarse a Meet/Teams/Zoom"
assert "assertCapturableTab(tab)" in background, "Debe validar páginas protegidas antes de capturar"
assert "Audio del sistema" in background, "El error de tabCapture debe ofrecer fallback del Desktop"
assert "chrome.scripting.executeScript" in background, "El overlay debe inyectarse bajo demanda"
assert "chrome.scripting.insertCSS" in background, "El CSS del overlay debe inyectarse bajo demanda"
assert "ensureOverlay(tab.id)" in background, "START_CAPTURE debe preparar overlay solo en la pestaña elegida"
assert "speakTranslation" in background, "La traducción final debe poder activar TTS local"
assert "tts.started" in offscreen and "tts.finished" in offscreen, "TTS debe avisar al motor para anti-feedback"
assert "chrome.tts.speak" in tts, "La extensión debe usar síntesis local de Chromium/Windows"

# Teams/Meet/Zoom deben conservar el audio audible a la frecuencia nativa del
# dispositivo. Solo la copia para ASR se reduce a 16 kHz dentro del worklet.
assert "new AudioContext({ sampleRate: 16000" not in offscreen, (
    "La reproducción de la pestaña no debe forzarse a 16 kHz; degrada la voz de Teams."
)
assert "TARGET_SAMPLE_RATE = 16000" in worklet, "El worklet debe definir el destino ASR de 16 kHz."
assert "sampleRate / TARGET_SAMPLE_RATE" in worklet, (
    "El worklet debe remuestrear desde la frecuencia nativa del AudioContext hacia 16 kHz."
)

# Consultar el popup debe ser pasivo. Solo START_CAPTURE puede usar `hello`, que
# arranca el motor y solicita una credencial efímera al bridge.
status_block = background.split("if (message?.type === 'GET_BRIDGE_STATUS')", 1)[1].split(
    "if (message?.type === 'START_CAPTURE')", 1
)[0]
assert "requestBridge('status'" in status_block, "GET_BRIDGE_STATUS debe usar status pasivo"
assert "requestBridge('hello'" not in status_block, "Consultar estado no debe arrancar el motor"
start_capture_function = background.split("async function startCapture", 1)[1].split(
    "async function stopCapture", 1
)[0]
assert "requestBridge('hello'" in start_capture_function, "START_CAPTURE debe solicitar sesión efímera"

# El camino caliente negociado debe enviar el ArrayBuffer PCM directamente.
assert "binaryPcm: true" in offscreen, "La extensión debe negociar PCM binario"
assert "websocket.send(event.data)" in offscreen, "El camino caliente debe enviar PCM binario directo"
assert "payload.binaryPcm === true" in offscreen, "No se debe activar binario sin confirmación del motor"
binary_block = offscreen.split("if (binaryPcmActive)", 1)[1].split("websocket.send(JSON.stringify", 1)[0]
assert "arrayBufferToBase64" not in binary_block, "PCM binario no debe pasar por Base64"

for path in ext.glob("*.js"):
    text = path.read_text(encoding="utf-8")
    if path.name != "popup.js":
        assert "https://" not in text, f"Código remoto/no local en {path.name}"
    external_ws = [
        match for match in re.findall(r"ws://[^'\"`]+", text)
        if not match.startswith("ws://127.0.0.1")
    ]
    assert not external_ws, f"WebSocket externo en {path.name}: {external_ws}"

print("Extension privacy/autodiscovery guard: OK")
