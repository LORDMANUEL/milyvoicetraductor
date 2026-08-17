# Evidencia de verificación local — 2026-08-17

## Ejecutado en este entorno

- `python3 scripts/verify_source.py` → **OK**.
- Motor Python: **14/14 tests** con `unittest` → **OK**.
- Contrato HTTP/WebSocket del motor mediante FastAPI TestClient → **OK**.
- Guardia de privacidad de extensión Chromium → **OK**.
- Smoke test de landing → **OK**.
- Escaneo de privacidad/secretos del árbol → **OK**.
- `node --check` sobre todos los JavaScript de la extensión → **OK**.
- JSON/catálogos/versiones/model revisions sincronizados → **OK**.
- Guardias de archivos grandes, secretos y cadenas Rust cortadas → **OK**.

## No ejecutado en este host

Este entorno no dispone de `cargo`/`rustc`, y la instalación npm completa no está disponible de forma confiable. Por ello **no se afirma compilación local de Rust/Tauri/Svelte para las fases nuevas**. Los scripts de CI/build están incluidos para ejecutar esa validación después, cuando se suba el ZIP a GitHub o se abra en una estación Windows de desarrollo.

La Fase 1 original sí había sido compilada previamente en GitHub Actions; este documento no reutiliza esa evidencia para afirmar que las fases nuevas compilan: deberán pasar nuevamente sobre el árbol final.

## Modelos pesados

Los pesos de IA no forman parte del ZIP. El Model Manager descarga las revisiones exactas declaradas en `resources/model-packs.json` y crea un manifiesto SHA-256 local tras completar el staging. Las pruebas unitarias del Model Manager simulan descarga, activación y rollback sin consumir varios GB.
