# MilyVoiceTraductor — Beta Engine Hub

> **Estado:** Beta / Testing. Esta compilación no sustituye la versión estable `v2.0.1`.

La rama `pruebas` contiene la siguiente evolución del motor de MilyVoiceTraductor. El objetivo de esta beta es reducir latencia y consumo de memoria, mejorar la selección automática de motores/modelos y mantener funcionamiento útil en equipos modestos.

## Versión estable

La versión estable y recomendada para uso normal continúa siendo **MilyVoiceTraductor `v2.0.1`**:

- Release: https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.0.1
- Instalador Windows x64: https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.1/MilyVoiceTraductor_2.0.1_x64-setup.exe

La estable conserva Whisper Small + M2M100 CT2 INT8 como baseline publicado y no se reemplaza por la beta hasta completar el ciclo de pruebas.

## Beta Engine Hub

Build validado de referencia:

- Rama: `pruebas`
- SHA fuente: `a6a8b7cb22b1feb656e492f3bba0e2e2555d5737`
- CI: `#1078`
- Resultado: **success**
- Run: https://github.com/LORDMANUEL/milyvoicetraductor/actions/runs/32247097330
- Artefacto Windows: https://github.com/LORDMANUEL/milyvoicetraductor/actions/runs/32247097330/artifacts/9364017906

> GitHub puede requerir iniciar sesión para descargar artefactos de Actions. Este artefacto es de prueba y expira según la retención configurada del workflow.

### Motores y modelos en prueba

- **Moonshine Tiny Streaming + Marian Tiny INT8** para EN→ES de muy baja latencia.
- **Whisper Tiny + Marian Tiny INT8** como ruta Lite EN→ES y fallback local.
- **Whisper Tiny multilingüe + Marian ZH→EN→ES INT8** como ruta Lite ZH→ES.
- Registro/adapters para sherpa-onnx, whisper.cpp y Vosk; solo se promueven automáticamente cuando runtime, pack y benchmark están completos.
- Google Chirp permanece opcional y requiere consentimiento explícito por ser un proveedor cloud.

### Selección automática y recursos

Engine Hub detecta hardware, ruta de idioma y disponibilidad real del runtime. Un motor no se selecciona por estar instalado: debe caber en presupuesto y superar los gates de rendimiento.

Perfil objetivo de pruebas:

```text
Equipo de referencia: 8 GB RAM
Windows:               4 GB
MilyVoiceTraductor:    máximo 2 GB
Chrome/Chromium:       1 GB
Reserva libre:         1 GB
CPU objetivo:          2 cores / 4 threads
Clase GPU/iGPU:        512 MB
Presupuesto VRAM app:  384 MB
```

El controlador puede degradar funciones no esenciales bajo presión antes de permitir crecimiento de cola o memoria: parciales, diarización, word timestamps y TTS se reducen antes que resultados finales.

### Extensión beta

La extensión de la rama `pruebas` también incorpora cambios que se validan junto al motor:

- modo **Tutor**;
- repetición/pronunciación del original;
- temas Automático, Mily, Cine, Clase, Alto contraste y Karaoke;
- elección de voces y voces por hablante;
- caché de preferencias;
- animación Karaoke solo cuando está activa para reducir CPU en reposo.

## Evidencia CI #1078

El pipeline Windows de la beta completó correctamente:

1. AI unit tests y stress realtime.
2. Simulación de máquina objetivo.
3. Política que impide activar Quality bajo presupuesto de 2 GiB.
4. Benchmark real Moonshine Lite EN→ES.
5. Benchmark real Whisper Tiny Lite EN→ES.
6. Benchmark Lite mandarín ZH→ES.
7. Rust tests y Clippy.
8. Build Desktop Windows.
9. Verificación de subsistema GUI.
10. Tauri NSIS.
11. Instalación del NSIS generado.
12. Empaquetado de extensión y SHA-256.

Esta evidencia permite distribuir la compilación como **beta para pruebas**, no como reemplazo automático de `v2.0.1`.

## Criterio para promover a estable

La beta solo debe sustituir la versión estable cuando se complete validación repetida en PCs Windows reales de bajos recursos, incluyendo reuniones largas, audio real EN/ES/ZH, Chrome/Teams concurrente, consumo de RAM sostenido, recuperación bajo presión y actualización sobre instalaciones existentes.
