#!/usr/bin/env python3
"""Guardia estática de permisos/privacidad para la extensión Chromium."""
from pathlib import Path
import json
import re

root = Path(__file__).resolve().parents[1]
ext = root / "apps" / "extension"
manifest = json.loads((ext / "manifest.json").read_text(encoding="utf-8"))
assert manifest["manifest_version"] == 3
assert "<all_urls>" not in json.dumps(manifest)
assert set(manifest["permissions"]) <= {"activeTab", "tabCapture", "offscreen", "storage", "notifications"}
assert manifest["host_permissions"] == ["http://127.0.0.1/*"]
for path in ext.glob("*.js"):
    text = path.read_text(encoding="utf-8")
    assert "https://" not in text, f"Código remoto/no local en {path.name}"
    external_ws = [match for match in re.findall(r"ws://[^'\"`]+", text) if not match.startswith("ws://127.0.0.1")]
    assert not external_ws, f"WebSocket externo en {path.name}: {external_ws}"
print("Extension privacy guard: OK")
