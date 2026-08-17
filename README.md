<p align="center">
  <img src="apps/site/assets/logo.svg" alt="MilyVoiceTraductor" width="150" />
</p>

<h1 align="center">MilyVoiceTraductor</h1>

<p align="center"><strong>Entiende reuniones en inglés o chino en español, en tiempo real y con procesamiento local.</strong></p>

<p align="center">
  Tu reunión, tu audio, tu equipo. MilyVoiceTraductor combina una aplicación de escritorio con una extensión Chromium para mostrar subtítulos traducidos sin depender de una plataforma de traducción en la nube.
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

> **Release actual: 1.0.0-rc.1.** Es una versión candidata lista para pruebas reales. La primera preparación necesita conexión a Internet para instalar o completar el runtime local y descargar los modelos; después, el procesamiento de la reunión ocurre localmente.

## Habla. Escucha. Entiende.

MilyVoiceTraductor está pensado para reuniones donde el idioma no debería ser una barrera. Captura el audio de una pestaña del navegador, reconoce el idioma de origen y entrega la traducción en español mediante subtítulos claros.

**Ideal para:**

- reuniones de trabajo con personas que hablan inglés o chino;
- Google Meet y las versiones web de Microsoft Teams o Zoom;
- capacitaciones, demostraciones y presentaciones internacionales;
- usuarios que prefieren mantener el contenido de sus reuniones en su propio equipo.

## Por qué MilyVoiceTraductor

| | Beneficio |
|---|---|
| 🔒 | **Privacidad por defecto.** No hay telemetría y el motor trabaja en tu equipo. |
| 🌎 | **Inglés y chino → español.** Diseñado alrededor del flujo de traducción que realmente necesitas. |
| 💬 | **Subtítulos durante la reunión.** La extensión Chromium integra la traducción en la pestaña que estás usando. |
| 🧠 | **IA local.** El instalador prepara el motor y descarga el modelo recomendado sin exigir una API de pago. |
| 🗂️ | **Sesiones bajo tu control.** Guardar transcripciones es opcional; está desactivado por defecto. |
| ♻️ | **Modelos administrables.** Puedes verificar, cambiar o recuperar modelos desde la aplicación. |

## Empieza en pocos pasos

### 1. Instala MilyVoiceTraductor

**[⬇ Descargar MilyVoiceTraductor para Windows x64](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.0-rc.1/MilyVoiceTraductor_1.0.0-rc.1_x64-setup.exe)**

Ejecuta el instalador. La RC1 prepara automáticamente el entorno local, instala Python 3.13 si el equipo lo necesita y `winget` está disponible, crea un runtime aislado y descarga el pack recomendado `business-qwen`.

Si la descarga del modelo se interrumpe, la instalación de escritorio permanece disponible y el estado queda guardado para poder reintentar sin empezar desde cero.

### 2. Añade la extensión al navegador

El instalador deja una copia preparada en:

```text
%LOCALAPPDATA%\MilyVoiceTraductor\extension
```

En Chrome, Edge o Brave abre la página de extensiones, activa **Modo desarrollador**, selecciona **Cargar descomprimida** y elige esa carpeta.

También puedes descargarla aparte:

**[⬇ Descargar extensión Chromium](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.0-rc.1/MilyVoiceTraductor-Chromium-Extension.zip)**

> Chromium exige una autorización explícita del usuario para cargar una extensión no publicada en una tienda y para iniciar la captura de una pestaña. MilyVoiceTraductor no intenta saltarse esas protecciones.

### 3. Abre tu reunión y comienza

Abre MilyVoiceTraductor, prepara el motor local y entra a tu reunión desde el navegador. Desde la extensión selecciona la pestaña que quieres traducir y pulsa **Iniciar traducción**.

La captura actual está enfocada en **audio de pestaña del navegador**. Para Microsoft Teams o Zoom utiliza sus versiones web en esta RC1.

## Privacidad que se puede explicar en una frase

**El contenido de tu reunión no necesita salir de tu equipo para ser traducido.**

MilyVoiceTraductor mantiene el motor en `localhost`, no incorpora telemetría y no guarda audio ni transcripciones de forma predeterminada. La persistencia de sesiones es una decisión del usuario.

Los permisos de captura se solicitan cuando hacen falta y la captura de pestaña solo comienza después de una acción explícita.

## Qué incluye la descarga de Windows

El instalador RC1 no es únicamente una interfaz. Incluye el bootstrap necesario para dejar preparado el producto:

- aplicación de escritorio MilyVoiceTraductor;
- motor de IA local;
- extensión Chromium;
- runtime Python aislado;
- instalación de dependencias del motor;
- diagnóstico local;
- descarga y verificación del pack de modelos comercial recomendado.

Los pesos de los modelos no se incrustan dentro del `.exe` porque son grandes y conservan sus propias licencias. Se descargan durante la preparación inicial.

## Navegadores

La extensión está diseñada para navegadores basados en Chromium, entre ellos:

**Google Chrome · Microsoft Edge · Brave · Chromium**

## Estado del producto

**1.0.0-rc.1** integra actualmente:

- aplicación de escritorio;
- traducción local;
- subtítulos mediante extensión Chromium;
- gestión de modelos y rollback;
- sesiones opcionales;
- instalación Windows con preparación automática del motor;
- verificaciones de privacidad y builds Windows/Linux en CI.

Antes de llamar a esta versión `1.0.0` estable todavía corresponde hacer pruebas de campo con diferentes micrófonos/equipos, medir latencia real según hardware y completar la distribución firmada de la extensión/instalador.

## Integridad de la descarga

Cada build Windows publicado incluye `SHA256SUMS.txt`.

**[Ver SHA-256 de la RC1](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.0-rc.1/SHA256SUMS.txt)**

La automatización de publicación toma exclusivamente un artefacto generado por un CI exitoso sobre `main`, vuelve a validar sus hashes y solo entonces crea o actualiza la Release pública.

## Para desarrolladores

El README principal está orientado al producto. La información de ingeniería está separada aquí:

- [Instalación y desarrollo](docs/INSTALLATION.md)
- [Arquitectura completa](docs/architecture/COMPLETE_ARCHITECTURE.md)
- [Modelos y licencias](docs/MODELS.md)
- [Privacidad](docs/privacy/PRIVACY.md)
- [Seguridad](SECURITY.md)
- [Checklist de release](docs/release/RELEASE_CHECKLIST.md)

## Licencia

El código propio de MilyVoiceTraductor se distribuye bajo **MIT**. Los modelos mantienen sus licencias originales y no se redistribuyen como pesos dentro del instalador.

<p align="center"><strong>MilyVoiceTraductor</strong><br/>Emerald green · Sapphire blue · Bone white<br/>Traducción local para conversaciones globales.</p>
