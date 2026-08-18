# MilyVoiceTraductor 2.0.0

MilyVoice 2.0 es un salto de arquitectura y rendimiento. La versión se publica únicamente desde un SHA que haya superado el pipeline completo de CI, MegaBench con modelos reales, Windows GUI, NSIS e instalación real.

## Principales cambios

- pipeline realtime CPU-first con PCM binario, ventanas adaptativas, parciales estables, backpressure y warm-up;
- audio de pestaña Chromium, micrófono, media local y audio del sistema Windows;
- WASAPI loopback con fallback protegido;
- modos Reunión, Educativo, Karaoke y Compacto;
- speakerId local A/B/C, colores, foco, TTS y exportación bilingüe;
- TTS local con ducking y anti-feedback sin cortar deliberadamente el PCM entrante;
- TXT/SRT/VTT y datos de timestamps/speaker cuando estén disponibles;
- MilyCompute Foundation: CPU fallback, registry de backends, selección por medición y detección conservadora de aceleradores;
- Hardware Advisor y base para CPU/CUDA/DirectML/OpenVINO/Vulkan sin sobreafirmar soporte de adaptadores no implementados;
- EN, ES y ZH como idiomas Tier 1 de arquitectura;
- MegaBench 2.0 incluido como artefacto verificable.

## Modelos

El baseline estable de esta versión continúa utilizando Whisper Small + M2M100 CTranslate2 INT8. Los laboratorios TriCore/Quality y Legacy CPU siguen siendo R&D: no se promocionan automáticamente hasta disponer de pesos reales, procedencia/licencia validada y benchmarks de promoción.

EN→ES y ZH→ES son los smoke receptores reales obligatorios de 2.0. ES→EN y ES→ZH permanecen Tier 1 de arquitectura y deben superar sus propios gates antes de anunciarse como una experiencia bidireccional cerrada.

## MegaBench

El artefacto `MilyVoiceTraductor-2.0.0-MegaBench.json` incluye:

- ASR P50/P95;
- ASR RTF P50/P95;
- MT EN→ES P50/P95;
- MT ZH→ES P50/P95;
- end-to-end P95 estimado;
- resultado PASS/FAIL del gate de regresión Windows CI;
- identificación del modelo y entorno.

Este benchmark del runner CI sirve para detectar regresiones de la candidata. No sustituye el benchmark físico obligatorio del futuro perfil Legacy sobre Intel Core i3 Haswell real.

## Archivos del release

- `MilyVoiceTraductor_2.0.0_x64-setup.exe`
- `MilyVoiceTraductor-Chromium-Extension.zip`
- `MilyVoiceTraductor-2.0.0-MegaBench.json`
- `SHA256SUMS.txt`

Todos deben provenir del mismo SHA verificado.
