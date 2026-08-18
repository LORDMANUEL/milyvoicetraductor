<p align="center">
  <img src="apps/site/assets/logo.svg" alt="MilyVoiceTraductor" width="150" />
</p>

<h1 align="center">MilyVoiceTraductor</h1>

<p align="center"><strong>Entiende reuniones en inglés o chino en español, en tiempo real y con procesamiento local.</strong></p>

<p align="center">
  Instala. Conecta. Entiende. MilyVoiceTraductor une una aplicación Windows y una extensión Chromium que se reconocen automáticamente para mostrar subtítulos traducidos sin depender de una API de pago.
</p>

<p align="center">
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.5/MilyVoiceTraductor_1.0.5_x64-setup.exe"><img alt="Descargar para Windows" src="https://img.shields.io/badge/Descargar_para_Windows-00A878?style=for-the-badge&logo=windows11&logoColor=white"></a>
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.5/MilyVoiceTraductor-Chromium-Extension.zip"><img alt="Descargar extensión Chromium" src="https://img.shields.io/badge/Extensión_Chromium-1769E0?style=for-the-badge&logo=googlechrome&logoColor=white"></a>
</p>

<p align="center">
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v1.0.5">Ver release 1.0.5</a>
  ·
  <a href="https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.5/SHA256SUMS.txt">Verificar SHA-256</a>
</p>

> **Release actual: 1.0.5.** El instalador lleva su propio runtime Python 3.13 y las dependencias del motor. No necesita `winget`, Python del sistema ni `pip` durante la instalación. La primera preparación usa Internet únicamente para descargar desde Hugging Face los pesos fijados del pack de tiempo real; la conversión M2M100 → CTranslate2 INT8 se realiza localmente dentro de la aplicación.

## Habla. Escucha. Entiende.

MilyVoiceTraductor está pensado para reuniones donde el idioma no debería ser una barrera. Captura el audio de la pestaña que autorizas, reconoce inglés o chino y entrega la conversación en español mediante subtítulos claros.

**Ideal para:** reuniones internacionales de trabajo, capacitaciones, demostraciones, soporte técnico y usuarios que prefieren mantener el contenido de sus conversaciones bajo su propio control.

## Lo simple es parte del producto

1. **Instala MilyVoiceTraductor para Windows.** El EXE incluye el runtime privado, motor local, bridge de navegador y copia de la extensión.
2. **Añade la extensión a Chrome, Edge, Brave o Chromium.** El navegador exige esa autorización una vez.
3. **Abre ambos.** La aplicación y la extensión se reconocen automáticamente mediante un enlace local seguro: no hay token que copiar ni puerto que escribir.
4. **La app prepara el Modelo Tiempo Real INT8.** Descarga `Systran/faster-whisper-small` y `facebook/m2m100_418M` desde Hugging Face usando revisiones fijadas; después convierte M2M100 localmente a INT8. La pantalla muestra si está descargando reconocimiento, descargando traducción, optimizando o verificando.
5. **Abre Meet, Teams Web o Zoom Web y pulsa Iniciar traducción.**

### Descargar

**[⬇ Descargar MilyVoiceTraductor 1.0.5 para Windows x64](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.5/MilyVoiceTraductor_1.0.5_x64-setup.exe)**

**[⬇ Descargar extensión Chromium](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.5/MilyVoiceTraductor-Chromium-Extension.zip)**

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
| ♻️ | **Descarga recuperable.** Staging, verificación, fases visibles y reintento sin perder trabajo válido. |
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

**Los pesos de los modelos no están en GitHub ni dentro del EXE.** La app descarga desde Hugging Face las revisiones fijadas de `Systran/faster-whisper-small` y `facebook/m2m100_418M`. M2M100 se convierte después a CTranslate2 INT8 dentro del equipo. No se abre ninguna consola externa durante esa preparación.

## Si algo falla

MilyVoiceTraductor no reduce todos los problemas al mismo mensaje. Puede distinguir, entre otros, falta de Internet, espacio insuficiente, descarga interrumpida, permisos, integridad del modelo, conversión INT8 y runtime incompleto.

La pantalla de primera preparación muestra el estado **Runtime → Bridge → Modelo → Extensión** y, dentro del modelo, indica la fase real de descarga/optimización. Cuando el runtime incluido necesita recuperación ofrece **Reparar instalación**; cuando el modelo falla ofrece **Reintentar** conservando el staging válido.

## Compatibilidad

**Windows x64** · **Google Chrome** · **Microsoft Edge** · **Brave** · **Chromium**

La versión 1.0.5 captura actualmente el audio de la pestaña del navegador. Para Microsoft Teams y Zoom utiliza sus versiones web.

## Estado del producto

La versión 1.0.5 incluye Desktop Tauri/Rust, motor local Python, gestión de modelos, sesiones opcionales, extensión Chromium MV3, enlace Native Messaging, runtime Python privado y un instalador NSIS sometido a pruebas Windows/Linux e instalación automatizada del propio EXE generado.

## Integridad de la descarga

Cada build Windows publicado incluye `SHA256SUMS.txt`.

**[Ver SHA-256 de 1.0.5](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.5/SHA256SUMS.txt)**

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
