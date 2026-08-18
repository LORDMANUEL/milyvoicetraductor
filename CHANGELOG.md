# Changelog

## [1.0.5] - 2026-08-18

### Corregido
- Versionado coherente en Desktop, Rust, Tauri, motor Python, extensión Chromium, CI y publicación.
- El instalador/optimizador de modelos ya no abre una consola negra en Windows.
- La preparación del modelo no depende de mantener abierta una ventana externa.
- La pantalla de primera preparación distingue descarga de Whisper, descarga de M2M100, conversión INT8, verificación y estado listo.
- El instalador NSIS incluye el runtime privado y usa el layout `bootstrap/` correcto.
- Verificación SHA-256 del runtime compatible con el contexto real del instalador Windows.
- Nombre del binario Windows fijado a `MilyVoiceTraductor.exe`.

### Modelos
- Perfil recomendado `realtime-m2m100`: Systran/faster-whisper-small + facebook/m2m100_418M.
- Los pesos se descargan desde Hugging Face mediante revisiones fijadas por commit.
- M2M100 se convierte localmente a CTranslate2 INT8 una vez para reducir memoria y latencia de ejecución.
- El progreso queda registrado en `models/operation.json` para que la UI pueda mostrar la fase real.

### Calidad
- Gate de consistencia de versión 1.0.5.
- Tests Python, TypeScript/Vitest, Rust workspace, Clippy estricto y Release builds Linux/Windows.
- Prueba del instalador NSIS generado sobre Windows antes de publicar artefactos.

## [1.0.0-rc.1] - 2026-08-17

### Añadido
- Motor IA local Python con protocolo WebSocket v1 autenticado.
- ASR local mediante faster-whisper con CPU int8 y CUDA opcional.
- Traducción local intercambiable Qwen/NLLB.
- Extensión Chromium Manifest V3 con tabCapture, Offscreen y AudioWorklet.
- Overlay de subtítulos inglés/chino → español.
- Model Manager con revisiones fijadas por commit, staging, activación atómica, SHA-256, verificación, rollback y eliminación segura.
- Sesiones opt-in con exportación TXT/SRT.
- Servicios Rust para motor, modelos y sesiones.
- Instalación de runtime desde fuente, build de sidecar y build Tauri/NSIS.
- Contrato de versionado/release y documentación completa.
- Verificación offline integral y empaquetado limpio de fuente/extensión.

### Privacidad
- Motor limitado a `127.0.0.1`.
- Token de emparejamiento local.
- Sin telemetría.
- Sin persistencia de transcripciones por defecto.
- Pesos, secretos y claves privadas excluidos del paquete fuente.

## [0.1.0] - 2026-08-17

### Añadido
- Fundación Tauri 2 + Rust + Svelte/TypeScript.
- Configuración, SQLite, logs, caché, diagnóstico y landing inicial.
