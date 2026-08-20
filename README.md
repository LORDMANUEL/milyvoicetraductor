<p align="center">
  <a href="https://lordmanuel.github.io/milyvoicetraductor/">
    <img src="apps/site/assets/logo.svg" alt="MilyVoiceTraductor" width="170" />
  </a>
</p>

<h1 align="center">MilyVoiceTraductor</h1>

<p align="center"><strong>Traducción local al español en tiempo real para reuniones, cursos, videos y audio de Windows.</strong></p>

<p align="center">
  <a href="https://lordmanuel.github.io/milyvoicetraductor/"><img alt="Sitio oficial" src="https://img.shields.io/badge/Sitio_oficial-Ver_producto-00a878?style=for-the-badge" /></a>
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.1/MilyVoiceTraductor_2.0.1_x64-setup.exe"><img alt="Descargar estable para Windows" src="https://img.shields.io/badge/Windows_x64-Descargar_estable_2.0.1-0078d4?style=for-the-badge&logo=windows" /></a>
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.1.0"><img alt="Beta 2.1.0" src="https://img.shields.io/badge/Beta-2.1.0-f59e0b?style=for-the-badge" /></a>
</p>

<p align="center">
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.1/MilyVoiceTraductor_2.0.1_x64-setup.exe"><strong>Descargar estable 2.0.1</strong></a>
  ·
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.1.0">Probar beta 2.1.0</a>
  ·
  <a href="docs/INSTALLATION.md">Instalación</a>
  ·
  <a href="docs/privacy/PRIVACY.md">Privacidad</a>
</p>

---

## Canales de versión

### Estable actual — `v2.0.1`

La versión recomendada para uso normal continúa siendo **MilyVoiceTraductor 2.0.1 para Windows x64**.

**[Descargar estable 2.0.1](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.1/MilyVoiceTraductor_2.0.1_x64-setup.exe)**

### Beta actual — `v2.1.0`

**MilyVoiceTraductor 2.1.0 es una beta pública para pruebas.** No sustituye todavía a 2.0.1 como estable.

La beta 2.1.0 incorpora Engine Hub, rutas Lite, selección adaptativa de motores y nuevas pruebas de Windows. Debe usarse para validación externa, reporte de fallos y comparación de rendimiento.

**[Descargar beta 2.1.0](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.1.0/MilyVoiceTraductor_2.1.0_x64-setup.exe)**

### Descargas oficiales

| Canal | Componente | Descarga |
|---|---|---|
| **Estable** | Instalador Windows x64 | [MilyVoiceTraductor 2.0.1](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.1/MilyVoiceTraductor_2.0.1_x64-setup.exe) |
| **Estable** | Extensión Chromium | [Extensión 2.0.1](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.1/MilyVoiceTraductor-Chromium-Extension.zip) |
| **Beta** | Instalador Windows x64 | [MilyVoiceTraductor 2.1.0 Beta](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.1.0/MilyVoiceTraductor_2.1.0_x64-setup.exe) |
| **Beta** | Extensión Chromium | [Extensión 2.1.0](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.1.0/MilyVoiceTraductor-Chromium-Extension.zip) |
| **Beta** | Hashes SHA-256 | [SHA256SUMS.txt](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.1.0/SHA256SUMS.txt) |
| **Beta** | Release / evidencia | [Tag v2.1.0](https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.1.0) |

---

## Qué hace MilyVoiceTraductor

MilyVoiceTraductor convierte voz y contenido multimedia en subtítulos y traducción al español, con procesamiento local y una aplicación de escritorio para Windows junto con una extensión Chromium.

### Fuentes de audio

- Microsoft Teams Desktop mediante audio del sistema Windows.
- Teams Web y otras pestañas Chromium.
- Micrófono.
- Audio del sistema.
- Archivos multimedia.

### Resultados

- subtítulos originales y traducción al español;
- transcripción local;
- identificación visual de hablantes;
- TTS con voces instaladas en Windows;
- modos de reunión, aprendizaje, video y karaoke;
- exportación local de sesiones y subtítulos.

## Arquitectura local

```text
audio → motor local → ASR → traducción → subtítulos / TTS / sesión
```

El instalador incorpora runtime Python privado, motor local, bridge Native Messaging y herramientas de reparación. No depende del Python del usuario ni de copiar tokens o puertos manualmente.

### MilyCompute / Engine Hub

En el canal beta 2.1.0 se prueban rutas como Moonshine, Whisper Tiny y Sherpa Zipformer con selección automática según hardware, memoria y rendimiento. La CPU permanece como fallback seguro.

## Historial

Las versiones anteriores se conservan públicamente:

- [v2.0.1 — estable actual](https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.0.1)
- [v2.0.0 — histórica](https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.0.0)
- [v1.0.5 — histórica](https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v1.0.5)
- [v1.0.0-rc.1 — RC histórica](https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v1.0.0-rc.1)

El registro técnico completo está en [VERSION_HISTORY.md](docs/release/VERSION_HISTORY.md).

## Documentación

- [MASTER y alcance](MASTER.md)
- [Instalación](docs/INSTALLATION.md)
- [Arquitectura](docs/architecture/COMPLETE_ARCHITECTURE.md)
- [Modelos y licencias](docs/MODELS.md)
- [Privacidad](docs/privacy/PRIVACY.md)
- [Seguridad](SECURITY.md)
- [Notas 2.0.1](docs/release/RELEASE_NOTES_2.0.1.md)
- [Notas beta 2.1.0](docs/release/RELEASE_NOTES_2.1.0.md)

## Licencia

El código propio de MilyVoiceTraductor se distribuye bajo licencia MIT. Modelos y componentes externos mantienen sus licencias originales.

---

<p align="center">
  <strong>2.0.1 estable · 2.1.0 beta pública</strong><br />
  IA local · Audio universal · Realtime · Privacidad por diseño
</p>
