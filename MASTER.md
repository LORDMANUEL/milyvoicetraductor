# MilyVoiceTraductor 2.0.0 — MASTER

Este documento es la **fuente operativa y normativa principal** de MilyVoiceTraductor. Consolida los requisitos aprobados entre conversaciones, especificaciones, Model Labs, commits y workstreams.

**Regla:** si un README, chat, experimento, documento 1.x o plan histórico contradice este MASTER, prevalece este MASTER hasta que una decisión posterior se documente explícitamente en `pruebas`.

## 1. Objetivo de MilyVoice 2.0

MilyVoiceTraductor es una aplicación Windows local y multimodal para:

- capturar audio de navegador, micrófono, sistema Windows o archivo multimedia;
- convertir voz a texto mediante ASR local;
- traducir texto mediante MT local;
- mostrar subtítulos originales/traducidos;
- sintetizar voz opcionalmente;
- reconocer hablantes de forma efímera por sesión;
- trabajar con video, cursos, canciones y modo karaoke;
- exportar sesiones cuando el usuario dé consentimiento;
- aprovechar CPU/GPU disponibles sin exigir CUDA o una GPU dedicada.

**2.0.0 es un salto de arquitectura y rendimiento**, no un simple cambio de versión. Introduce la fundación MilyCompute, audio/realtime ampliado y un sistema de MegaBench integrado al release.

## 2. Autoridad documental

Orden de autoridad:

1. `MASTER.md` — este documento.
2. `docs/WORKSTREAMS.md` — coordinación y locks.
3. diseños especializados vigentes.
4. planes técnicos vigentes.
5. especificaciones 1.x históricas como referencia de evolución.
6. conversaciones antiguas.

Documentos históricos que siguen siendo útiles pero no cambian la versión normativa:

- `docs/superpowers/specs/2026-08-18-milyvoice-1.0.5-master-spec.md`;
- `docs/superpowers/specs/2026-08-18-realtime-universal-audio-karaoke-design.md`;
- `docs/superpowers/plans/2026-08-18-cpu-realtime-optimization.md`;
- `docs/superpowers/specs/2026-08-17-automatic-onboarding-embedded-runtime-design.md`.

## 3. Ramas y trabajo paralelo

- `main`: estable/publicable. No se programa directamente aquí.
- `pruebas`: desarrollo, CI, RC e integración.
- No crear ramas efímeras como flujo normal.
- Varios chats pueden trabajar en paralelo únicamente respetando `docs/WORKSTREAMS.md`.
- Antes de modificar un archivo compartido: leer HEAD, SHA actual y lock.
- Nunca asumir que otro chat terminó un bloque; verificar código + tests + SHA.
- Merge `pruebas → main` solo después de todos los gates 2.0.

## 4. Versión 2.0.0

La candidata debe declarar **2.0.0** de forma consistente en:

- `VERSION`;
- Cargo workspace/desktop;
- Node root/Desktop;
- Tauri;
- motor Python;
- extensión Chromium;
- API/frontend preview;
- CI/artifact naming;
- publish workflow;
- instalador NSIS;
- release assets;
- sitio/README de candidata.

CI debe fallar ante cualquier divergencia.

## 5. Idiomas Tier 1 y definición correcta de ASR/MT

**ASR = voz → texto.** ASR no traduce idiomas.

**MT = texto → texto traducido.**

Tier 1 obligatorio:

- Español (`es`).
- Inglés (`en`).
- Chino mandarín (`zh`).

Fast paths end-to-end:

```text
voz EN → ASR EN → MT EN→ES → texto/voz ES
voz ZH → ASR ZH → MT ZH→ES → texto/voz ES
voz ES → ASR ES → MT ES→EN → texto/voz EN
voz ES → ASR ES → MT ES→ZH → texto/voz ZH
```

### Prioridad de producto

**EN→ES y ZH→ES son los flujos receptores prioritarios** para reuniones, videos, cursos y contenido externo. Su latencia/calidad no puede degradarse por agregar otros idiomas.

ES→EN y ES→ZH son Tier 1 para conversación bidireccional y deben alcanzar gates equivalentes antes de anunciarse como experiencia voice-to-voice cerrada.

No afirmar soporte bidireccional funcional solamente porque el diseño lo contemple; el protocolo/router correspondiente debe estar implementado y verificado.

## 6. Mily Linguistic Engine

La arquitectura incluye una capa lingüística formal y liviana:

- Language Detector;
- Text Normalizer;
- Grammar/Stability Layer;
- Terminology Manager;
- Sentence Segmenter;
- Context Manager;
- Pronunciation Lexicon;
- Phonetic Layer.

Perfiles mínimos de arquitectura:

- `en-es-realtime`;
- `es-en-realtime`;
- `zh-es-realtime`;
- `es-zh-realtime`.

Para mandarín:

- respetar información tonal;
- distinguir simplificado/tradicional cuando aplique a presentación;
- pinyin opcional solo en UI educativa;
- pinyin no sustituye texto interno ASR/MT;
- no introducir pitch-shift de training que altere tonos del mandarín.

## 7. Pack estable actual

Hasta que exista un modelo propio realmente promocionado, el baseline estable sigue siendo:

```text
ASR: Systran/faster-whisper-small
MT : facebook/m2m100_418M → CTranslate2 INT8
```

Reglas:

- snapshots fijados por revisión;
- CPU INT8 de primera clase;
- CUDA opcional si existe y rinde mejor;
- no sustituir el baseline por un trainer, dry-run o modelo no benchmarkeado;
- warm-up antes del primer audio útil;
- activación atómica de packs;
- rollback disponible.

## 8. Estado normativo de Model Labs

### TriCore / Quality

Preparado para:

- MilyASR EN/ES/ZH sobre Whisper Small;
- MT EN→ES, ES→EN, ZH→ES, ES→ZH;
- LoRA/fine-tuning;
- evaluación;
- merge/export CT2/ONNX;
- promotion gates.

**Estado actual:** infraestructura de laboratorio preparada; **los pesos fine-tuned no se consideran producción mientras no existan artefactos reales entrenados y un reporte de promoción aprobado**.

### Legacy CPU

Objetivo:

- Whisper Tiny INT8 ASR EN/ES/ZH;
- MT pequeño INT8;
- referencia Intel Core i3 Haswell 2C/4T sin GPU;
- prioridad a tiempo real y bajo consumo.

**Estado actual:** laboratorio/tests/configuración preparados; **no declarar Legacy Stable sin pesos finales y benchmark físico sobre i3 Haswell real**.

### Promoción de un modelo

Un candidato solo entra al producto si:

1. existen pesos reales reproducibles;
2. licencia/proveniencia son válidas para el canal de uso;
3. no empeora números, negaciones, nombres o términos críticos;
4. supera o empata el baseline en calidad relevante;
5. cumple P50/P95/RTF del hardware objetivo;
6. pasa benchmark end-to-end;
7. produce formatos requeridos por MilyCompute;
8. queda versionado, hashado y reversible.

**La velocidad forma parte de la calidad.**

## 9. MilyCompute Foundation

MilyVoice no implementa drivers kernel propios. MilyCompute es la capa de orquestación sobre runtimes/APIs existentes.

Cadena:

```text
Hardware Probe
→ Backend Discovery
→ Compatibility Filter
→ Benchmark
→ Scoring
→ Model Router
→ Runtime Telemetry
→ Fallback
```

Componentes:

- Hardware Profiler;
- Backend Registry;
- Backend Selector;
- Benchmark Engine;
- Memory/Compute Budget;
- Model Router foundation;
- Fallback Manager;
- caché de selección por hardware/modelo.

Backends de arquitectura:

- CPU AVX/AVX2/FMA/AVX512 cuando aplique;
- CUDA;
- Windows ML;
- DirectML;
- OpenVINO;
- Vulkan;
- ROCm/HIP cuando exista compatibilidad real.

### Regla conservadora

`runtime_detected != adapter_ready`.

Detectar DirectML/OpenVINO/Vulkan/CUDA **no autoriza a afirmar que el modelo activo ya ejecuta en ese backend**. Los estados deben distinguir al menos:

- `available/ready`;
- `detected-not-ready`;
- `unavailable`.

CPU siempre debe ser fallback seguro.

### Selección

No usar reglas rígidas por marca (`Intel=OpenVINO`, `AMD=DirectML`, etc.). Seleccionar por medición real cuando el adaptador esté listo:

1. RTF;
2. latencia;
3. memoria/estabilidad como criterio adicional.

Una GPU disponible puede perder frente a CPU y MilyVoice debe elegir CPU si el benchmark lo demuestra.

## 10. Hardware Profiler

CPU:

- fabricante/modelo;
- arquitectura;
- núcleos físicos;
- hilos lógicos;
- SSE4.2/AVX/AVX2/FMA/AVX512 cuando aplique;
- RAM total/disponible;
- benchmark corto local.

GPU/aceleradores cuando Windows permita consultarlo con seguridad:

- fabricante/modelo;
- integrada/discreta;
- memoria dedicada/compartida si está disponible;
- CUDA/DirectML/OpenVINO/Vulkan/Windows ML capabilities;
- evidencia de runtime;
- benchmark solo cuando exista adaptador funcional.

También registrar audio devices/WASAPI capabilities sin exponer información sensible innecesaria.

## 11. Pipeline realtime 2.0

Cadena objetivo:

```text
fuente
→ PCM 16 kHz
→ energy gate/VAD
→ ring/segmentación adaptativa
→ ASR incremental
→ estabilidad
→ MT
→ OutputBus
→ subtítulos/TTS/sesión
```

Requisitos de rendimiento:

- presupuesto por núcleos físicos;
- `cpu_threads` Whisper;
- `intra_threads`/control CTranslate2;
- evitar sobresuscripción;
- PCM binario por WebSocket;
- primera inferencia conversación ~0.8–1.2 s cuando sea viable;
- parciales estables;
- ASR/MT desacoplados cuando CPU lo permita;
- colas limitadas;
- `beam_size=1` realtime;
- warm-up;
- estados `healthy/pressure/overloaded`;
- bajo presión reducir opcionales/parciales antes que perder finales;
- ningún crecimiento monotónico de cola;
- jamás descartar deliberadamente utterances finales por optimización.

## 12. Fuentes de audio

- `browser_tab`: pestaña Chromium capturable;
- `system_loopback`: WASAPI loopback Windows con fallback protegido;
- `microphone`;
- `media_file`.

La extensión no se limita a Meet/Teams/Zoom: debe funcionar en YouTube, cursos, radio web, reproductores HTML5 y sitios `http/https` capturables. Páginas protegidas se rechazan con mensaje explícito.

## 13. Video, educativo y karaoke

Modos:

- Reunión;
- Educativo;
- Karaoke;
- Compacto.

Karaoke:

- español + original;
- `word_timestamps` únicamente cuando se necesiten;
- resaltado palabra/fragmento;
- más contexto/VAD menos agresivo;
- en CPU débil degradar palabra→frase antes que perder realtime.

## 14. Hablantes

Opcional y local:

- Hablante A/B/C…;
- `speakerId` estable por sesión;
- color estable;
- modos todos/dominante/fijado;
- renombrar/priorizar/silenciar/reactivar;
- voz TTS asignable por speaker;
- no inferir género, edad o identidad.

## 15. TTS y OutputBus

Modos:

- Subtítulos;
- Subtítulos + voz;
- Solo voz.

TTS:

- local;
- voces Windows/Chromium como primera implementación;
- cola separada;
- ducking configurable;
- anti-feedback sin apagar deliberadamente la captura PCM;
- no abrir consola.

## 16. Subtítulos, temas y accesibilidad

- original + traducción;
- original ocultable;
- Shadow DOM en web;
- cinco temas mínimos: Mily azul, Oscuro cine, Clase clara, Alto contraste, Karaoke neón;
- tamaño/posición/opacidad configurables;
- contraste suficiente por speaker.

## 17. Sesiones y exportación

Persistencia desactivada por defecto y solo con consentimiento.

Cuando se guarda una sesión puede incluir:

- original;
- traducción;
- timestamps;
- speakerId;
- words opcionales.

Formatos:

- TXT bilingüe;
- SRT español;
- SRT bilingüe;
- VTT bilingüe;
- cues por palabra cuando existan datos karaoke.

## 18. Instalación Windows sin CMD

El usuario instala una sola app gráfica.

Obligatorio:

- `MilyVoiceTraductor.exe` = `IMAGE_SUBSYSTEM_WINDOWS_GUI`;
- procesos Python/bridge sin ventanas de consola;
- runtime Python 3.13 privado incluido;
- sin dependencia de Python/winget/pip del usuario;
- Native Messaging auto-configurado;
- sin token/puerto manual en UX normal;
- NSIS no descarga gigabytes durante instalación;
- preparación de modelos dentro de la UI con progreso/reintento;
- reparación integrada;
- cerrar una terminal inexistente nunca puede matar la app.

## 19. Seguridad y privacidad

- audio/transcripción/MT/TTS local salvo descarga inicial de pesos;
- localhost/Native Messaging restringidos;
- credenciales efímeras;
- logs redactados;
- sin secretos `.env`, tokens o contraseñas en Git;
- sin audio/transcripciones de usuario en Git;
- modelos fijados por revisión/hash;
- activación atómica y rollback.

## 20. MegaBench 2.0

MilyVoice 2.0 introduce un gate de rendimiento reproducible en el pipeline Windows.

El mismo SHA debe ejecutar el pack real Whisper Small + M2M100 CT2 INT8 y producir:

- ASR P50/P95 ms;
- ASR RTF P50/P95;
- MT EN→ES P50/P95 ms;
- MT ZH→ES P50/P95 ms;
- end-to-end P95 estimado;
- entorno/model pack;
- PASS/FAIL;
- `MilyVoiceTraductor-2.0.0-MegaBench.json`.

El runner de GitHub es un **gate de regresión**, no una certificación de hardware mínimo. El benchmark físico Legacy Haswell sigue siendo un gate distinto y pendiente hasta ejecutarse en ese equipo real.

Los límites CI deben impedir regresiones catastróficas sin confundir variabilidad de runners con especificaciones de producto.

## 21. Mega Tests / Definition of Done 2.0

No marcar 2.0 como entregable hasta pasar, sobre el mismo SHA:

### Fuente/privacidad

- consistencia 2.0.0;
- source verification;
- privacy scan;
- extension guard;
- site smoke.

### Python/realtime

- unit tests completos;
- `compileall`;
- benchmarking contract;
- CPU budget;
- queue/backpressure stress;
- realtime optimization;
- telemetry;
- final utterance preservation.

### Frontend

- TypeScript;
- tests;
- build.

### Rust/MilyCompute

- `cargo fmt`;
- workspace tests;
- MilyCompute backend selection/registry/discovery contracts;
- Clippy `-D warnings`;
- release build.

### Windows real

- runtime Python privado;
- bridge/Native Messaging instalado;
- installed-flow;
- MegaBench real EN→ES/ZH→ES;
- Rust tests/Clippy Windows;
- Desktop Release;
- `WINDOWS_GUI`;
- Tauri NSIS;
- instalación real del NSIS generado;
- extensión Chromium ZIP.

### Artefacto final

Debe contener exactamente desde el mismo SHA:

- `MilyVoiceTraductor_2.0.0_x64-setup.exe`;
- `MilyVoiceTraductor-Chromium-Extension.zip`;
- `MilyVoiceTraductor-2.0.0-MegaBench.json`;
- `SHA256SUMS.txt`.

Solo después puede integrarse a `main` y publicarse v2.0.0.

## 22. Roadmap posterior

No mezclar roadmap futuro con Definition of Done actual.

### 2.1

- adapters reales DirectML/OpenVINO/Vulkan donde ganen benchmarks;
- perfiles lingüísticos Tier 1 más profundos;
- Model Advisor avanzado.

### 2.2

- full-duplex;
- micrófono virtual;
- voz↔voz bidireccional cerrada.

### 2.3

- tutor;
- fonética avanzada;
- pronunciación/correcciones;
- pinyin educativo;
- ejercicios.

## 23. Política de implementación

- TDD: test rojo → implementación mínima → verde → refactor.
- No ocultar deuda técnica.
- No llamar “funcional” a un backend solo detectado.
- No promover pesos inexistentes.
- No degradar privacidad por rendimiento.
- No sacrificar finales por latencia.
- No cambiar el baseline de modelos antes de benchmark y promotion gate.
- `main` siempre debe permanecer funcional.
