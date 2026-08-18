<p align="center">
  <img src="apps/site/assets/logo.svg" alt="MilyVoiceTraductor" width="150" />
</p>

<h1 align="center">MilyVoiceTraductor 2.0</h1>

<p align="center"><strong>Voz, subtítulos y traducción local en tiempo real para español, inglés y chino mandarín.</strong></p>

<p align="center">
  Reuniones, pestañas web, audio del sistema, micrófono, videos, cursos y karaoke con runtime privado, selección adaptativa de cómputo y procesamiento local.
</p>

<p align="center">
  <img alt="Windows 2.0.0 Stable" src="https://img.shields.io/badge/Windows_2.0.0-Stable-00A878?style=for-the-badge&logo=windows11&logoColor=white">
  <img alt="CI 852 verified" src="https://img.shields.io/badge/CI_852-Verified-1769E0?style=for-the-badge&logo=githubactions&logoColor=white">
</p>

> **Release estable actual: 2.0.0.** La candidata `0403d63ff0b9387a84e55a014387b3074e033467` superó CI #852 completo y fue promovida a `main`. Pasó guards, Frontend, motor Python, Rust core, MegaBench con modelos reales, `WINDOWS_GUI`, Tauri NSIS e instalación real del instalador generado.

## Estado de entrega 2.0.0

El build validado genera conjuntamente:

- `MilyVoiceTraductor_2.0.0_x64-setup.exe`;
- `MilyVoiceTraductor-Chromium-Extension.zip`;
- `MilyVoiceTraductor-2.0.0-MegaBench.json`;
- `SHA256SUMS.txt`.

El artefacto de referencia fue producido por **CI #852** sobre el mismo SHA probado. El README no publica enlaces ficticios a una GitHub Release que todavía no exista; el build verificable queda asociado al workflow correspondiente.

[Ver CI #852 y su artefacto verificado](https://github.com/LORDMANUEL/milyvoicetraductor/actions/runs/32188948683)

## Qué cambia en 2.0

MilyVoice 2.0 es un salto de arquitectura y rendimiento:

- **CPU realtime optimizada:** presupuesto por núcleos físicos, INT8, ventanas adaptativas, energy gate, parciales estables, ASR/MT desacoplados, backpressure y warm-up.
- **MilyCompute Foundation:** CPU siempre disponible y registro/selección conservadora de CUDA, DirectML, OpenVINO y Vulkan. Detectar un runtime no significa afirmar que el adaptador del modelo ya esté listo.
- **Hardware Advisor:** topología CPU real, AVX/AVX2/FMA/AVX512 cuando existan y base para selección por benchmark, no por marca.
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

**EN→ES y ZH→ES son los caminos receptores prioritarios** para reuniones, videos y cursos. ES→EN y ES→ZH forman parte de la arquitectura Tier 1 bidireccional y solo se anuncian como funcionales cuando el protocolo/router correspondiente haya superado sus gates.

ASR significa voz→texto; MT realiza la traducción entre idiomas.

## Modelo estable y Model Labs

El baseline estable de producción continúa siendo:

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

- **TriCore / Quality:** trainers, evaluación y exportación preparados; los pesos fine-tuned no se consideran promocionados hasta existir y superar los promotion gates.
- **Legacy CPU:** laboratorio para Whisper Tiny + MT pequeño INT8 con objetivo i3 Haswell; no se considera Stable sin pesos finales y benchmark físico en ese hardware.

El MegaBench del runner GitHub detecta regresiones de 2.0, pero **no sustituye el benchmark físico Legacy**.

## Windows sin CMD ni consola negra

La versión 2.0 corrige específicamente el problema de ventanas de terminal visibles.

- `MilyVoiceTraductor.exe` se compila como `IMAGE_SUBSYSTEM_WINDOWS_GUI`.
- El Native Messaging bridge Release usa subsistema Windows, sin consola.
- El motor Python privado se inicia con `CREATE_NO_WINDOW` y streams anulados.
- La reparación PowerShell usa `CREATE_NO_WINDOW`, modo no interactivo y streams anulados.
- CI #852 verifica el subsistema GUI antes de crear NSIS.
- El NSIS generado se instala realmente en el runner antes de publicar el artefacto.

El usuario ejecuta un único instalador gráfico. No necesita instalar Python, `winget`, pip ni crear un venv manualmente.

## Instalación Windows

El paquete incluye:

- Desktop Tauri/Rust;
- Python 3.13 x64 privado;
- dependencias del motor;
- motor local;
- bridge Native Messaging;
- extensión Chromium;
- diagnóstico/reparación;
- registro local necesario para auto-reconocimiento.

Los pesos del modelo se descargan desde Hugging Face durante la preparación visual de la aplicación y se verifican antes de activarse.

## Fuentes y modos

**Fuentes:**

- cualquier pestaña `http/https` capturable en Chrome/Edge/Brave/Chromium;
- micrófono;
- audio del sistema Windows;
- MP4/WebM/MP3/WAV/M4A y otros formatos soportados por el reproductor interno.

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

## MegaBench 2.0 — build estable

CI #852 ejecutó el pack real `realtime-m2m100@1.0.0` sobre Windows y obtuvo:

| Métrica | Resultado |
|---|---:|
| ASR P50 | 2457 ms |
| ASR P95 | 2897 ms |
| ASR RTF P95 | **0.248** |
| MT EN→ES P95 | **447 ms** |
| MT ZH→ES P95 | **504 ms** |
| End-to-end P95 estimado | **3400 ms** |
| Gate | **PASS** |

El fixture ASR reconoció correctamente una frase inglesa de prueba con números y negación. El gate ejecutó 5 inferencias ASR y 24 traducciones por dirección EN→ES y ZH→ES.

## Definition of Done 2.0

La versión estable fue promovida solo después de pasar, sobre el mismo SHA:

1. consistencia de versión 2.0.0;
2. source verification y privacy scan;
3. extension/site guards;
4. Python unit tests + `compileall`;
5. stress realtime, CPU budget, queue/backpressure y telemetría;
6. Frontend typecheck/tests/build;
7. Rust core tests y Clippy `-D warnings`;
8. runtime Python privado y bootstrap offline;
9. installed-flow + Native Messaging;
10. MegaBench real Whisper Small + M2M100;
11. workspace tests Windows;
12. Clippy Windows;
13. Desktop Release;
14. `WINDOWS_GUI`;
15. Tauri NSIS;
16. instalación real del NSIS generado;
17. extensión Chromium ZIP;
18. SHA-256 de los artefactos.

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

<p align="center"><strong>MilyVoiceTraductor 2.0.0 Stable</strong><br/>Local · realtime · adaptive compute</p>
