# Changelog

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
