#!/usr/bin/env python3
"""Guardia estática de permisos, privacidad y auto-descubrimiento Chromium."""
from pathlib import Path
import json
import re

root = Path(__file__).resolve().parents[1]
ext = root / "apps" / "extension"
manifest = json.loads((ext / "manifest.json").read_text(encoding="utf-8"))
popup = (ext / "popup.html").read_text(encoding="utf-8")
background = (ext / "background.js").read_text(encoding="utf-8")

assert manifest["manifest_version"] == 3
assert "<all_urls>" not in json.dumps(manifest)
assert "nativeMessaging" in manifest["permissions"], "Falta nativeMessaging para autoreconocimiento"
assert set(manifest["permissions"]) <= {
    "activeTab", "tabCapture", "offscreen", "storage", "notifications", "nativeMessaging"
}
assert manifest["host_permissions"] == ["http://127.0.0.1/*"]
assert manifest.get("key"), "La extensión debe fijar un ID estable para allowed_origins"
assert 'id="token"' not in popup, "El usuario no debe pegar tokens"
assert 'id="port"' not in popup, "El usuario no debe configurar puertos"
assert 'connectNative("com.milyvoice.traductor")' in background, "Falta conexión al host nativo"

for path in ext.glob("*.js"):
    text = path.read_text(encoding="utf-8")
    assert "https://" not in text, f"Código remoto/no local en {path.name}"
    external_ws = [
        match for match in re.findall(r"ws://[^'\"`]+", text)
        if not match.startswith("ws://127.0.0.1")
    ]
    assert not external_ws, f"WebSocket externo en {path.name}: {external_ws}"

print("Extension privacy/autodiscovery guard: OK")
