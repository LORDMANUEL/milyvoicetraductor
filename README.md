<p align="center">
  <a href="https://lordmanuel.github.io/milyvoicetraductor/">
    <img src="apps/site/assets/logo.svg" alt="MilyVoiceTraductor" width="170" />
  </a>
</p>

<h1 align="center">MilyVoiceTraductor</h1>

<p align="center"><strong>Traducción local al español en tiempo real para reuniones, cursos, videos y audio de Windows.</strong></p>

<p align="center">
  <a href="https://lordmanuel.github.io/milyvoicetraductor/"><img alt="Sitio oficial" src="https://img.shields.io/badge/Sitio_oficial-Ver_producto-00a878?style=for-the-badge" /></a>
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.1/MilyVoiceTraductor_2.0.1_x64-setup.exe"><img alt="Descargar para Windows" src="https://img.shields.io/badge/Windows_x64-Descargar_2.0.1-0078d4?style=for-the-badge&logo=windows" /></a>
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.0.1"><img alt="Release v2.0.1" src="https://img.shields.io/badge/Release-v2.0.1-2563eb?style=for-the-badge" /></a>
</p>

<p align="center">
  <a href="https://lordmanuel.github.io/milyvoicetraductor/"><strong>Explorar MilyVoiceTraductor</strong></a>
  ·
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.0.1">Notas y descargas</a>
  ·
  <a href="docs/INSTALLATION.md">Instalación</a>
  ·
  <a href="docs/privacy/PRIVACY.md">Privacidad</a>
</p>

---

## Traduce lo que escuchas, directamente en tu PC

MilyVoiceTraductor convierte voz y contenido multimedia en subtítulos y traducción al español sin enviar la conversación a un servicio de transcripción en la nube. La aplicación combina una experiencia nativa para Windows, una extensión para navegadores Chromium y un motor de inteligencia artificial que trabaja en `localhost`.

La versión publicada actualmente es **`v2.0.1` para Windows x64**.

### Fuentes de audio

| Fuente | Uso principal |
|---|---|
| **Microsoft Teams Desktop** | Reuniones reproducidas mediante el audio del sistema Windows. |
| **Teams Web y otras pestañas Chromium** | Captura directa de la pestaña con subtítulos sobre el navegador. |
| **Micrófono** | Conversaciones presenciales, dictado y práctica de idiomas. |
| **Audio del sistema** | Aplicaciones, reuniones y contenido reproducido en Windows. |
| **Archivos multimedia** | Videos, cursos, grabaciones, canciones y material educativo. |

### Resultados disponibles

- subtítulos originales y traducción al español en tiempo real;
- transcripción local de reuniones y contenido multimedia;
- identificación visual de hablantes mediante etiquetas y colores;
- lectura de la traducción con voces TTS instaladas en Windows;
- modos de reunión, aprendizaje, video y karaoke;
- exportación local de sesiones y subtítulos;
- funcionamiento con CPU y aceleración NVIDIA CUDA compatible cuando ofrece una mejora real.

## Diseñado como producto local y autónomo

### Privacidad de origen

El flujo principal permanece dentro del equipo:

```text
audio → motor local → reconocimiento → traducción → subtítulos / TTS / sesión
```

No incluye telemetría del contenido de la conversación. Las sesiones se guardan únicamente cuando el usuario habilita la persistencia.

### Instalación sin depender del Python del usuario

El instalador incorpora un **runtime Python 3.13 privado**, el motor local, el bridge de Native Messaging y las herramientas de reparación necesarias. La aplicación no depende de que el usuario instale Python, configure puertos o copie tokens manualmente.

### Integración automática con Chrome y Edge

La extensión Chromium se comunica con la aplicación mediante un host nativo restringido. Desktop, motor y extensión se reconocen localmente y utilizan credenciales efímeras.

### MilyCompute

MilyCompute inspecciona el hardware disponible y conserva siempre una ruta segura mediante CPU. En `2.0.1`, la ejecución comprobada utiliza:

- **CPU** como backend universal y fallback obligatorio;
- **NVIDIA CUDA** cuando CTranslate2 puede inicializar el modelo de forma compatible y el benchmark confirma su utilidad.

La detección de una GPU por sí sola no se presenta como aceleración. La decisión se basa en capacidad ejecutable, estabilidad, latencia y RTF.

## Mejoras incorporadas en `2.0.1`

La versión `2.0.1` consolida la base funcional de MilyVoiceTraductor con mejoras enfocadas en experiencia, continuidad y rendimiento:

- instalación limpia y actualización sobre instalaciones existentes;
- inicio real de la aplicación instalada y recuperación automática del motor local;
- aplicación, bridge y reparación sin ventanas de consola negras;
- reproducción nativa de Teams Web mientras la copia para ASR se procesa a 16 kHz;
- selección automática de una salida WASAPI activa cuando el dispositivo predeterminado está en silencio;
- continuidad del audio entre segmentos para no perder el final de una frase;
- colas realtime limitadas que priorizan resultados finales;
- fallback automático a CPU cuando CUDA no puede inicializarse;
- recuperación segura de configuración y base de datos locales;
- versión consistente entre Desktop, extensión, motor, instalador, sitio y artefactos;
- MegaBench con Whisper Small y M2M100 reales antes de publicar la distribución.

Los detalles técnicos y los problemas resueltos se encuentran en las [notas de la versión `v2.0.1`](docs/release/RELEASE_NOTES_2.0.1.md).

## Instalación

1. Descarga el instalador oficial:
   **[MilyVoiceTraductor_2.0.1_x64-setup.exe](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.1/MilyVoiceTraductor_2.0.1_x64-setup.exe)**.
2. Ejecuta el instalador en Windows x64.
3. Abre MilyVoiceTraductor y completa la preparación inicial del modelo.
4. Para traducir pestañas web, descarga y carga la **[extensión Chromium](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.1/MilyVoiceTraductor-Chromium-Extension.zip)** en Chrome, Edge, Brave u otro navegador Chromium compatible.
5. Selecciona la fuente de audio y comienza la sesión.

La descarga inicial de los pesos de IA requiere Internet. Una vez preparados, el reconocimiento y la traducción se ejecutan localmente.

## Descargas oficiales

| Componente | Descarga |
|---|---|
| Instalador Windows x64 | [MilyVoiceTraductor 2.0.1](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.1/MilyVoiceTraductor_2.0.1_x64-setup.exe) |
| Extensión Chromium | [Chrome / Edge / Brave](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.1/MilyVoiceTraductor-Chromium-Extension.zip) |
| Resultado MegaBench | [MilyVoiceTraductor-2.0.1-MegaBench.json](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.1/MilyVoiceTraductor-2.0.1-MegaBench.json) |
| Hashes de integridad | [SHA256SUMS.txt](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.1/SHA256SUMS.txt) |
| Release completa | [Tag `v2.0.1`](https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.0.1) |

## Tecnología

```text
Windows Desktop:  Tauri 2 + Rust + Svelte + TypeScript
Motor local:      Python 3.13 privado + FastAPI/WebSocket
Reconocimiento:   Faster-Whisper Small
Traducción:       M2M100 418M + CTranslate2 INT8
Navegador:        Chromium Manifest V3 + Native Messaging
Audio Windows:    WASAPI loopback
Datos locales:    SQLite + archivos de sesión opt-in
```

## Documentación del proyecto

- [MASTER y alcance del producto](MASTER.md)
- [Instalación y desarrollo](docs/INSTALLATION.md)
- [Arquitectura completa](docs/architecture/COMPLETE_ARCHITECTURE.md)
- [Modelos y licencias](docs/MODELS.md)
- [Política de privacidad](docs/privacy/PRIVACY.md)
- [Seguridad](SECURITY.md)
- [Notas de MilyVoiceTraductor 2.0.1](docs/release/RELEASE_NOTES_2.0.1.md)
- [Checklist de publicación](docs/release/RELEASE_CHECKLIST.md)

## Licencia

El código propio de MilyVoiceTraductor se distribuye bajo licencia MIT. Los modelos y componentes externos mantienen sus licencias originales y no se redistribuyen dentro del repositorio salvo que su licencia lo permita expresamente.

---

<p align="center">
  <strong>MilyVoiceTraductor 2.0.1</strong><br />
  IA local · Audio universal · Realtime · Privacidad por diseño
</p>
