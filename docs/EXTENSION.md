# Extensión Chromium

La extensión se encuentra en `apps/extension/` y usa Manifest V3.

## Permisos

Solo declara:

- `activeTab`
- `tabCapture`
- `offscreen`
- `storage`
- `notifications`

El host local permitido es `http://127.0.0.1/*`. No existe `<all_urls>`.

## Flujo

```text
Popup → acción del usuario → tabCapture → offscreen document
      → AudioWorklet PCM16 → WebSocket localhost autenticado
      → motor IA → translation.final → content script → Shadow DOM overlay
```

El audio de la pestaña se vuelve a conectar al destino de AudioContext para que la reunión permanezca audible. El motor solo escucha en loopback y exige el token local de emparejamiento.

## Instalar sin tienda

Ejecute `installer/windows/install-extension.ps1` y cargue la carpeta resultante como extensión descomprimida. Para publicar en Chrome Web Store/Edge Add-ons se debe empaquetar `apps/extension` y completar la revisión de tienda; esa publicación no cambia el motor local.
