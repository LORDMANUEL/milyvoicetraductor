# MilyVoiceTraductor — Coordinación de Workstreams

Este documento existe para que varios chats/agentes trabajen en paralelo sobre `pruebas` sin sobrescribir cambios ni duplicar trabajo.

**Fuente normativa:** `MASTER.md`.

## Regla cero

Antes de escribir en GitHub:

1. leer `MASTER.md`;
2. leer este archivo;
3. consultar el HEAD actual de `pruebas`;
4. volver a leer el archivo que se vaya a modificar y usar su SHA actual;
5. no asumir que un archivo conserva el contenido visto en un turno anterior;
6. si el archivo pertenece al otro workstream, no reemplazarlo: documentar la necesidad y esperar al checkpoint de integración.

`main` no se toca durante desarrollo.

## Freeze de integración MilyVoice 2.0.0

La candidata actual se versiona como **2.0.0** por el salto conjunto de realtime, audio, MilyCompute, hardware routing y sistema de pruebas. Durante este freeze:

- el trabajo independiente puede continuar dentro de archivos reservados a cada workstream;
- los metadatos de versión, `Cargo.toml`, `.github/workflows/ci.yml`, `publish-rc.yml` y scripts de mega benchmark quedan en estado `INTEGRATION`;
- ningún workstream debe volver a 1.0.5 esos archivos;
- el artefacto final solo se considera candidato entregable cuando contenga EXE NSIS, extensión Chromium, `SHA256SUMS.txt` y reporte MegaBench 2.0.0 producidos por el mismo SHA;
- los Model Labs Quality/Legacy no se promueven automáticamente a producción durante este freeze.

---

## Workstream A — Plataforma / Arquitectura / MilyCompute

**Responsable actual:** este chat.

### Objetivo

Cerrar la fundación técnica que permite a MilyVoice ejecutar el mejor backend disponible y preparar correctamente los cuatro fast paths Tier 1 EN↔ES y ZH↔ES.

### Alcance

- `MASTER.md` y gobierno de arquitectura.
- MilyCompute Foundation.
- Hardware Profiler profesional.
- inventario de CPU/GPU/aceleradores;
- discovery de CPU/CUDA/DirectML/Windows ML/OpenVINO/Vulkan;
- Backend Registry y estados `available / detected-not-ready / unavailable`;
- microbenchmark, scoring y caché de selección;
- Model Router foundation;
- presupuesto de memoria/cómputo;
- abstracción de idiomas Tier 1;
- protocolo preparado para EN→ES, ES→EN, ZH→ES, ES→ZH;
- Mily Linguistic Engine foundation;
- gobierno de packs Stable / Quality / Legacy;
- gates de promoción de modelos y hardware;
- CI estático/contract tests de estas capas.

### Archivos reservados a Workstream A mientras esté `ACTIVE`

- `MASTER.md`
- `docs/WORKSTREAMS.md`
- `crates/mily-system/**`
- `crates/mily-compute/**`
- `services/ai/mily_ai/languages.py` si se crea
- `services/ai/mily_ai/compute_router.py` si se crea
- tests directamente asociados a MilyCompute/hardware/language contracts

### Archivos compartidos — no editar sin checkpoint

- `Cargo.toml`
- `services/ai/mily_ai/protocol.py`
- `services/ai/mily_ai/providers.py`
- `services/ai/mily_ai/server.py`
- `.github/workflows/ci.yml`

---

## Workstream B — Realtime / UX / Multimodal / Release

**Responsable actual:** chat de “Validar y arreglar GitHub” / implementación realtime.

### Objetivo

Cerrar funcional y visualmente el producto realtime ya especificado y llevarlo hasta pruebas reales Windows/NSIS sin rediseñar MilyCompute.

### Alcance

- Desktop Svelte/Tauri UX.
- extensión Chrome/Edge.
- browser tab capture.
- WASAPI loopback y fallback protegido.
- micrófono y media_file.
- speakers A/B/C.
- renombrar/fijar/dominante/silenciar-reactivar speaker.
- voz por speaker.
- TTS local y cola TTS.
- ducking configurable.
- anti-feedback sin apagar PCM.
- karaoke/word timestamps.
- modos Reunión/Educativo/Karaoke/Compacto.
- `Subtítulos`, `Subtítulos + voz`, `Solo voz`.
- posición/tamaño/opacidad/temas/contraste.
- sesiones TXT/SRT/VTT bilingües.
- UI de exportación.
- tests frontend/extensión/realtime.
- Windows release build, `WINDOWS_GUI`, NSIS real, instalación real, extensión ZIP y SHA256.

### Archivos reservados a Workstream B mientras esté `ACTIVE`

- `apps/desktop/**` salvo metadatos de versión durante el freeze 2.0;
- `apps/extension/**` salvo manifest de versión durante el freeze 2.0;
- `services/ai/mily_ai/system_loopback.py`
- `services/ai/mily_ai/speakers.py`
- `services/ai/mily_ai/echo_guard.py`
- `services/ai/mily_ai/sessions.py`
- tests directamente asociados a realtime/UX/exportación/WASAPI/speakers/TTS
- scripts de validación específica NSIS/extension/realtime, salvo los scripts MegaBench 2.0 en integración.

### Restricciones

- No cambiar el stack estable de modelos por TriCore/Legacy.
- No declarar ES→EN o ES→ZH soportado hasta que el protocolo/router lo habilite realmente.
- No modificar `MASTER.md` salvo registrar una contradicción para Workstream A.
- Si necesita tocar `protocol.py`, `providers.py`, `server.py` o CI, respetar el lock de integración.

---

## Workstream C — Model Lab / R&D

**Responsable:** chat/laboratorio de modelos.

### Objetivo

Entrenar, evaluar y exportar candidatos de modelos sin interferir con el cierre de la aplicación.

### Estado actual obligatorio

#### Quality / TriCore

- trainers/configs/evaluación/exportación preparados;
- objetivo ASR EN/ES/ZH + MT EN↔ES/ZH↔ES;
- **no asumir pesos fine-tuned promocionados**;
- cualquier candidato debe superar baseline y gates realtime.

#### Legacy CPU

- objetivo Whisper Tiny + MT pequeño INT8;
- referencia Intel Core i3 Haswell sin GPU;
- **no asumir pesos finales Stable**;
- benchmark físico de i3 real obligatorio antes de promoción.

### Regla de aislamiento

Workstream C no modifica `pruebas` de la aplicación para introducir un modelo experimental. Solo entrega artefacto, hashes, licencia/proveniencia, benchmark, métricas, formatos y reporte PASS/FAIL. Workstream A decide si el candidato entra al Model Router.

---

## Locks temporales de archivos compartidos

Formato: `archivo | owner | motivo | estado`

Estado permitido: `FREE`, `LOCKED-A`, `LOCKED-B`, `INTEGRATION`.

### Estado durante freeze 2.0.0

- `Cargo.toml` | integración 2.0 | versionado/workspace | `INTEGRATION`
- `services/ai/mily_ai/protocol.py` | — | contrato WebSocket/languages/realtime | `FREE`
- `services/ai/mily_ai/providers.py` | — | ASR/MT/backends | `FREE`
- `services/ai/mily_ai/server.py` | B preferente | realtime server | `LOCKED-B`
- `.github/workflows/ci.yml` | integración 2.0 | mega gates + artefacto | `INTEGRATION`
- `.github/workflows/publish-rc.yml` | integración 2.0 | publicación 2.0 | `INTEGRATION`
- `scripts/test_release_version.py` | integración 2.0 | consistencia 2.0 | `INTEGRATION`
- `installer/windows/test-realtime-model.ps1` y MegaBench | integración 2.0 | modelo real + velocidad | `INTEGRATION`

---

## Checkpoints de integración

### Checkpoint P1 — Realtime closure

Workstream B demuestra frontend/tests/build verdes, extensión/guards verdes, WASAPI/fallback correcto, speaker/TTS/karaoke/export funcional y no pérdida deliberada de PCM durante TTS.

### Checkpoint P2 — MilyCompute foundation

Workstream A demuestra profiler CPU, inventario GPU cuando esté disponible, registry de backends, discovery conservador, benchmark/scoring determinista, fallback CPU y lenguaje Tier 1 desacoplado arquitectónicamente.

### Checkpoint P3 — MegaTest 2.0

- pruebas unitarias Python/Frontend/Rust;
- Clippy `-D warnings`;
- stress de colas y backpressure;
- modelo real Whisper Small + M2M100 CT2 INT8;
- P50/P95 ASR y MT, RTF ASR, end-to-end cuando exista fixture válido;
- EN→ES y ZH→ES smoke real obligatorios;
- reporte JSON versionado 2.0.0;
- runtime privado, `WINDOWS_GUI`, NSIS e instalación real;
- extensión ZIP y SHA256 del mismo SHA.

El benchmark del runner GitHub mide regresiones de la candidata; **no sustituye** el gate físico Legacy sobre un i3 Haswell real.

### Checkpoint P4 — Release candidate

- README no declara Stable antes del release real;
- limpiar ramas antiguas después de verificar trabajo único;
- proteger `main` cuando los workflows requeridos estén definidos;
- merge a `main` únicamente desde `pruebas` validada.

---

## Regla sobre EN↔ES y ZH↔ES

```text
voz EN → ASR EN → MT EN→ES → texto/voz ES
voz ZH → ASR ZH → MT ZH→ES → texto/voz ES
voz ES → ASR ES → MT ES→EN → texto/voz EN
voz ES → ASR ES → MT ES→ZH → texto/voz ZH
```

EN→ES y ZH→ES son el flujo receptor prioritario original y no pueden empeorar. ES→EN y ES→ZH son Tier 1 para conversación bidireccional futura.

## Regla sobre modelos

Hoy la aplicación debe seguir operando con el baseline estable Whisper Small + M2M100 CT2 INT8.

Los nombres `MilyASR-*`, `MilyMT-*`, `TriCore`, `Quality` o `Legacy` describen **candidatos/laboratorios** hasta que existan pesos reales y un reporte de promoción aprobado. Nunca convertir un `READY_FOR_GPU_FINETUNING`, trainer, adapter vacío, dry-run o configuración en una afirmación de “modelo entrenado”.

## Cómo otro chat debe retomar trabajo

1. leer `MASTER.md`;
2. leer este archivo;
3. identificar su workstream;
4. comprobar locks;
5. consultar HEAD de `pruebas`;
6. validar último CI asociado al SHA relevante;
7. continuar solo su lista;
8. no modificar archivos `INTEGRATION` hasta que se libere el freeze 2.0.
