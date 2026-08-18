# MilyVoiceTraductor 1.0.5 — Audio universal, karaoke educativo y voz en tiempo real

## Estado base

La implementación parte del commit verde `6f5cd6242472ce0ff760632e18c917a9d844642e` en `pruebas`, donde ya están validados: aplicación Tauri 1.0.5, runtime Python privado, modelo `realtime-m2m100`, subtítulos superpuestos en Meet/Teams/Zoom, ausencia de consola negra, CI Linux/Windows, NSIS e instalación real.

`main` no recibirá este alcance hasta que la nueva candidata vuelva a superar CI completo, verificación de subsistema GUI, NSIS instalado, extensión empaquetada y pruebas funcionales específicas de audio/subtítulos/voz.

## Objetivo

Convertir MilyVoiceTraductor en un traductor local universal para reuniones, videos, clases, cursos, canciones, micrófono y audio del sistema, con baja latencia en CPU, subtítulos bilingües, modo educativo tipo karaoke, múltiples hablantes con colores estables y síntesis de voz española opcional.

## Principios obligatorios

- Todo procesamiento de audio, transcripción, traducción, diarización y síntesis se ejecuta localmente salvo la descarga inicial de modelos fijados por versión/hash.
- El producto debe funcionar sin GPU; si existe CUDA se aprovechará automáticamente.
- La aplicación y los procesos auxiliares nunca deben abrir una consola visible en Windows.
- La UI debe mostrar estados reales: `Capturando`, `Audio detectado`, `Silencio`, `Transcribiendo`, `Traduciendo`, `Hablando`, `Fuente perdida` y errores accionables.
- La latencia no puede crecer sin límite. Las colas tendrán presupuesto máximo y compactarán/descartarán trabajo obsoleto antes de quedar varios segundos atrás.
- No se inferirá automáticamente el género de una persona a partir de su voz. Los hablantes se etiquetarán como `Hablante A`, `Hablante B`, etc. Cada hablante conservará color e identidad acústica; el usuario podrá asignarle una voz TTS masculina, femenina o neutra de forma manual.
- El pack de traducción actual `realtime-m2m100` seguirá siendo el default. No se sustituirá por otro modelo como solución rápida de rendimiento antes de optimizar el pipeline.

## Descomposición en cuatro subproyectos

### A. Motor CPU de baja latencia

El pipeline actual de ventanas rígidas de 2 s pasará a una arquitectura incremental con tres etapas desacopladas:

1. `AudioIngress`: recibe PCM mono y mantiene un ring buffer.
2. `AsrWorker`: procesa ventanas adaptativas de aproximadamente 0.8–1.2 s en modo conversación, con VAD previo y contexto solapado corto. Emite texto parcial y texto estable.
3. `TranslationWorker`: traduce únicamente texto estable; usa caché, cola limitada y procesa en paralelo mientras ASR escucha el siguiente bloque.
4. `OutputBus`: distribuye eventos a overlay, transcripción Desktop, grabador de sesión y TTS.

El motor detectará núcleos lógicos/físicos y aplicará perfiles `ligero`, `balanceado` y `maxima-velocidad`. CTranslate2/Whisper configurarán threads según ese perfil en lugar de usar valores estáticos.

Se medirán localmente `audio_queue_ms`, `asr_ms`, `translation_ms`, `tts_queue_ms`, `real_time_factor` y `cpu_profile`. Estas métricas no salen del equipo.

### B. Captura universal y salud de audio

Se soportarán cuatro fuentes:

- `browser_tab`: pestaña activa de Chrome/Edge mediante `chrome.tabCapture`.
- `system_loopback`: audio reproducido por Windows mediante WASAPI loopback desde el Desktop.
- `microphone`: entrada seleccionada por el usuario.
- `media_file`: audio de un reproductor HTML5 interno para archivos compatibles de video/audio.

La extensión dejará de limitarse a Meet/Teams/Zoom. Permitirá cualquier pestaña `http/https` capturable por Chromium, incluyendo YouTube, Vimeo, cursos, radio web y reproductores HTML5. Seguirán excluidas páginas protegidas del navegador (`chrome://`, Web Store y equivalentes).

Cada fuente publicará RMS/peak y timestamp de última muestra. Si la sesión está activa pero no entra señal útil durante un umbral configurable, la UI mostrará `No se detecta audio`. En navegador se ofrecerá fallback a `Audio del sistema` cuando la pestaña no entregue señal.

### C. Hablantes, colores y voz española

El modo multihablante usará VAD + embeddings de voz + clustering online. Para no hacer pesada la instalación base, el modelo de embeddings será un componente local pequeño y separado que se descargará únicamente cuando el usuario active `Identificar hablantes`.

El sistema emitirá `speakerId` estable (`speaker-a`, `speaker-b`, ...). Cada speaker tendrá:

- color de subtítulo estable;
- nombre editable por el usuario;
- voz TTS asignada de forma estable;
- opción `silenciar`, `priorizar` o `fijar hablante`.

Modos de foco:

- `todas`: transcribe/traduce todos los hablantes detectados;
- `dominante`: prioriza el speaker con continuidad acústica predominante;
- `fijado`: procesa solo el speaker elegido salvo que el usuario cambie el foco.

La síntesis en español será opcional y local. La primera implementación usará las voces instaladas de Windows mediante API nativa para evitar otro modelo pesado. La UI permitirá elegir voz por hablante; cuando existan varias voces, MilyVoice asignará perfiles distintos automáticamente sin etiquetar el género de las personas.

El TTS tendrá cola propia, ducking opcional del audio original y protección anti-feedback: el audio sintetizado por MilyVoice no debe volver a entrar al ASR como si fuera un participante.

### D. Video, canciones, karaoke educativo y temas

El Desktop incluirá una vista `Aprender con video/audio` con selector de archivo y reproductor HTML5. Formatos soportados serán los que WebView2/Windows pueda decodificar de forma nativa (p. ej. MP4/WebM/MP3/WAV/M4A cuando el codec esté disponible). Los formatos no compatibles mostrarán un error explícito; no se bundleará FFmpeg en esta fase.

Modos visuales:

- `Reunión`: español principal, original pequeño arriba o debajo.
- `Educativo`: traducción española principal y frase original inglesa debajo.
- `Karaoke`: frase española + línea original; la palabra/fragmento original activo se resalta sincronizado con timestamps.
- `Compacto`: una sola línea para pantallas pequeñas.

El modo karaoke activará `word_timestamps` únicamente cuando sea necesario. En CPU lenta podrá degradar automáticamente a resaltado por frase para proteger la latencia.

Para canciones se añadirá `music_mode`, que usa ventanas más largas que conversación, conserva más contexto y desactiva decisiones agresivas de VAD cuando detecte música continua. El objetivo es ayudar a seguir letras/frases y su traducción durante reproducción; la precisión dependerá de cuán separada esté la voz de la música.

Temas visuales incluidos:

- `Mily azul` (actual);
- `Oscuro cine`;
- `Clase clara`;
- `Alto contraste`;
- `Karaoke neón`.

Los colores de hablante se aplicarán sobre cada tema mediante tokens CSS para conservar contraste AA. El usuario podrá mover el overlay entre `arriba`, `centro inferior`, `abajo` y ajustar tamaño/opacidad.

## Protocolo de eventos

El WebSocket local conservará `protocol: 1` para mensajes existentes y ampliará eventos de salida sin romper consumidores actuales:

- `audio.level { rms, peak, source, silentMs }`
- `transcription.partial { text, language, speakerId, start, end }`
- `transcription.final { original, language, speakerId, start, end, words? }`
- `translation.final { original, translation, speakerId, start, end, words? }`
- `tts.started { speakerId, start, end }`
- `tts.finished { speakerId, start, end }`
- `pipeline.metrics { audioQueueMs, asrMs, translationMs, ttsQueueMs, realTimeFactor }`

Los eventos actuales `engine.ready`, `engine.loading`, `session.started`, `session.finished` y `translation.final` seguirán siendo compatibles.

## Sesiones y exportación

Cuando el usuario habilite persistencia, cada segmento guardará `speakerId`, original, español, timestamps y opcionalmente palabras. Las exportaciones incluirán:

- TXT bilingüe;
- SRT español;
- SRT bilingüe;
- VTT bilingüe.

En modo karaoke, VTT podrá incluir spans/cues por palabra cuando existan timestamps de palabra.

## UX de inicio

El inicio de sesión en Desktop o extensión mostrará:

1. fuente seleccionada;
2. nivel de audio en vivo;
3. estado del motor/modelo;
4. idioma origen/destino;
5. foco de hablante;
6. modo visual;
7. TTS apagado/encendido;
8. latencia actual.

No se mostrará `Traduciendo` hasta que se haya recibido audio útil y exista una sesión activa.

## Pruebas de aceptación

### Rendimiento CPU

- Audio inglés continuo de habla rápida durante al menos 3 minutos.
- La cola no debe crecer de forma monotónica.
- Se registrará P50/P95 de ASR y traducción.
- La UI debe seguir respondiendo mientras ASR y traducción trabajan.

### Captura

- Meet/Teams/Zoom siguen funcionando.
- Una pestaña genérica con video/audio produce subtítulos.
- Fuente sin audio muestra `No se detecta audio`.
- WASAPI loopback captura audio de una app externa en Windows.
- Micrófono produce transcripción y traducción.

### Hablantes/TTS

- Audio de dos speakers alternados produce dos `speakerId` estables y colores distintos.
- `fijar hablante` ignora segmentos del speaker no seleccionado.
- Asignar dos voces TTS distintas conserva la misma voz por speaker.
- El TTS no se reinyecta al ASR.
- El ducking reduce y restaura el audio original sin bloquear la captura.

### Video/canción/karaoke

- Archivo MP4 compatible reproduce audio y genera subtítulos dentro del Desktop.
- Archivo MP3 compatible genera traducción mientras se reproduce.
- Modo educativo muestra español + inglés.
- Modo karaoke resalta palabra/fragmento según timestamps sin bloquear el reproductor.
- Tema/color/posición cambian sin reiniciar la sesión.

### Release

- `npm run typecheck`, tests frontend y build.
- tests Python completos.
- `cargo test --workspace` Linux/Windows.
- `cargo clippy --workspace --all-targets -- -D warnings`.
- Release Windows con `IMAGE_SUBSYSTEM_WINDOWS_GUI`.
- NSIS 1.0.5 generado e instalado realmente.
- Extensión ZIP y SHA256 verificados.
- Solo después de lo anterior: merge a `main`, CI de `main` con prueba de modelo real y publicación del artefacto final.

## Fuera de alcance de esta iteración

- Inferir género, edad, identidad u otros atributos sensibles desde la voz.
- Clonación de voz de participantes.
- Traducción a destinos distintos de español.
- Servicio cloud obligatorio.
- Bundlear FFmpeg o un modelo pesado de separación musical en el instalador base.
- Cambiar M2M100/Whisper por otro stack antes de medir el pipeline optimizado.
