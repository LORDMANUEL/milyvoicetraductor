# MilyVoiceTraductor 2.1 — Tier 1 bidireccional

## Objetivo

Cerrar la fase 2.1 haciendo ejecutables las cuatro rutas Tier 1 ya declaradas por la arquitectura:

- EN→ES
- ZH→ES
- ES→EN
- ES→ZH

La fase conserva 2.0.2 como estable pública y 2.1.0 como beta hasta que el mismo SHA pase sus gates completos. No incluye full-duplex, micrófono virtual ni Tutor 2.3.

## Estado de partida

`languages.py` ya define las cuatro rutas, pero el protocolo WebSocket, Desktop y extensión fijan `targetLanguage=es`. El pipeline detecta únicamente inglés/mandarín. El pack Quality `realtime-m2m100` ya contiene Whisper Small + M2M100 CT2 INT8, pero declara solo EN→ES y ZH→ES.

## Diseño

### 1. Contrato de ruta

`ClientMessage` aceptará `sourceLanguage` en `auto|en|es|zh` y `targetLanguage` en `es|en|zh`, pero solo permitirá combinaciones Tier 1. `auto` solo se admitirá cuando el destino sea `es`, porque el detector actual distingue EN/ZH; las rutas salientes desde español requieren `sourceLanguage=es` explícito.

La validación usará `languages.get_tier1_route()` para evitar duplicar reglas entre protocolo, servidor y UI.

### 2. Selección y compatibilidad del pack

Antes de iniciar una sesión, el servidor construirá `route_id = <source>-<target>` y exigirá que el pack activo declare esa ruta. Si no la declara, responderá `MODEL_ROUTE_UNSUPPORTED` y pedirá optimización/cambio de pack.

`realtime-m2m100` ampliará sus rutas a las cuatro Tier 1. Los perfiles Lite actuales se mantienen EN→ES/ZH→ES y no se anunciarán falsamente como bidireccionales.

### 3. ASR español

Faster-Whisper aceptará `es` como idioma configurado/detectado. El lock automático seguirá restringido a idiomas que el detector pueda fijar de forma confiable para esa sesión. Para `sourceLanguage=es`, se fuerza español y no se ejecuta detección automática.

### 4. MT con destino dinámico

El traductor M2M100 recibirá `target_language` al construirse. La traducción usará el token de destino correspondiente (`es`, `en` o `zh`) en vez de fijar español. La caché incluirá el destino implícitamente porque cada instancia pertenece a una única ruta/sesión.

Marian continúa siendo direccional por su propio manifiesto; sus packs no cambian.

### 5. Pipeline

`RealtimePipeline` recibirá `target_language`. La detección interna admitirá español cuando esté configurado. `SessionRecorder` ya registra source/target, por lo que el servidor pasará ambos valores reales.

### 6. Desktop

Desktop añadirá selector de destino `Español/Inglés/Chino`. Si el destino no es español, el origen quedará restringido a español para esta fase. Si el origen está en `auto`, el destino solo puede ser español. El cliente WebSocket propagará el destino en hello, audio chunks y stop.

TTS dejará de asumir español: elegirá voz e idioma por `targetLanguage` (`es-ES`, `en-US`, `zh-CN`) y filtrará las voces locales por prefijo del idioma destino.

### 7. Extensión

El popup añadirá destino seleccionable con las mismas reglas de compatibilidad. Background y offscreen propagarán `targetLanguage` en toda la sesión. TTS de la extensión elegirá idioma/voz según el destino guardado.

El modo Tutor sigue degradándose a `education`; no se amplía en 2.1.

## Errores públicos

- `ROUTE_UNSUPPORTED`: combinación de idiomas fuera de Tier 1.
- `MODEL_ROUTE_UNSUPPORTED`: el pack activo no ejecuta la ruta pedida.
- Los errores existentes de modelo/runtime permanecen sin exponer rutas locales o secretos.

## Pruebas / Definition of Done

El mismo candidato debe demostrar:

1. protocolo acepta exactamente las cuatro rutas Tier 1;
2. `auto→es` continúa válido y `auto→en/zh` se rechaza;
3. M2M100 usa token de destino dinámico;
4. Faster-Whisper acepta español explícito;
5. pipeline conserva source/target reales;
6. servidor rechaza un pack incompatible antes del warm-up;
7. `realtime-m2m100` declara las cuatro rutas y ningún Lite recibe rutas no verificadas;
8. Desktop transmite destino dinámico en hello/chunk/stop;
9. extensión transmite destino dinámico en popup/background/offscreen;
10. TTS Desktop/extensión selecciona idioma de salida según destino;
11. tests Python, frontend typecheck/tests/build y preflight de `pruebas` quedan verdes;
12. la promoción a `main` solo ocurre después de CI completo sobre el SHA final.

## Fuera de alcance

- full-duplex simultáneo;
- micrófono virtual;
- interrupción/barge-in;
- Tutor completo, fonética/pinyin/ejercicios;
- promover DirectML/OpenVINO/Vulkan si el adapter no ejecuta realmente el modelo;
- afirmar perfil 2 GB para ES→EN/ES→ZH mientras solo exista el carril Quality M2M100.