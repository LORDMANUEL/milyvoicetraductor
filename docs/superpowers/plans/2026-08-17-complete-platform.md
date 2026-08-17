# MilyVoiceTraductor Complete Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Completar la plataforma local MilyVoiceTraductor con motor IA, extensión Chromium, gestión de modelos, sesiones/exportación, empaquetado, actualización y pruebas sin exponer datos de reuniones.

**Architecture:** Tauri/Rust conserva control del escritorio, persistencia y procesos. Un sidecar Python aislado ejecuta ASR/traducción y expone un protocolo WebSocket local autenticado. La extensión Chromium captura solo la pestaña elegida y presenta subtítulos; modelos, motor y aplicación tienen ciclos de versión independientes.

**Tech Stack:** Tauri 2, Rust 2024, Svelte 5, TypeScript, Python 3.13, FastAPI/WebSocket, faster-whisper, Transformers/NLLB, SQLite, Manifest V3.

## Global Constraints

- Privacidad por defecto; sin telemetría.
- Ningún audio o texto sale del equipo salvo descarga explícita de modelos/actualizaciones.
- Logs sanitizados; nunca registrar audio, transcripciones, tokens o rutas personales completas.
- CPU-first; GPU opcional.
- Los pesos de modelos no se versionan ni se incluyen en el ZIP fuente.
- Las claves privadas de firma no se versionan.
- Código modular, clases/traits donde aporten contratos y estado; funciones puras donde simplifiquen.
- Estados honestos: un componente ausente se muestra como no instalado.
- Los tests de núcleo no requieren descargar modelos pesados.

---

### Task 1: Protocolo y motor IA local
- [x] Definir mensajes versionados de WebSocket y validación.
- [x] Implementar configuración local, token de emparejamiento y logs seguros.
- [x] Implementar normalización PCM, buffer con solapamiento, ASR faster-whisper y traductor NLLB.
- [x] Implementar servidor FastAPI localhost con health, modelos y WebSocket autenticado.
- [x] Implementar tests unitarios sin cargar pesos.

### Task 2: Gestor de modelos
- [x] Definir manifiesto de packs y licencias.
- [x] Implementar descarga mediante huggingface_hub, staging, activación atómica y rollback.
- [x] Implementar CLI para listar/instalar/eliminar/rollback.
- [x] Mantener pesos fuera de Git/ZIP.

### Task 3: Puente Rust/Tauri
- [x] Implementar EngineProcessManager y ModelInventoryManager.
- [x] Exponer comandos Tauri para iniciar/detener motor, obtener token, inventario y sesiones.
- [x] Extender configuración/versionado y rutas estándar.
- [x] Mantener mensajes públicos sanitizados.

### Task 4: Extensión Chromium
- [x] Manifest V3 con permisos mínimos y dominios de reunión explícitos.
- [x] Captura por acción del usuario, offscreen document, AudioWorklet y resample PCM16.
- [x] WebSocket autenticado a localhost.
- [x] Overlay de subtítulos y popup de configuración/emparejamiento.

### Task 5: UI final de escritorio
- [x] Panel con estados reales.
- [x] Traducción en vivo: motor, token y guía de extensión.
- [x] Modelos: inventario/instalación por CLI/backend.
- [x] Sesiones: listado y exportación TXT/SRT.
- [x] Ajustes de privacidad, CPU/GPU y persistencia.

### Task 6: Sesiones y exportación
- [x] Persistencia local opt-in de transcripciones.
- [x] TXT/SRT y metadatos mínimos.
- [x] No almacenar audio por defecto.

### Task 7: Build, instalación y actualización
- [x] Script de setup de desarrollo Windows.
- [x] Script de build del sidecar con Nuitka.
- [x] Tauri bundling preparado.
- [x] Workflow de release con artefactos Windows.
- [x] Updater seguro documentado; claves privadas fuera del repositorio.

### Task 8: Web y documentación
- [x] Landing estática sin trackers/CDN.
- [x] README completo con flujos de instalación y uso.
- [x] Manual de arquitectura, privacidad, modelos y extensión.

### Task 9: Verificación local
- [x] Compilación sintáctica Python.
- [x] Tests unitarios del motor sin pesos.
- [x] Tests de privacidad/sitio.
- [x] Validación JSON/manifest/extensión y escaneo de marcadores/secretos.
- [ ] CI Rust/Tauri/Windows final: se ejecutará al subir el ZIP pulido a GitHub.
