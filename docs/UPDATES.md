# Versionado y actualizaciones

## Versiones

El proyecto usa SemVer para desktop/engine/extensión. El candidato incluido en este paquete es `1.0.0-rc.1`.

Los modelos tienen versión independiente dentro de `resources/model-packs.json`.

## Aplicación

Tauri genera el instalador NSIS con `installer/windows/build-release.ps1`. Una release pública debe firmar ejecutables/instaladores y los artefactos de actualización con claves mantenidas **fuera del repositorio**.

No se incluye ninguna clave privada, token de GitHub ni certificado de firma en el ZIP.

## Canal de actualización

`resources/update/channel-template.json` define el contrato de publicación. `scripts/make_release_notes.py` genera un manifiesto de plantilla para la versión actual. En la ronda de GitHub se conectará este contrato con releases firmadas; hasta entonces el chequeo remoto permanece deshabilitado por privacidad y porque no existe un endpoint de producción firmado.

## Modelos

Los modelos se actualizan independientemente de la aplicación. El Model Manager conserva `active` y `previous`, por lo que una actualización de pesos no obliga a cambiar el desktop y puede revertirse.
