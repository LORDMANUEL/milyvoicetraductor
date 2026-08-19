<p align="center">
  <img src="apps/site/assets/logo.svg" alt="MilyVoiceTraductor" width="150" />
</p>

<h1 align="center">MilyVoiceTraductor 2.0.1</h1>

<p align="center"><strong>Voz, subtítulos y traducción local en tiempo real para español, inglés y chino mandarín.</strong></p>

> **2.0.1 es la candidata correctiva de 2.0.** La versión 2.0 tuvo un defecto de validación: el smoke NSIS comprobaba el payload instalado, pero no arrancaba explícitamente el Desktop instalado. En 2.0.1 el mismo EXE generado debe instalarse, arrancar y permanecer activo antes de permitir cualquier artefacto o promoción a `main`.

## Objetivo 2.0.1

Este ciclo está deliberadamente limitado a **estabilidad, arranque, publicación, rendimiento y MilyCompute**. No cambia el baseline de modelos y no incorpora fine-tunes experimentales.

Baseline estable:

```text
ASR: Systran/faster-whisper-small
MT : facebook/m2m100_418M → CTranslate2 INT8
```

### Correcciones obligatorias

- versión `2.0.1` única en VERSION, Cargo, Node, Tauri, motor Python y extensión Chromium;
- landing y descargas `2.0.1`, sin textos RC/2.0.0 obsoletos;
- Desktop, Native Messaging, motor Python y reparación sin CMD visible;
- NSIS real instalado en CI;
- **arranque real del `MilyVoiceTraductor.exe` instalado**;
- runtime Python 3.13 privado;
- Native Messaging y extensión preparados automáticamente;
- MegaBench real Whisper Small + M2M100;
- CPU como fallback obligatorio;
- MilyCompute elige únicamente adapters realmente ejecutables y medidos.

## Hardware / MilyCompute

MilyVoice no presupone que una GPU siempre sea mejor. El Hardware Profiler detecta CPU, núcleos físicos, AVX/AVX2/FMA, RAM y adaptadores GPU Windows mediante DXGI. MilyCompute mantiene estados distintos para runtime detectado y adapter realmente listo.

```text
Hardware Profiler
      ↓
Backend Registry
      ↓
Compatibility / health
      ↓
Benchmark P50 / P95 / RTF
      ↓
Model Router
      ↓
CPU fallback seguro
```

El perfil Legacy continúa optimizado para equipos pequeños, pero el benchmark físico específico sobre Intel Core i3 Haswell real permanece como validación externa pendiente. No se presenta como ejecutado mientras no exista esa evidencia física.

## Windows sin consola negra

- `MilyVoiceTraductor.exe`: subsistema `WINDOWS_GUI`.
- bridge Native Messaging: subsistema Windows en Release.
- motor Python: `CREATE_NO_WINDOW`.
- reparación PowerShell: `CREATE_NO_WINDOW`, no interactivo y streams anulados.
- el gate NSIS 2.0.1 arranca explícitamente el Desktop instalado.

## MegaBench 2.0.1

El mismo SHA debe generar `MilyVoiceTraductor-2.0.1-MegaBench.json` midiendo Whisper Small + M2M100 CT2 INT8 reales. El benchmark del runner es un gate de regresión; no reemplaza el benchmark físico Legacy Haswell.

## Artefacto esperado

Cuando la candidata supere todos los gates y sea promovida a `main`, la release `v2.0.1` debe contener exactamente:

- `MilyVoiceTraductor_2.0.1_x64-setup.exe`;
- `MilyVoiceTraductor-Chromium-Extension.zip`;
- `MilyVoiceTraductor-2.0.1-MegaBench.json`;
- `SHA256SUMS.txt`.

## Privacidad

El hot path permanece local:

```text
audio → 127.0.0.1 → ASR → MT → subtítulos/TTS/sesión
```

No se guardan tokens, contraseñas, audio ni transcripciones dentro de Git. La persistencia de sesiones sigue siendo opt-in.

## Ingeniería

- [MASTER](MASTER.md)
- [Coordinación de workstreams](docs/WORKSTREAMS.md)
- [Instalación y desarrollo](docs/INSTALLATION.md)
- [Arquitectura](docs/architecture/COMPLETE_ARCHITECTURE.md)
- [Modelos y licencias](docs/MODELS.md)
- [Privacidad](docs/privacy/PRIVACY.md)
- [Seguridad](SECURITY.md)
- [Checklist de release](docs/release/RELEASE_CHECKLIST.md)

## Licencia

El código propio de MilyVoiceTraductor se distribuye bajo MIT. Los pesos externos mantienen sus licencias originales y no se redistribuyen dentro del repositorio.

<p align="center"><strong>MilyVoiceTraductor 2.0.1</strong><br/>Local · realtime · adaptive compute</p>
