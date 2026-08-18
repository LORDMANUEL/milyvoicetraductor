<p align="center">
  <img src="apps/site/assets/logo.svg" alt="MilyVoiceTraductor" width="150" />
</p>

<h1 align="center">MilyVoiceTraductor 2.0</h1>

<p align="center"><strong>Voz, subtítulos y traducción local en tiempo real para español, inglés y chino mandarín.</strong></p>

<p align="center">
  Reuniones, pestañas web, audio del sistema, micrófono, videos, cursos y karaoke con runtime privado, selección adaptativa de cómputo y procesamiento local.
</p>

<p align="center">
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.0/MilyVoiceTraductor_2.0.0_x64-setup.exe"><img alt="Descargar para Windows" src="https://img.shields.io/badge/Windows_2.0.0-00A878?style=for-the-badge&logo=windows11&logoColor=white"></a>
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.0/MilyVoiceTraductor-Chromium-Extension.zip"><img alt="Extensión Chromium" src="https://img.shields.io/badge/Extensión_Chromium-1769E0?style=for-the-badge&logo=googlechrome&logoColor=white"></a>
</p>

<p align="center">
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.0.0">Ver release 2.0.0</a>
  ·
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.0/SHA256SUMS.txt">Verificar SHA-256</a>
  ·
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.0/MilyVoiceTraductor-2.0.0-MegaBench.json">MegaBench</a>
</p>

> **Candidata actual: 2.0.0 RC.** La rama `pruebas` no se declara Stable hasta que el mismo SHA supere tests Python/Frontend/Rust, Clippy, MegaBench con modelos reales, Windows GUI, NSIS e instalación real. El release público v2.0.0 solo se publica desde `main` después de esos gates.

## Qué cambia en 2.0

MilyVoice 2.0 es un salto de arquitectura, no un simple cambio de número:

- **CPU realtime optimizada:** presupuesto por núcleos físicos, INT8, ventanas adaptativas, energy gate, parciales estables, ASR/MT desacoplados, backpressure y warm-up.
- **MilyCompute Foundation:** CPU siempre disponible y registro/selección conservadora de CUDA, DirectML, OpenVINO y Vulkan. Detectar un runtime no significa afirmar que el adaptador del modelo ya esté listo.
- **Hardware Advisor:** topología CPU real, características AVX/AVX2/FMA/AVX512 cuando existan y base para selección por benchmark, no por marca.
- **Audio universal:** pestaña Chromium, micrófono, archivo multimedia y audio del sistema con WASAPI loopback/fallback protegido.
- **Multimodal realtime:** subtítulos, educativo, karaoke, múltiples hablantes, TTS local, ducking y sesiones exportables.
- **MegaBench 2.0:** P50/P95, RTF y smoke con Whisper Small + M2M100 reales en Windows antes de empaquetar el artefacto.

## Idiomas Tier 1

La prioridad del producto se mantiene clara:

```text
voz EN → ASR EN → MT EN→ES → texto/voz ES
voz ZH → ASR ZH → MT ZH→ES → texto/voz ES
voz ES → ASR ES → MT ES→EN → texto/voz EN
voz ES → ASR ES → MT ES→ZH → texto/voz ZH
```

**EN→ES y ZH→ES son los caminos receptores prioritarios** para reuniones, videos y cursos. ES→EN y ES→ZH son Tier 1 de la arquitectura bidireccional y solo se anuncian como funcionales cuando el protocolo/router correspondiente haya superado sus gates.

ASR significa voz→texto; MT realiza la traducción entre idiomas.

## Modelo estable y Model Labs

El baseline de producción continúa siendo:

```text
Systran/faster-whisper-small
        ↓
ASR local CTranslate2
        ↓
facebook/m2m100_418M
        ↓
CTranslate2 INT8
```

No se sustituyen esos pesos automáticamente por experimentos.

- **TriCore / Quality:** trainers, evaluación y exportación preparados; los pesos fine-tuned no se consideran promocionados hasta existir y superar los gates.
- **Legacy CPU:** laboratorio para Whisper Tiny + MT pequeño INT8 con objetivo i3 Haswell; no se considera Stable sin pesos finales y benchmark físico en ese hardware.

El MegaBench del runner GitHub detecta regresiones de 2.0, pero **no sustituye el benchmark físico Legacy**.

## Instalación Windows sin terminal

El usuario ejecuta un único instalador gráfico. El paquete incluye:

- Desktop Tauri/Rust;
- Python 3.13 x64 privado;
- dependencias del motor;
- motor local;
- bridge Native Messaging;
- extensión Chromium;
- diagnóstico/reparación;
- registro local necesario para auto-reconocimiento.

No requiere instalar Python, `winget`, pip o un venv manualmente. Los pesos del modelo se descargan desde Hugging Face durante la preparación visual de la aplicación y se verifican antes de activarse.

## Fuentes y modos

**Fuentes:**

- cualquier pestaña `http/https` capturable en Chrome/Edge/Brave/Chromium;
- micrófono;
- audio del sistema Windows;
- MP4/WebM/MP3/WAV/M4A y otros formatos que soporte el reproductor interno.

**Vistas:**

- Reunión;
- Educativo;
- Karaoke;
- Compacto.

**Salida:**

- Subtítulos;
- Subtítulos + voz;
- Solo voz.

Cuando se activa identificación local de hablantes, se usan etiquetas efímeras `Hablante A/B/C…`, colores estables y voces TTS asignables. No se infiere género, edad o identidad.

## Privacidad

El hot path permanece local:

```text
audio → 127.0.0.1 → ASR → MT → subtítulos/TTS/sesión
```

- sin telemetría de conversación;
- persistencia desactivada por defecto;
- Native Messaging limitado a la extensión autorizada;
- credenciales locales efímeras;
- modelos por revisión fijada y activación atómica;
- sin tokens, contraseñas, audio o transcripciones dentro de Git.

## MegaBench y Definition of Done

Un ZIP de 2.0 solo es entregable cuando el **mismo SHA** produce:

1. Python unit tests + `compileall`;
2. stress de colas/backpressure/telemetría/CPU;
3. Frontend typecheck/tests/build;
4. `cargo fmt`, workspace tests y Clippy `-D warnings`;
5. runtime Python privado verificado;
6. instalación/bridge/Native Messaging reales;
7. **MegaBench real** con Whisper Small y M2M100: ASR P50/P95, ASR RTF, MT EN→ES P50/P95 y MT ZH→ES P50/P95;
8. Desktop Release `WINDOWS_GUI`;
9. Tauri NSIS;
10. instalación real del NSIS generado;
11. extensión ZIP;
12. `MilyVoiceTraductor-2.0.0-MegaBench.json`;
13. `SHA256SUMS.txt`.

### Descargar

**[⬇ MilyVoiceTraductor 2.0.0 Windows x64](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.0/MilyVoiceTraductor_2.0.0_x64-setup.exe)**

**[⬇ Extensión Chromium](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.0/MilyVoiceTraductor-Chromium-Extension.zip)**

**[⬇ MegaBench 2.0](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.0/MilyVoiceTraductor-2.0.0-MegaBench.json)**

El instalador también deja la extensión preparada en `%LOCALAPPDATA%\MilyVoiceTraductor\extension`. Chromium exige autorización explícita para instalar una extensión fuera de tienda y para comenzar `tabCapture`.

## Ingeniería

- [MASTER](MASTER.md)
- [Coordinación de workstreams](docs/WORKSTREAMS.md)
- [Instalación y desarrollo](docs/INSTALLATION.md)
- [Arquitectura completa](docs/architecture/COMPLETE_ARCHITECTURE.md)
- [Modelos y licencias](docs/MODELS.md)
- [Privacidad](docs/privacy/PRIVACY.md)
- [Seguridad](SECURITY.md)
- [Checklist de release](docs/release/RELEASE_CHECKLIST.md)

## Licencia

El código propio de MilyVoiceTraductor se distribuye bajo **MIT**. Los pesos externos conservan sus licencias originales y no se redistribuyen dentro del repositorio.

<p align="center"><strong>MilyVoiceTraductor 2.0</strong><br/>Local · realtime · adaptive compute</p>
