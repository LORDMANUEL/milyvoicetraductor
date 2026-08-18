# MilyVoiceTraductor 1.0.5 — MASTER

Este documento es el punto de entrada y la fuente operativa del proyecto. Reúne las instrucciones y requisitos aprobados para que el alcance no vuelva a quedar disperso entre conversaciones, commits, Model Labs o fases.

**Regla:** si una conversación, documento histórico, experimento o README contradice este MASTER, prevalece este MASTER salvo que se actualice explícitamente en `pruebas` con una decisión posterior documentada.

## 1. Objetivo del producto

MilyVoiceTraductor es una aplicación Windows local y multimodal para escuchar audio, transcribir voz, traducir en tiempo real, mostrar subtítulos y, opcionalmente, sintetizar voz. Debe cubrir reuniones, pestañas web, videos, cursos, canciones, micrófono, audio del sistema y archivos multimedia compatibles.

Debe funcionar **sin GPU** y, cuando exista hardware acelerador, aprovecharlo automáticamente sin convertir CUDA/NVIDIA en requisito arquitectónico.

La experiencia prioritaria de calidad de MilyVoice es:

- voz inglesa → ASR inglés → traducción a español;
- voz china mandarín → ASR mandarín → traducción a español;
- voz española → ASR español → traducción a inglés;
- voz española → ASR español → traducción a mandarín.

Aclaración terminológica: **ASR no traduce idiomas**. ASR convierte voz a texto en el idioma reconocido. La traducción bidireccional la realiza MT. Por tanto, los cuatro fast paths end-to-end de primera clase son **EN→ES, ES→EN, ZH→ES y ES→ZH**.

## 2. Documentos normativos

- Especificación maestra completa: `docs/superpowers/specs/2026-08-18-milyvoice-1.0.5-master-spec.md`.
- Diseño de audio universal/karaoke/TTS/hablantes: `docs/superpowers/specs/2026-08-18-realtime-universal-audio-karaoke-design.md`.
- Plan de optimización CPU: `docs/superpowers/plans/2026-08-18-cpu-realtime-optimization.md`.
- Diseño de onboarding/runtime embebido: `docs/superpowers/specs/2026-08-17-automatic-onboarding-embedded-runtime-design.md`.
- Coordinación entre chats/workstreams: `docs/WORKSTREAMS.md`.

Orden de autoridad: **este MASTER → especificación maestra 1.0.5 → diseño especializado → plan de implementación → documentación histórica → conversaciones antiguas**.

## 3. Regla de ramas

- `main`: versión estable/publicable. No se programa directamente aquí.
- `pruebas`: desarrollo, tests, RC y correcciones.
- No crear ramas efímeras como flujo normal salvo necesidad extraordinaria.
- Solo fusionar `pruebas` a `main` después de CI completo, instalación NSIS real y pruebas funcionales del alcance aprobado.
- Ningún chat/agente puede asumir que otro chat terminó un bloque: debe verificar código, tests y último SHA de `pruebas`.

## 4. Versión

Toda la cadena de la candidata estable debe declarar `1.0.5`: `VERSION`, Cargo, Node, Tauri, motor, workflows, release, artefactos e instalador. CI debe fallar ante cualquier desalineación.

## 5. Instalación Windows — requisito obligatorio SIN CMD

El usuario instala una sola aplicación gráfica. No debe ver ni depender de ventanas `cmd.exe`, PowerShell, consola de Python o terminal auxiliar.

Gates obligatorios:

- `MilyVoiceTraductor.exe` debe ser `IMAGE_SUBSYSTEM_WINDOWS_GUI`.
- Procesos Python de motor, descarga, conversión y reparación se lanzan con `CREATE_NO_WINDOW` en Windows.
- El bridge/Native Messaging no abre terminal visible.
- NSIS silencioso no muestra `MessageBox` ni lanza procesos interactivos.
- El runtime Python 3.13 es privado y se instala con la aplicación; el usuario no instala Python, `winget`, pip ni venv.
- El modelo se prepara desde la UI después de abrir la app; NSIS no descarga gigabytes de IA durante instalación.
- La descarga/conversión del modelo debe mostrarse por fases: descarga ASR → descarga traducción → optimización/conversión → verificación → activación.
- Cerrar una supuesta ventana de terminal nunca puede matar la app porque esa ventana no debe existir.

## 6. Idiomas Tier 1 y fast paths

### Tier 1 — prioridad obligatoria

- Español (`es`).
- Inglés (`en`).
- Chino mandarín (`zh`, con manejo explícito de escritura cuando aplique).

El soporte a otros idiomas no puede degradar latencia, reconocimiento, traducción, gramática, fonética ni calidad de voz de estos tres.

### Cuatro fast paths privilegiados

- `EN → ES`
- `ES → EN`
- `ZH → ES`
- `ES → ZH`

Cada dirección debe poder tener configuración propia de ASR, estabilización, segmentación, caché, traducción, TTS y benchmark. No se debe asumir que EN→ES y ES→EN tienen idéntico comportamiento de parciales o longitud sintáctica.

### Prioridad práctica de producto

Para reuniones, videos y cursos, **EN→ES y ZH→ES siguen siendo la ruta principal de recepción**, porque el objetivo original es comprender inmediatamente contenido extranjero en español. Las rutas inversas **ES→EN y ES→ZH son también Tier 1** y deben evolucionar hasta la misma calidad para conversación bidireccional.

La arquitectura y el protocolo de 1.0.5 no deben quedar acoplados permanentemente a `targetLanguage=es`; cualquier compatibilidad temporal debe quedar marcada como deuda activa y no como diseño definitivo.

## 7. Mily Linguistic Engine

MilyVoice tendrá una capa lingüística formal y liviana, evitando usar un LLM grande para operaciones deterministas:

- Language Detector.
- Text Normalizer.
- Grammar/Stability Layer.
- Terminology Manager.
- Sentence Segmenter.
- Context Manager.
- Pronunciation Lexicon.
- Phonetic Layer.

Perfiles mínimos:

- `en-es-realtime`.
- `es-en-realtime`.
- `zh-es-realtime`.
- `es-zh-realtime`.

Para mandarín:

- distinguir cuando proceda simplificado/tradicional en presentación;
- segmentación y puntuación adecuadas;
- cuidado de números, nombres y términos técnicos;
- pinyin opcional **solo como capa educativa/presentación**, no como sustituto del texto interno del ASR/MT;
- ninguna política de entrenamiento futura puede introducir augmentación de pitch que destruya información tonal del mandarín.

## 8. Pack IA estable actual

Mientras no exista un candidato propio promocionado por benchmarks reales, el pack comercial estable sigue siendo:

- ASR: `Systran/faster-whisper-small`, snapshot fijado por commit.
- Traducción: `facebook/m2m100_418M`, snapshot fijado por commit.
- M2M100 convertido localmente a CTranslate2 INT8.
- CPU INT8 como ruta de primera clase.
- CUDA opcional cuando sea compatible y realmente mejore el rendimiento.

**No sustituir automáticamente este pack por experimentos Quality/Legacy solo porque existan trainers o configuraciones.**

## 9. Estado obligatorio de los Model Labs

### MilyVoice TriCore / Quality

Existe un laboratorio preparado para:

- `MilyASR-EN` sobre Whisper Small;
- `MilyASR-ES` sobre Whisper Small;
- `MilyASR-ZH` sobre Whisper Small;
- MT EN→ES, ES→EN, ZH→ES y ES→ZH sobre/adaptado desde M2M100.

**Estado normativo actual:** código de entrenamiento/evaluación/exportación preparado; **pesos fine-tuned reales no promocionados como producción**. No afirmar que existen modelos finales hasta comprobar artefactos entrenados y gates de calidad.

### MilyVoice Legacy CPU

Existe un laboratorio preparado para máquinas débiles con:

- Whisper Tiny INT8 para ASR EN/ES/ZH;
- MT pequeños directos para EN↔ES y ZH↔ES;
- objetivo de referencia Intel Core i3 Haswell 2C/4T, sin GPU;
- benchmark de end-to-end, P95 y RTF.

**Estado normativo actual:** laboratorio/código y tests preparados; **pesos finales no promocionados y benchmark físico en i3 real todavía obligatorio antes de llamarlo Stable**.

### Regla de promoción de modelos

Un modelo propio solo puede entrar al producto si:

1. pesos entrenados reales existen y son reproducibles;
2. licencia y procedencia de datos son compatibles con el canal comercial;
3. supera o empata la calidad crítica del baseline;
4. no empeora números, negaciones, nombres propios o términos clave;
5. cumple P50/P95/RTF del hardware objetivo;
6. pasa benchmark end-to-end, no solo métrica offline;
7. genera artefactos CT2/ONNX/otro formato requeridos por MilyCompute;
8. queda versionado, firmado/hashado y reversible.

La velocidad **forma parte de la calidad** de MilyVoice.

## 10. MilyCompute Foundation — obligatorio desde 1.0.5

MilyVoice no escribirá un driver gráfico/kernel propio. `MilyCompute` es una capa de orquestación de cómputo que utiliza APIs/runtimes existentes de Windows y del hardware.

Arquitectura objetivo:

`Hardware Probe → Backend Discovery → Compatibility Filter → Microbenchmark → Scoring → Model Router → Runtime Telemetry → Fallback`.

Componentes mínimos:

- Hardware Profiler.
- Backend Registry.
- Backend Selector.
- Benchmark Engine.
- Memory Budget/Manager.
- Model Router.
- Fallback Manager.

Backends reconocidos por arquitectura:

- CPU AVX/AVX2/AVX512/FMA cuando aplique.
- CUDA.
- Windows ML.
- DirectML.
- OpenVINO.
- Vulkan.
- ROCm/HIP cuando el hardware/OS realmente lo soporte.

**1.0.5 debe contener la fundación y detección/scoring; no es obligatorio que todos los modelos ejecuten ya en todos los backends.** Los backends no productivos deben reportarse como `detected/not-ready` en vez de fingir soporte funcional.

## 11. Hardware Profiler profesional

El profiler debe evolucionar más allá de un hint NVIDIA/CUDA.

CPU:

- fabricante/modelo;
- arquitectura;
- núcleos físicos;
- hilos lógicos;
- SSE4.2/AVX/AVX2/FMA/AVX512 cuando exista;
- RAM total/disponible;
- benchmark corto local.

GPU por dispositivo:

- Intel/AMD/NVIDIA/otro;
- nombre/modelo y, cuando sea posible, PCI/vendor/device ID;
- integrada/discreta;
- memoria dedicada y compartida cuando pueda consultarse de forma segura;
- DX12/DirectML capability;
- Vulkan capability;
- OpenVINO capability;
- CUDA capability;
- otros backends disponibles;
- benchmark únicamente si el backend puede ejecutarse realmente.

También debe registrar:

- dispositivos de audio relevantes;
- capacidad WASAPI/loopback;
- NPU/aceleradores cuando Windows los exponga de forma útil.

No se debe seleccionar backend solo por marca. Ejemplo válido: una Intel Iris puede existir pero perder contra CPU INT8; gana el backend medido.

## 12. Selección por benchmark, no por marca

Flujo obligatorio:

1. detectar hardware;
2. enumerar backends;
3. descartar incompatibles;
4. microbenchmark corto y cacheable;
5. medir ASR/MT latency, RTF y presión de memoria;
6. puntuar;
7. seleccionar por workload;
8. persistir recomendación con versión de hardware/driver/modelo;
9. invalidar benchmark cuando cambie un componente relevante.

Debe ser posible que ASR y MT usen backends distintos. El diseño debe permitir procesamiento híbrido CPU+iGPU/dGPU cuando los benchmarks lo justifiquen.

## 13. Traducción en tiempo real

Cadena objetivo:

`fuente de audio → PCM16/16 kHz → energy gate/VAD → ASR incremental → estabilización lingüística → MT → OutputBus → overlay/Desktop/TTS/sesión`.

La UI debe distinguir estados reales: `Capturando`, `Audio detectado`, `Silencio`, `Transcribiendo`, `Traduciendo`, `Hablando`, `Fuente perdida`, `No se detecta audio`, `CPU al límite`.

La cola no puede crecer indefinidamente. Bajo presión se reduce trabajo parcial antes de permitir atraso acumulativo.

## 14. Fuentes de audio aprobadas

- `browser_tab`: pestaña Chromium capturable.
- `system_loopback`: audio del sistema Windows por loopback.
- `microphone`: entrada seleccionada.
- `media_file`: reproductor interno para video/audio compatible.

La extensión debe funcionar más allá de Meet/Teams/Zoom: YouTube, Vimeo, cursos, radio web, reproductores HTML5 y cualquier página `http/https` capturable. Páginas protegidas del navegador se excluyen con mensaje explícito.

WASAPI nativo es la ruta principal para audio del sistema en Windows; selector protegido/WebView puede existir como fallback explícito, nunca como doble captura simultánea.

## 15. Subtítulos y transcripción

- Mostrar texto original y traducción.
- Original puede ocultarse.
- Transcripción parcial puede aparecer antes de la traducción final.
- Solo texto estable entra a MT para evitar retrabajo CPU.
- Overlay con Shadow DOM, independiente del DOM de la web.
- Vista Desktop con transcripción continua.
- Persistencia desactivada por defecto.

## 16. Video, audio y aprendizaje

Vista `Aprender con video/audio` con reproductor local y subtítulos sobre el contenido.

Modos:

- `Reunión`.
- `Educativo`.
- `Karaoke`.
- `Compacto`.

En karaoke se usan timestamps por palabra/fragmento cuando estén disponibles. En CPU débil se degrada de palabra a frase antes de sacrificar tiempo real.

Para EN/ES/ZH, las capas educativas futuras pueden mostrar pronunciación/pinyin sin contaminar la representación interna utilizada por ASR/MT.

## 17. Hablantes

- Identificar localmente `Hablante A/B/C…` mediante características/embeddings/clustering cuando se active.
- Mantener `speakerId` estable por sesión.
- Color estable por hablante.
- Modos `todos`, `dominante`, `fijado`.
- Permitir renombrar, priorizar, silenciar/reactivar o fijar speaker.
- No inferir género, edad ni identidad desde la voz.
- El usuario puede asignar a cada speaker una voz TTS instalada.

## 18. TTS y OutputBus

Modos mínimos:

- `Subtítulos`.
- `Subtítulos + voz`.
- `Solo voz`.

Requisitos:

- TTS local.
- Cola TTS separada de ASR/MT; no cancelar cada frase nueva de forma que se pierda una final válida.
- Voces instaladas de Windows/Chrome como primera implementación para no agregar otro modelo pesado.
- Ducking opcional/configurable del audio original.
- Anti-feedback sin dejar de escuchar al interlocutor: no apagar globalmente PCM mientras habla TTS.
- TTS nunca abre consola.

## 19. Temas y accesibilidad

Temas mínimos: `Mily azul`, `Oscuro cine`, `Clase clara`, `Alto contraste`, `Karaoke neón`.

Ajustes obligatorios: posición, tamaño, opacidad, mostrar/ocultar original y colores por speaker con contraste suficiente.

## 20. Sesiones y exportación

Solo con consentimiento:

- original, traducción, timestamps, speakerId y palabras opcionales;
- TXT bilingüe;
- SRT de traducción;
- SRT bilingüe;
- VTT bilingüe;
- cues por palabra cuando haya datos karaoke.

## 21. Optimización CPU — prioridad permanente

Antes de subir el tamaño de modelos:

1. detectar presupuesto de núcleos físicos;
2. asignar threads explícitos;
3. evitar sobresuscripción;
4. PCM binario por WebSocket;
5. energy gate + VAD;
6. ring buffer y ventanas adaptativas;
7. parciales estables;
8. ASR y MT desacoplados con colas limitadas;
9. beam 1 y decodificación acotada en realtime;
10. warm-up;
11. control `healthy/pressure/overloaded`;
12. métricas locales P50/P95/RTF;
13. nunca perder utterances finales ni acumular atraso monotónico;
14. degradar primero características opcionales antes de romper realtime.

## 22. Seguridad y privacidad

- Todo audio/transcripción/traducción/TTS local salvo descarga inicial de modelos.
- Native Messaging limitado a la extensión autorizada.
- Credenciales efímeras; no token/puerto manual en UX normal.
- Logs redactados.
- Sin `.env` reales, contraseñas, tokens, audio o transcripciones en Git.
- Descargas de modelos fijadas por revisión/hash y activación atómica.
- Los Model Labs no pueden publicar secretos/tokens de Hugging Face en Git, logs o chats.

## 23. Gates lingüísticos Tier 1

Para EN↔ES y ZH↔ES no basta con “el modelo responde”. Deben existir benchmarks reproducibles que incluyan según corresponda:

- WER/CER ASR;
- latencia P50/P95;
- RTF;
- números/fechas/cantidades;
- negaciones;
- nombres propios;
- preguntas y frases largas/cortas;
- habla rápida;
- ruido/micrófono mediocre;
- terminología empresarial, informática, automotriz, ventas, cursos y conversación cotidiana.

No se promociona un modelo si mejora una métrica offline pero rompe realtime.

## 24. Definition of Done 1.0.5

No marcar 1.0.5 como estable hasta pasar:

- consistencia de versión;
- source/privacy/extension/site guards;
- Python unit tests + compileall;
- frontend typecheck/tests/build;
- Rust fmt/tests/Clippy `-D warnings` Linux y Windows;
- runtime Python privado + SHA-256;
- bootstrap/bridge/Native Messaging instalado;
- Desktop Release Windows;
- verificación PE `WINDOWS_GUI`;
- NSIS generado e instalado realmente;
- extensión ZIP;
- SHA256SUMS;
- prueba real del pack estable antes de promoción;
- pruebas funcionales de browser_tab, system_loopback, microphone y media_file;
- speakers, TTS, anti-feedback, educativo/karaoke y exportación;
- fundación MilyCompute y Hardware Profiler sin depender solo de hints CUDA;
- detección/reporting seguro de CPU/CUDA/DirectML/Vulkan/OpenVINO aunque algunos backends sigan `not-ready`;
- arquitectura/protocolo preparados para los cuatro fast paths Tier 1;
- al menos EN→ES y ZH→ES no pueden degradarse respecto al baseline funcional;
- las rutas ES→EN y ES→ZH deben quedar funcionales o, si un gate externo impide su promoción, permanecer explícitamente bloqueadas como requisito de release y no ocultarse como “soportadas”.

Solo después: merge `pruebas → main`, repetir CI sobre `main`, publicar artefactos y entregar EXE/ZIP/hash.

## 25. Roadmap vinculante

### 1.0.5

- cierre realtime multimodal actual;
- MilyCompute Foundation;
- Hardware Profiler profesional;
- CPU/CUDA actuales + discovery de DirectML/Vulkan/OpenVINO/Windows ML;
- benchmark/scoring/fallback foundation;
- ES/EN/ZH como Tier 1;
- arquitectura de cuatro fast paths;
- gobierno Quality/Legacy de modelos.

### 1.1

- ejecución real DirectML/Windows ML para workloads aprobados;
- Intel OpenVINO real cuando gane benchmark;
- Vulkan ASR donde corresponda;
- perfiles lingüísticos completos EN↔ES y ZH↔ES;
- Model Advisor visible al usuario;
- routing híbrido por workload.

### 1.2

- full duplex;
- voz↔voz bidireccional;
- virtual microphone/output routing;
- dos direcciones simultáneas con control de eco y presupuesto de cómputo.

### 1.3

- tutor de idiomas;
- fonética/pronunciación avanzada;
- pinyin educativo;
- correcciones y ejercicios;
- seguimiento local de aprendizaje con consentimiento.

## 26. Coordinación entre chats/agentes

La división actual está en `docs/WORKSTREAMS.md` y es obligatoria para evitar conflictos.

Principio:

- **Workstream Plataforma/Arquitectura:** MASTER, MilyCompute, hardware profiler, backend registry/scoring, protocolo/abstracción de idiomas, gobierno de modelos y gates.
- **Workstream Realtime/UX:** Desktop/extensión, fuentes de audio, speakers, karaoke, TTS/ducking, accesibilidad, exportación y pruebas funcionales/NSIS.

Antes de modificar un archivo compartido, cada chat debe leer el último SHA de `pruebas`. Si un archivo pertenece temporalmente al otro workstream, no se sobrescribe: se documenta la necesidad y se coordina mediante `docs/WORKSTREAMS.md`.

## 27. Política de trabajo

- TDD: prueba que falla → implementación mínima → prueba verde → commit.
- No ocultar deuda técnica ni marcar una fase completa si el gate real no pasó.
- No degradar privacidad para ganar rendimiento.
- No sacrificar utterances finales para bajar latencia.
- No cambiar el modelo estable solo porque exista un experimento nuevo.
- Ningún modelo propio se llama “entrenado”, “estable” o “production” sin pesos y benchmarks reales.
- Seleccionar backend por benchmark, no por marca.
- `main` siempre debe permanecer funcional.
