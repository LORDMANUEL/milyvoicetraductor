<p align="center">
  <img src="apps/site/assets/logo.svg" alt="MilyVoiceTraductor" width="150" />
</p>

<h1 align="center">MilyVoiceTraductor</h1>

<p align="center"><strong>Entiende reuniones en inglés o chino en español, en tiempo real y con procesamiento local.</strong></p>

<p align="center">
  Instala. Conecta. Entiende. MilyVoiceTraductor une una aplicación Windows y una extensión Chromium que se reconocen automáticamente para mostrar subtítulos traducidos sin depender de una API de pago.
</p>

<p align="center">
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.0-rc.1/MilyVoiceTraductor_1.0.0-rc.1_x64-setup.exe"><img alt="Descargar para Windows" src="https://img.shields.io/badge/Descargar_para_Windows-00A878?style=for-the-badge&logo=windows11&logoColor=white"></a>
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.0-rc.1/MilyVoiceTraductor-Chromium-Extension.zip"><img alt="Descargar extensión Chromium" src="https://img.shields.io/badge/Extensión_Chromium-1769E0?style=for-the-badge&logo=googlechrome&logoColor=white"></a>
</p>

<p align="center">
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v1.0.0-rc.1">Ver release 1.0.0 RC1</a>
  ·
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.0-rc.1/SHA256SUMS.txt">Verificar SHA-256</a>
</p>

> **Release actual: 1.0.0-rc.1.** El instalador lleva su propio runtime Python 3.13 y las dependencias del motor. No necesita `winget`, Python del sistema ni `pip` durante la instalación. La primera preparación usa Internet únicamente para descargar los pesos del modelo de IA.

## Habla. Escucha. Entiende.

MilyVoiceTraductor está pensado para reuniones donde el idioma no debería ser una barrera. Captura el audio de la pestaña que autorizas, reconoce inglés o chino y entrega la conversación en español mediante subtítulos claros.

**Ideal para:** reuniones internacionales de trabajo, capacitaciones, demostraciones, soporte técnico y usuarios que prefieren mantener el contenido de sus conversaciones bajo su propio control.

## Lo simple es parte del producto

1. **Instala MilyVoiceTraductor para Windows.** El EXE incluye el runtime privado, motor local, bridge de navegador y copia de la extensión.
2. **Añade la extensión a Chrome, Edge, Brave o Chromium.** El navegador exige esa autorización una vez.
3. **Abre ambos.** La aplicación y la extensión se reconocen automáticamente mediante un enlace local seguro: no hay token que copiar ni puerto que escribir.
4. **La app prepara Business Qwen.** Si el modelo no está todavía, comienza su descarga y verificación automáticamente. Si Internet se corta, Reintentar reutiliza el staging válido en vez de empezar desde cero.
5. **Abre Meet, Teams Web o Zoom Web y pulsa Iniciar traducción.**

### Descargar

**[⬇ Descargar MilyVoiceTraductor para Windows x64](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.0-rc.1/MilyVoiceTraductor_1.0.0-rc.1_x64-setup.exe)**

**[⬇ Descargar extensión Chromium](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.0-rc.1/MilyVoiceTraductor-Chromium-Extension.zip)**

El instalador deja además la extensión en:

```text
%LOCALAPPDATA%\MilyVoiceTraductor\extension
```

En un navegador Chromium sin publicación en tienda: abre la página de extensiones, activa **Modo desarrollador**, pulsa **Cargar descomprimida** y selecciona esa carpeta. Chromium también exige un clic explícito para comenzar a capturar el audio de una pestaña; MilyVoiceTraductor conserva esa protección.

## Por qué MilyVoiceTraductor

| | Beneficio |
|---|---|
| 🔒 | **Privacidad por defecto.** Motor en localhost, sin telemetría y sin guardar audio por defecto. |
| ⚡ | **Listo sin preparar Python.** Python 3.13 y las dependencias necesarias vienen dentro del instalador. |
| 🔗 | **App + extensión se reconocen solas.** Native Messaging local elimina token y puerto manuales. |
| 🌎 | **Inglés / chino → español.** Enfocado en el flujo real de reuniones internacionales. |
| 💬 | **Subtítulos durante la reunión.** La traducción aparece en la pestaña que autorizaste. |
| 🧠 | **IA local.** Los pesos se descargan una vez; después reconocimiento y traducción se ejecutan en tu equipo. |
| ♻️ | **Descarga recuperable.** Staging, verificación, errores específicos y reintento sin perder trabajo válido. |
| 🛠️ | **Reparación integrada.** Si el runtime incluido queda incompleto, la propia app ofrece Reparar instalación. |

## Privacidad que se puede explicar en una frase

**El contenido de tu reunión no necesita salir de tu equipo para ser traducido.**

La extensión captura únicamente la pestaña que autorizas. El motor escucha en `127.0.0.1`; el bridge Native Messaging acepta exclusivamente la extensión de MilyVoiceTraductor y entrega credenciales locales efímeras. No hay un token permanente guardado en el navegador.

Guardar transcripciones es opcional y está desactivado por defecto.

## ¿Qué descarga Internet la primera vez?

El EXE ya incluye:

- aplicación de escritorio;
- Python 3.13 x64 privado;
- dependencias Python del motor;
- motor de IA local;
- bridge Native Messaging;
- extensión Chromium;
- diagnóstico y recuperación del runtime.

**Solo los pesos de los modelos se descargan durante la primera preparación.** Se mantienen fuera del `.exe` porque son archivos grandes y conservan sus propias licencias.

## Si algo falla

MilyVoiceTraductor no reduce todos los problemas al mismo mensaje. Puede distinguir, entre otros, falta de Internet, espacio insuficiente, descarga interrumpida, permisos, integridad del modelo y runtime incompleto.

La pantalla de primera preparación muestra el estado **Runtime → Bridge → Modelo → Extensión**. Cuando el runtime incluido necesita recuperación ofrece **Reparar instalación**; cuando el modelo falla ofrece **Reintentar** conservando el staging válido.

## Compatibilidad

**Windows x64** · **Google Chrome** · **Microsoft Edge** · **Brave** · **Chromium**

La RC1 captura actualmente el audio de la pestaña del navegador. Para Microsoft Teams y Zoom utiliza sus versiones web.

## Estado del producto

La RC1 incluye Desktop Tauri/Rust, motor local Python, gestión de modelos, sesiones opcionales, extensión Chromium MV3, enlace Native Messaging, runtime Python privado y un instalador NSIS sometido a pruebas Windows/Linux.

Antes de etiquetarla `1.0.0` estable corresponde completar la prueba de campo final en distintos equipos Windows y medir latencia real según CPU/GPU.

## Integridad de la descarga

Cada build Windows publicado incluye `SHA256SUMS.txt`.

**[Ver SHA-256 de la RC1](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.0-rc.1/SHA256SUMS.txt)**

La descarga pública se actualiza desde un artefacto generado por CI y verificado antes de publicarse.

## Para desarrolladores

La portada está orientada al producto. La ingeniería está documentada aparte:

- [Instalación y desarrollo](docs/INSTALLATION.md)
- [Arquitectura completa](docs/architecture/COMPLETE_ARCHITECTURE.md)
- [Modelos y licencias](docs/MODELS.md)
- [Privacidad](docs/privacy/PRIVACY.md)
- [Seguridad](SECURITY.md)
- [Checklist de release](docs/release/RELEASE_CHECKLIST.md)

## Licencia

El código propio de MilyVoiceTraductor se distribuye bajo **MIT**. Los modelos mantienen sus licencias originales y no se redistribuyen como pesos dentro del instalador.

<p align="center"><strong>MilyVoiceTraductor</strong><br/>Emerald green · Sapphire blue · Bone white<br/>Traducción local para conversaciones globales.</p>
