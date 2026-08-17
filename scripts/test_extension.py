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

EXPECTED_EXTENSION_ID = "edcpjonegaempcifgodcmgejbcpdpddm"
EXPECTED_NATIVE_HOST = "com.milyvoice.traductor"

assert manifest["manifest_version"] == 3
assert "<all_urls>" not in json.dumps(manifest)
assert "nativeMessaging" in manifest["permissions"], "Falta nativeMessaging para autoreconocimiento"
assert set(manifest["permissions"]) <= {
    "activeTab", "tabCapture", "offscreen", "storage", "notifications", "nativeMessaging"
}
assert manifest["host_permissions"] == ["http://127.0.0.1/*"]
public_key = manifest.get("key", "")
assert public_key, "La extensión debe fijar un ID estable para allowed_origins"

# Reproduce el cálculo de ID de Chromium a partir de la clave pública.
digest = hashlib.sha256(base64.b64decode(public_key)).digest()[:16]
alphabet = "abcdefghijklmnop"
derived_id = "".join(alphabet[byte >> 4] + alphabet[byte & 15] for byte in digest)
assert derived_id == EXPECTED_EXTENSION_ID, f"ID de extensión inesperado: {derived_id}"

assert 'id="token"' not in popup, "El usuario no debe pegar tokens"
assert 'id="port"' not in popup, "El usuario no debe configurar puertos"
assert f"const NATIVE_HOST = '{EXPECTED_NATIVE_HOST}'" in background
assert "connectNative(NATIVE_HOST)" in background, "Falta conexión al host nativo"

for path in ext.glob("*.js"):
    text = path.read_text(encoding="utf-8")
    # El único https permitido en JS es el link visible de descarga del producto.
    if path.name != "popup.js":
        assert "https://" not in text, f"Código remoto/no local en {path.name}"
    external_ws = [
        match for match in re.findall(r"ws://[^'\"`]+", text)
        if not match.startswith("ws://127.0.0.1")
    ]
    assert not external_ws, f"WebSocket externo en {path.name}: {external_ws}"

print("Extension privacy/autodiscovery guard: OK")
