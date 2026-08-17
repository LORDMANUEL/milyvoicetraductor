# Arquitectura completa — MilyVoiceTraductor

```text
Chromium MV3
  tabCapture → Offscreen → AudioWorklet PCM16
           │
           │ ws://127.0.0.1 + token
           ▼
AI Engine local (Python)
  protocolo → buffer → faster-whisper → traductor → sesiones
           │
           ├─ business-qwen (Qwen3)
           └─ lite-nllb (NLLB, no comercial)

Tauri 2 / Rust
  UI Svelte
    ├─ configuración
    ├─ EngineProcessManager
    ├─ ModelManagerService
    ├─ SessionService
    ├─ SQLite
    ├─ logs sanitizados
    └─ caché limitada
```

## Límites de confianza

- El navegador nunca conoce rutas del sistema; únicamente el token que el usuario copia/pega para emparejar.
- El motor escucha solo en `127.0.0.1`.
- El audio no atraviesa Internet. Solo la instalación/actualización de pesos accede a repositorios externos.
- Persistir transcripciones es opt-in.
- Los logs no incluyen texto de reuniones, audio, emails, rutas de usuario completas ni secretos.
- GPU es una optimización, no un requisito.

## Fallos y degradación

- Sin GPU → CPU/int8 para Whisper y CPU para traducción.
- Sin modelos → el servidor responde `MODEL_NOT_INSTALLED`; no inventa traducciones.
- Sin motor → el desktop muestra `notInstalled` y permite diagnóstico/instalación desde los scripts de setup.
- Motor caído → Rust puede reiniciarlo; el motor también vigila el PID padre para no quedar huérfano.
- Descarga incompleta → se elimina staging y no se activa el pack.
