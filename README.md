<p align="center">
  <a href="https://lordmanuel.github.io/milyvoicetraductor/">
    <img src="apps/site/assets/logo.svg" alt="MilyVoiceTraductor" width="170" />
  </a>
</p>

<h1 align="center">MilyVoiceTraductor</h1>

<p align="center"><strong>Traducción local al español en tiempo real para reuniones, cursos, videos y audio de Windows.</strong></p>

<p align="center">
  <a href="https://lordmanuel.github.io/milyvoicetraductor/"><img alt="Sitio oficial" src="https://img.shields.io/badge/Sitio_oficial-Ver_producto-00a878?style=for-the-badge" /></a>
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.1.0/MilyVoiceTraductor_2.1.0_x64-setup.exe"><img alt="Descargar para Windows" src="https://img.shields.io/badge/Windows_x64-Descargar_2.1.0-0078d4?style=for-the-badge&logo=windows" /></a>
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.1.0"><img alt="Release v2.1.0" src="https://img.shields.io/badge/Release-v2.1.0-2563eb?style=for-the-badge" /></a>
</p>

<p align="center">
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.1.0/MilyVoiceTraductor_2.1.0_x64-setup.exe"><strong>Descargar MilyVoiceTraductor 2.1.0 para Windows x64</strong></a>
  ·
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.1.0">Ver release</a>
  ·
  <a href="docs/INSTALLATION.md">Instalación</a>
  ·
  <a href="docs/privacy/PRIVACY.md">Privacidad</a>
</p>

---

## Estable actual — `v2.1.0`

**MilyVoiceTraductor 2.1.0** es la versión estable recomendada para pruebas y uso en Windows x64.

**[Descargar instalador 2.1.0](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.1.0/MilyVoiceTraductor_2.1.0_x64-setup.exe)**

La release 2.1.0 fue construida con el flujo de Windows que valida runtime privado, Native Messaging, motores Lite reales, Desktop Windows, subsistema GUI, NSIS e instalación/reinstalación del instalador generado antes de publicar los artefactos.

### Descargas oficiales

| Componente | Descarga |
|---|---|
| **Instalador Windows x64** | [MilyVoiceTraductor_2.1.0_x64-setup.exe](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.1.0/MilyVoiceTraductor_2.1.0_x64-setup.exe) |
| **Extensión Chromium** | [MilyVoiceTraductor-Chromium-Extension.zip](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.1.0/MilyVoiceTraductor-Chromium-Extension.zip) |
| **Hashes SHA-256** | [SHA256SUMS.txt](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.1.0/SHA256SUMS.txt) |
| **Benchmark Moonshine Lite** | [MoonshineLiteBench.json](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.1.0/MilyVoiceTraductor-2.1.0-MoonshineLiteBench.json) |
| **Benchmark Whisper Tiny Lite** | [WhisperTinyLiteBench.json](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.1.0/MilyVoiceTraductor-2.1.0-WhisperTinyLiteBench.json) |
| **Benchmark Sherpa Lite** | [SherpaLiteBench.json](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.1.0/MilyVoiceTraductor-2.1.0-SherpaLiteBench.json) |
| **Simulación de equipo objetivo** | [TargetMachineSimulation.json](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.1.0/MilyVoiceTraductor-2.1.0-TargetMachineSimulation.json) |
| **Release completa** | [GitHub Release v2.1.0](https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.1.0) |

## Qué incluye 2.1.0

- aplicación Windows nativa con Tauri 2 + Rust;
- runtime Python 3.13 privado;
- Native Messaging para integración automática con Chromium;
- captura de pestaña, micrófono, audio del sistema y archivos multimedia;
- traducción realtime **EN → ES** con rutas Lite seleccionables automáticamente;
- Moonshine Tiny Streaming, Whisper Tiny y Sherpa Zipformer dentro del Engine Hub certificado;
- mandarín **ZH → ES** disponible como ruta experimental;
- Resource Governor y simulación de presupuesto bajo 2 GiB para el producto;
- subtítulos, sesiones, TTS, modos de aprendizaje/video/karaoke y herramientas de diagnóstico;
- extensión para Chrome, Edge, Brave y navegadores Chromium compatibles.

## Instalación

1. Descarga **[MilyVoiceTraductor_2.1.0_x64-setup.exe](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.1.0/MilyVoiceTraductor_2.1.0_x64-setup.exe)**.
2. Ejecuta el instalador en Windows x64.
3. Abre MilyVoiceTraductor.
4. Para audio de pestaña, descarga la **[extensión Chromium](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.1.0/MilyVoiceTraductor-Chromium-Extension.zip)**, extráela y cárgala como extensión desempaquetada.
5. Selecciona la fuente de audio y comienza la sesión.

No es necesario instalar Python por separado ni copiar manualmente puertos o tokens para el enlace normal Desktop ↔ extensión.

## Privacidad

El flujo local principal permanece dentro del equipo:

```text
audio → ASR local → traducción local → subtítulos / TTS / sesión
```

No se envía el contenido de la conversación a un servicio de telemetría. Los conectores cloud opcionales, si se habilitan en el futuro o por configuración explícita, deben mostrar claramente que el audio sale del equipo.

## Certificación de la distribución

El gate Windows de 2.1.0 comprueba, entre otros:

- frontend y tests AI;
- bootstrap offline;
- bridge Native Messaging;
- runtime Python privado;
- flujo instalado y registro del bridge;
- simulación de equipo objetivo;
- política de memoria Lite;
- Moonshine EN→ES real;
- Whisper Tiny EN→ES real;
- Sherpa Zipformer EN→ES real;
- ZH→ES experimental;
- Rust + Clippy Windows;
- Desktop Release;
- `WINDOWS_GUI`;
- Tauri NSIS;
- instalación y reinstalación del NSIS generado;
- extensión Chromium;
- hashes SHA-256 y bundle final.

## Tecnología

```text
Windows Desktop:  Tauri 2 + Rust + Svelte + TypeScript
Motor local:      Python 3.13 privado + Engine Hub
ASR Lite:         Moonshine / Whisper Tiny / Sherpa Zipformer
Traducción:       Marian / CTranslate2 según pack
Navegador:        Chromium Manifest V3 + Native Messaging
Audio Windows:    WASAPI loopback
Datos locales:    SQLite + archivos de sesión opt-in
```

## Versiones anteriores

- [v2.0.1](https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.0.1)
- [v2.0.0](https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.0.0)
- [v1.0.5](https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v1.0.5)
- [v1.0.0-rc.1](https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v1.0.0-rc.1)

## Documentación

- [MASTER y alcance del producto](MASTER.md)
- [Instalación](docs/INSTALLATION.md)
- [Arquitectura](docs/architecture/COMPLETE_ARCHITECTURE.md)
- [Modelos y licencias](docs/MODELS.md)
- [Privacidad](docs/privacy/PRIVACY.md)
- [Seguridad](SECURITY.md)
- [Notas de 2.1.0](docs/release/RELEASE_NOTES_2.1.0.md)
- [Checklist de publicación](docs/release/RELEASE_CHECKLIST.md)

## Licencia

El código propio de MilyVoiceTraductor se distribuye bajo licencia MIT. Los modelos y componentes externos mantienen sus licencias originales y solo se redistribuyen cuando su licencia lo permite.

---

<p align="center">
  <strong>MilyVoiceTraductor 2.1.0 estable</strong><br />
  IA local · Audio universal · Realtime · Privacidad por diseño
</p>
