# MilyVoiceTraductor 1.0.0 RC1

Esta Release Candidate reúne por primera vez el flujo completo de instalación y uso de MilyVoiceTraductor para Windows.

## Descargas

- **MilyVoiceTraductor_1.0.0-rc.1_x64-setup.exe** — instalador Windows x64.
- **MilyVoiceTraductor-Chromium-Extension.zip** — extensión para Chrome, Edge, Brave y Chromium.
- **SHA256SUMS.txt** — hashes SHA-256 de los archivos publicados.

## Qué incluye

- aplicación de escritorio MilyVoiceTraductor;
- motor de IA local para reconocimiento y traducción;
- extensión Chromium para captura explícita del audio de una pestaña y subtítulos;
- preparación automática de Python 3.13 cuando sea necesario y `winget` esté disponible;
- runtime Python aislado bajo `%LOCALAPPDATA%\MilyVoiceTraductor`;
- instalación de dependencias del motor;
- diagnóstico local después de preparar el runtime;
- descarga y verificación del pack recomendado `business-qwen`;
- gestión de modelos, sesiones opcionales y configuración local;
- ausencia de telemetría y persistencia de transcripciones desactivada por defecto.

## Primera instalación

La primera preparación necesita conexión a Internet para instalar dependencias y descargar los modelos. El instalador no incrusta los pesos de los modelos, por su tamaño y porque cada modelo mantiene su propia licencia.

Si el modelo no termina de descargarse, el desktop y el runtime quedan preparados y la descarga puede reintentarse sin reinstalar todo el producto.

## Extensión Chromium

Durante RC1 la extensión se carga manualmente desde `%LOCALAPPDATA%\MilyVoiceTraductor\extension` mediante **Modo desarrollador → Cargar descomprimida**. Chromium exige una acción explícita del usuario tanto para cargar una extensión no distribuida por una tienda como para iniciar la captura de una pestaña.

La captura actual se centra en audio de pestaña. Para Teams o Zoom se recomienda utilizar sus versiones web.

## Privacidad

El motor escucha únicamente en el equipo local, no incorpora telemetría y no guarda audio ni transcripciones por defecto. Los permisos de captura son progresivos y la captura empieza únicamente tras una acción del usuario.

## Estado

RC1 está destinada a pruebas reales antes de promover `1.0.0` estable. Los siguientes criterios de producto son pruebas de campo de latencia y calidad en hardware diverso, y distribución firmada del instalador/extensión.

Los archivos de esta Release son publicados automáticamente únicamente después de que `main` supere la matriz de CI y sus hashes vuelvan a validarse.
