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
- `crates/mily-compute/**` si se crea
- `services/ai/mily_ai/languages.py` si se crea
- `services/ai/mily_ai/compute_router.py` si se crea
- tests directamente asociados a MilyCompute/hardware/language contracts

### Archivos compartidos — no editar sin checkpoint

- `Cargo.toml`
- `services/ai/mily_ai/protocol.py`
- `services/ai/mily_ai/providers.py`
- `services/ai/mily_ai/server.py`
- `.github/workflows/ci.yml`

Cuando Workstream A necesite uno de estos archivos, primero registra abajo el lock temporal.

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

- `apps/desktop/**`
- `apps/extension/**`
- `services/ai/mily_ai/system_loopback.py`
- `services/ai/mily_ai/speakers.py`
- `services/ai/mily_ai/echo_guard.py`
- `services/ai/mily_ai/sessions.py`
- tests directamente asociados a realtime/UX/exportación/WASAPI/speakers/TTS
- scripts de validación específica NSIS/extension/realtime, salvo gates explícitos de MilyCompute

### Restricciones

- No cambiar el stack estable de modelos por TriCore/Legacy.
- No declarar ES→EN o ES→ZH soportado hasta que el protocolo/router lo habilite realmente.
- No modificar `MASTER.md` salvo registrar una contradicción para Workstream A.
- Si necesita tocar `protocol.py`, `providers.py`, `server.py` o CI, registrar lock compartido antes.

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

Workstream C no modifica `pruebas` de la aplicación para introducir un modelo experimental. Solo entrega:

- artefacto versionado;
- hashes;
- licencia/proveniencia;
- benchmark;
- métricas de calidad;
- formatos de exportación;
- reporte PASS/FAIL.

Workstream A decide si el candidato entra al Model Router; Workstream B no lo integra directamente.

---

## Locks temporales de archivos compartidos

Formato:

`archivo | owner | motivo | estado`

Estado permitido: `FREE`, `LOCKED-A`, `LOCKED-B`, `INTEGRATION`.

### Estado inicial

- `Cargo.toml` | — | workspace compartido | `FREE`
- `services/ai/mily_ai/protocol.py` | — | contrato WebSocket/languages/realtime | `FREE`
- `services/ai/mily_ai/providers.py` | — | ASR/MT/backends | `FREE`
- `services/ai/mily_ai/server.py` | B preferente | realtime server; A debe evitarlo hasta integración compute | `LOCKED-B`
- `.github/workflows/ci.yml` | — | gates de ambos workstreams | `FREE`

Si un agente toma un lock, debe actualizar esta sección primero y liberar el lock al concluir el commit verificable.

---

## Checkpoints de integración

### Checkpoint P1 — Realtime closure

Workstream B demuestra:

- frontend/tests/build verdes;
- extensión/guards verdes;
- WASAPI/fallback correcto;
- speaker/TTS/karaoke/export funcional;
- no pérdida deliberada de PCM durante TTS.

### Checkpoint P2 — MilyCompute foundation

Workstream A demuestra:

- profiler CPU completo;
- inventario GPU real al menos en Windows cuando esté disponible;
- registry de backends;
- discovery sin afirmar soporte inexistente;
- benchmark/scoring determinista con tests;
- fallback CPU siempre disponible;
- lenguaje Tier 1 desacoplado de `target=es` en arquitectura/contratos.

### Checkpoint P3 — Integración

Solo después de P1 + P2:

- integrar cambios que requieran `protocol.py`, `providers.py`, `server.py` y CI;
- ejecutar suite completa;
- Windows runtime privado;
- NSIS real;
- functional smoke;
- real model pack gate.

### Checkpoint P4 — Release candidate

- PR #9 o su sucesor deja de ser draft solo con gates completos;
- README no declara Stable antes del release real;
- limpiar ramas antiguas solo después de verificar trabajo único;
- proteger `main` cuando los workflows requeridos estén definidos;
- merge a `main` únicamente desde `pruebas` validada.

---

## Regla sobre EN↔ES y ZH↔ES

La prioridad debe interpretarse correctamente:

```text
voz EN → ASR EN → MT EN→ES → texto/voz ES
voz ZH → ASR ZH → MT ZH→ES → texto/voz ES

voz ES → ASR ES → MT ES→EN → texto/voz EN
voz ES → ASR ES → MT ES→ZH → texto/voz ZH
```

EN→ES y ZH→ES son el flujo receptor prioritario original y no pueden empeorar.

ES→EN y ES→ZH son igualmente Tier 1 para conversación bidireccional y deben alcanzar calidad equivalente antes de considerar cerrada la experiencia voice-to-voice futura.

---

## Regla sobre modelos

Hoy la aplicación debe seguir pudiendo operar con el baseline estable Whisper Small + M2M100 CT2 INT8.

Los nombres `MilyASR-*`, `MilyMT-*`, `TriCore`, `Quality` o `Legacy` describen **candidatos/laboratorios** hasta que existan pesos reales y un reporte de promoción aprobado.

Nunca convertir un `READY_FOR_GPU_FINETUNING`, trainer, adapter vacío, dry-run o configuración en una afirmación de “modelo entrenado”.

---

## Cómo otro chat debe retomar trabajo

Al comenzar una sesión:

1. leer `MASTER.md`;
2. leer este archivo;
3. identificar su workstream;
4. comprobar locks;
5. consultar HEAD de `pruebas`;
6. validar último CI asociado al SHA relevante;
7. continuar solo su lista;
8. documentar cualquier nueva contradicción en este archivo, no improvisar un tercer diseño paralelo.
