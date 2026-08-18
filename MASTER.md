# MilyVoiceTraductor 1.0.5 — MASTER

Este documento es el punto de entrada y la fuente operativa del proyecto. Reúne las instrucciones y requisitos aprobados para que el alcance no vuelva a quedar disperso entre conversaciones, commits o fases.

## 1. Objetivo del producto

MilyVoiceTraductor es una aplicación Windows local para escuchar audio, transcribirlo, traducirlo al español y mostrar el resultado como subtítulos y, opcionalmente, voz sintetizada en tiempo real. Debe funcionar sin GPU y cubrir reuniones, pestañas web, videos, cursos, canciones, micrófono, audio del sistema y archivos multimedia compatibles.

## 2. Documentos normativos

- Especificación maestra completa: `docs/superpowers/specs/2026-08-18-milyvoice-1.0.5-master-spec.md`.
- Diseño de audio universal/karaoke/TTS/hablantes: `docs/superpowers/specs/2026-08-18-realtime-universal-audio-karaoke-design.md`.
- Plan de optimización CPU: `docs/superpowers/plans/2026-08-18-cpu-realtime-optimization.md`.
- Diseño de onboarding/runtime embebido: `docs/superpowers/specs/2026-08-17-automatic-onboarding-embedded-runtime-design.md`.

Si existe una discrepancia, prevalece este orden: especificación maestra 1.0.5 → diseño especializado → plan de implementación → documentación histórica.

## 3. Regla de ramas

- `main`: versión estable/publicable. No se programa directamente aquí.
- `pruebas`: desarrollo, tests, RC y correcciones.
- No crear ramas efímeras como flujo normal salvo necesidad extraordinaria.
- Solo fusionar `pruebas` a `main` después de CI completo, instalación NSIS real y pruebas funcionales del alcance aprobado.

## 4. Versión

Toda la cadena debe declarar `1.0.5`: `VERSION`, Cargo, Node, Tauri, motor, workflows, release, artefactos e instalador. CI debe fallar ante cualquier desalineación.

## 5. Instalación Windows — requisito obligatorio SIN CMD

El usuario instala una sola aplicación gráfica. No debe ver ni depender de ventanas `cmd.exe`, PowerShell, consola de Python o terminal auxiliar.

Gates obligatorios:

- `MilyVoiceTraductor.exe` debe ser `IMAGE_SUBSYSTEM_WINDOWS_GUI`.
- Procesos Python de motor, descarga, conversión y reparación se lanzan con `CREATE_NO_WINDOW` en Windows.
- El bridge/Native Messaging no abre terminal visible.
- NSIS silencioso no muestra `MessageBox` ni lanza procesos interactivos.
- El runtime Python 3.13 es privado y se instala con la aplicación; el usuario no instala Python, `winget`, pip ni venv.
- El modelo se prepara desde la UI después de abrir la app; NSIS no descarga gigabytes de IA durante instalación.
- La descarga/conversión del modelo debe mostrarse dentro de la app por fases: descarga ASR → descarga traducción → conversión INT8 → verificación → activación.
- Cerrar una supuesta ventana de terminal nunca puede matar la app porque esa ventana no debe existir.

## 6. Pack IA principal

Default comercial: `realtime-m2m100`.

- ASR: `Systran/faster-whisper-small`, snapshot fijado por commit.
- Traducción: `facebook/m2m100_418M`, snapshot fijado por commit.
- M2M100 se convierte localmente una sola vez a CTranslate2 INT8.
- CPU INT8 es ruta de primera clase.
- CUDA es opcional y se usa automáticamente si existe.
- No reemplazar este stack antes de medir la optimización CPU aprobada.

## 7. Traducción en tiempo real

Cadena objetivo:

`fuente de audio → PCM16/16 kHz → energy gate/VAD → ASR incremental → estabilización → traducción → OutputBus → overlay/Desktop/TTS/sesión`.

La UI debe distinguir estados reales: `Capturando`, `Audio detectado`, `Silencio`, `Transcribiendo`, `Traduciendo`, `Hablando`, `Fuente perdida`, `No se detecta audio`, `CPU al límite`.

La cola no puede crecer indefinidamente. Bajo presión se reduce trabajo parcial antes de permitir atraso acumulativo.

## 8. Fuentes de audio aprobadas

- `browser_tab`: pestaña Chromium capturable.
- `system_loopback`: audio del sistema Windows por loopback.
- `microphone`: entrada seleccionada.
- `media_file`: reproductor interno para video/audio compatible.

La extensión debe funcionar más allá de Meet/Teams/Zoom: YouTube, Vimeo, cursos, radio web, reproductores HTML5 y cualquier página `http/https` capturable. Páginas protegidas del navegador se excluyen con mensaje explícito.

## 9. Subtítulos y transcripción

- Mostrar texto original y español.
- Original puede ocultarse.
- Transcripción parcial puede aparecer antes de la traducción final.
- Solo texto estable entra a traducción para evitar retrabajo CPU.
- Overlay con Shadow DOM, independiente del DOM de la web.
- Vista Desktop con transcripción continua.
- Persistencia desactivada por defecto.

## 10. Video, audio y canciones para aprendizaje

Vista `Aprender con video/audio` con reproductor local y subtítulos sobre el contenido.

Modos:

- `Reunión`: español principal + original secundario.
- `Educativo`: español principal + inglés debajo para aprender.
- `Karaoke`: español + frase inglesa sincronizada; resaltar palabra/fragmento cuando haya timestamps.
- `Compacto`: una línea para pantallas pequeñas.

`music_mode` usa más contexto y VAD menos agresivo. En CPU débil el karaoke degrada de palabra a frase antes de sacrificar tiempo real.

## 11. Hablantes

- Identificar localmente `Hablante A/B/C…` mediante embeddings/clustering cuando se active la función.
- Mantener `speakerId` estable por sesión.
- Color estable por hablante.
- Modos `todas`, `dominante`, `fijado`.
- Permitir renombrar, priorizar, silenciar o fijar speaker.
- No inferir género, edad ni identidad desde la voz.
- El usuario puede asignar a cada speaker una voz TTS masculina, femenina o neutra.

## 12. Voz española en tiempo real

Modos: `Subtítulos`, `Subtítulos + voz`, `Solo voz`.

- TTS local.
- Cola TTS separada de ASR/traducción.
- Voces instaladas de Windows como primera implementación para no agregar otro modelo pesado.
- Ducking opcional del audio original.
- Anti-feedback para que la voz sintetizada no vuelva a entrar al ASR.
- TTS nunca abre consola.

## 13. Temas y accesibilidad

Temas mínimos: `Mily azul`, `Oscuro cine`, `Clase clara`, `Alto contraste`, `Karaoke neón`.

Ajustes: posición, tamaño, opacidad, mostrar/ocultar original y colores por speaker con contraste suficiente.

## 14. Sesiones y exportación

Solo con consentimiento:

- original, español, timestamps, speakerId y palabras opcionales;
- TXT bilingüe;
- SRT español;
- SRT bilingüe;
- VTT bilingüe;
- cues por palabra cuando haya datos karaoke.

## 15. Optimización CPU — prioridad inmediata

Antes de cambiar modelos:

1. detectar presupuesto de núcleos físicos;
2. asignar `cpu_threads` a Faster-Whisper y `intra_threads` a M2M100;
3. evitar sobresuscripción;
4. pasar PCM binario por WebSocket para sacar Base64/JSON del camino caliente;
5. energy gate + Silero VAD;
6. ring buffer y ventanas adaptativas ~0.8–1.2 s para conversación;
7. hipótesis parciales estables;
8. ASR y traducción desacoplados con colas limitadas;
9. M2M100 `beam_size=1`, sin scores y longitud de decodificación acotada;
10. warm-up antes del primer audio útil;
11. control `healthy/pressure/overloaded`;
12. métricas locales P50/P95 y RTF;
13. nunca perder utterances finales ni acumular atraso monotónico.

## 16. Seguridad y privacidad

- Todo audio/transcripción/traducción/TTS local salvo descarga inicial de modelos.
- Native Messaging limitado a la extensión autorizada.
- Credenciales efímeras; no token/puerto manual en UX normal.
- Logs redactados.
- Sin `.env` reales, contraseñas, tokens, audio o transcripciones en Git.
- Descargas de modelos fijadas por revisión/hash y activación atómica.

## 17. Definition of Done / Release gates

No marcar una versión como terminada hasta pasar:

- consistencia de versión 1.0.5;
- source/privacy/extension/site guards;
- Python unit tests + compileall;
- frontend typecheck/tests/build;
- Rust fmt/tests/Clippy `-D warnings` Linux y Windows;
- runtime Python privado + SHA-256;
- bootstrap/bridge/Native Messaging instalado;
- Desktop Release Windows;
- verificación PE `WINDOWS_GUI`;
- NSIS 1.0.5 generado;
- instalación real del NSIS generado;
- extensión ZIP;
- SHA256SUMS;
- prueba real del pack en `main`;
- pruebas funcionales: audio → transcripción → traducción → overlay, CPU rápida, pestaña genérica, loopback, micrófono, media_file, hablantes, TTS, anti-feedback, educativo/karaoke y exportación.

Solo después: merge a `main`, repetir CI en `main`, publicar artefacto y entregar EXE/ZIP/hash.

## 18. Política de trabajo

- TDD: prueba que falla → implementación mínima → prueba verde → commit.
- No ocultar deuda técnica ni marcar una fase completa si el gate real no pasó.
- No degradar privacidad para ganar rendimiento.
- No sacrificar utterances finales para bajar latencia.
- No cambiar modelo antes del benchmark del stack actual.
- `main` siempre debe permanecer funcional.
