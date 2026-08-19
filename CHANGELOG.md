# Changelog

## [2.0.1] - 2026-08-18

### Corregido
- El gate NSIS ya no se limita a comprobar archivos: instala y arranca el `MilyVoiceTraductor.exe` generado.
- El Desktop instalado debe crear una ventana Windows real antes de aceptar el artefacto.
- El mismo gate repite instalación sobre estado local existente y vuelve a exigir arranque visible.
- Sitio, VERSION, Cargo, Node, Tauri, motor Python, extensión, CI y publicación declaran la misma versión 2.0.1.
- El paquete Python interno deja atrás el `1.0.0rc1` residual.
- La landing deja de publicar textos 2.0 RC y enlaces v2.0.0 obsoletos.
- El workflow de publicación toma únicamente el artefacto del SHA verificado por CI.

### MilyCompute / rendimiento
- CPU INT8 permanece como fallback obligatorio para cualquier PC.
- Perfil Auto prueba CUDA solo cuando CTranslate2 reporta un dispositivo utilizable.
- Si CUDA se detecta pero no inicializa, Faster-Whisper y M2M100 vuelven automáticamente a CPU en perfil Auto.
- Perfil GPU forzado informa errores CUDA explícitos en vez de ocultarlos con fallback.
- Hardware Advisor deja de asumir `cualquier GPU = CUDA` y cruza Runtime Registry con inventario DXGI real.
- Intel/AMD pueden aparecer como candidatos de runtimes alternativos, pero nunca se marcan `ready` sin adapter ejecutable y benchmark real.
- Se conservan los perfiles de CPU débiles, colas acotadas, warm-up y MegaBench P50/P95/RTF.

### Modelos
- Sin cambio de pesos: `Systran/faster-whisper-small` + `facebook/m2m100_418M` CTranslate2 INT8.
- Model Labs Quality/TriCore/Legacy siguen en R&D/Features y no forman parte de esta optimización.
- El benchmark físico específico Intel Core i3 Haswell sigue pendiente y no se sustituye por el runner de GitHub.

### Validación
- Tests de fallback CPU/CUDA del router y proveedores.
- Tests de Hardware Advisor para impedir falsos candidatos CUDA en Intel/AMD.
- Recuperación segura de configuración anterior/corrupta antes del arranque.
- MegaBench con modelos reales.
- `WINDOWS_GUI`, Tauri NSIS, Native Messaging, arranque visible y reinstalación real.

## [2.0.0] - 2026-08-18

### Nota
- Introdujo MilyCompute Foundation, MegaBench y el salto realtime/multimodal.
- La publicación se considera reemplazada por 2.0.1 porque su smoke NSIS verificaba payload/registro pero no arrancaba explícitamente el Desktop instalado, y la web conservó referencias RC/2.0.0 inconsistentes.

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
