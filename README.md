<p align="center">
  <img src="apps/site/assets/logo.svg" alt="MilyVoiceTraductor" width="150" />
</p>

<h1 align="center">MilyVoiceTraductor 2.0.2</h1>

<p align="center"><strong>Estable · Windows x64 · traducción local en tiempo real para español, inglés y chino mandarín.</strong></p>

> **2.0.2 es el hotfix estable de 2.0.x.** Corrige el primer arranque, la preparación del runtime y el comportamiento del instalador sin cambiar el baseline de modelos de producción.

## Descarga estable 2.0.2

- [Instalador Windows x64](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.2/MilyVoiceTraductor_2.0.2_x64-setup.exe)
- [Extensión Chromium](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.2/MilyVoiceTraductor-Chromium-Extension.zip)
- [MegaBench 2.0.2](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.2/MilyVoiceTraductor-2.0.2-MegaBench.json)
- [SHA256SUMS](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.2/SHA256SUMS.txt)

## Flujo de primer arranque corregido

```text
Instalar MilyVoiceTraductor 2.0.2
        ↓
runtime privado + motor + bridge + extensión
        ↓
ABRIR la aplicación
        ↓
¿hay modelo activo?
   sí → traducción
   no → Gestor de modelos
        ↓
descarga únicamente por acción del usuario
```

El instalador **no descarga modelos**. Si el runtime está listo pero aún no hay un modelo activo, el shell abre y lleva al Gestor de modelos. Un fallo real del runtime sí mantiene el flujo de reparación.

## Correcciones de 2.0.2

- elimina `installModel('realtime-m2m100')` del onboarding automático;
- un modelo ausente ya no bloquea todo el Desktop;
- primer arranque sin modelo abre el Gestor de modelos;
- el NSIS muestra claramente `MilyVoiceTraductor 2.0.2`;
- un fallo del bootstrap hace que el NSIS termine con error: no se permite un falso **Installation Complete**;
- el runtime Python privado incluye Visual C++ Runtime app-local junto a `python.exe`;
- las DLL app-local se verifican por SHA-256 contra `runtime-manifest.json`;
- los imports nativos del runtime se prueban módulo por módulo y `RUNTIME_IMPORT_FAILED` identifica el módulo que falló sin filtrar rutas ni secretos;
- instalación limpia, primer arranque, reinstalación y Native Messaging se ejercitan con el NSIS real en GitHub Actions.

## Baseline estable de modelos

2.0.2 mantiene los pesos de producción de la línea 2.0.x:

```text
ASR: Systran/faster-whisper-small
MT : facebook/m2m100_418M → CTranslate2 INT8
```

La descarga/optimización del pack ocurre desde la aplicación cuando el usuario la solicita. Los pesos no se incluyen dentro del repositorio.

## Gates obligatorios

Un SHA de 2.0.2 solo puede publicarse si pasa: consistencia de versión, privacidad, extensión, GitHub Pages, Frontend typecheck/tests/build, tests del motor, Rust format/tests/Clippy, runtime Python privado, Visual C++ app-local, diagnóstico de imports, Native Messaging, MegaBench real EN→ES y ZH→ES, Desktop Release, `WINDOWS_GUI`, bundle NSIS, **NSIS negativo ante bootstrap roto**, primer arranque sin descarga implícita, instalación/reinstalación real, extensión y SHA-256.

## Privacidad

El hot path permanece local:

```text
audio → 127.0.0.1 → ASR → MT → subtítulos/TTS/sesión
```

No hay telemetría del contenido. La persistencia de sesiones continúa siendo opt-in.

## Historial

- `v2.0.1`: estable anterior; queda disponible como histórico.
- `v2.0.0`: histórico.
- la línea `2.1.x` pertenece al canal Beta y no reemplaza automáticamente esta estable.

## Ingeniería

- [MASTER](MASTER.md)
- [Instalación y desarrollo](docs/INSTALLATION.md)
- [Arquitectura](docs/architecture/COMPLETE_ARCHITECTURE.md)
- [Modelos y licencias](docs/MODELS.md)
- [Privacidad](docs/privacy/PRIVACY.md)
- [Seguridad](SECURITY.md)
- [Notas 2.0.2](docs/release/RELEASE_NOTES_2.0.2.md)

## Licencia

El código propio de MilyVoiceTraductor se distribuye bajo MIT. Los pesos externos mantienen sus licencias originales. SHA-256 verifica integridad; no se presenta el binario como Authenticode-firmado mientras no exista una identidad legítima de firma.

<p align="center"><strong>MilyVoiceTraductor 2.0.2 · ESTABLE</strong><br/>Local · realtime · adaptive compute</p>
