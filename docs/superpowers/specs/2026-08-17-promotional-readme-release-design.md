# MilyVoiceTraductor — Promotional README & Release Design

## Objetivo

Convertir la portada del repositorio en una página de producto orientada a usuarios finales y ofrecer descargas permanentes de la RC1 sin depender de artefactos temporales de GitHub Actions.

## Experiencia de usuario

La primera pantalla del README mostrará el logo, una propuesta de valor simple y botones directos para descargar Windows, la extensión Chromium y los hashes. El contenido principal explicará qué hace MilyVoiceTraductor, por qué es privado, en qué reuniones puede usarse y cómo comenzar en pocos pasos. Los detalles de arquitectura, compilación y desarrollo quedarán enlazados al final, no dominarán la portada.

La landing estática usará los mismos enlaces de descarga para que repositorio y sitio no diverjan.

## Distribución

La Release pública será `v1.0.0-rc.1`. Los assets esperados son:

- `MilyVoiceTraductor_1.0.0-rc.1_x64-setup.exe`
- `MilyVoiceTraductor-Chromium-Extension.zip`
- `SHA256SUMS.txt`

La Release no se construye de forma independiente. Un workflow `workflow_run` se ejecutará únicamente cuando el workflow `CI` termine con éxito sobre `main`. Descargará el artefacto Windows correspondiente al SHA validado, comprobará `SHA256SUMS.txt` y solo después creará o actualizara la Release.

## Mensaje de producto

- Traducción de reuniones web en inglés o chino a español.
- Procesamiento local y sin telemetría.
- Extensión para Chrome, Edge, Brave y otros navegadores Chromium.
- Instalador Windows que prepara motor, runtime y modelo recomendado.
- Audio y transcripciones no se guardan por defecto.

## Limitaciones comunicadas claramente

- La primera preparación necesita Internet para instalar dependencias/descargar modelos.
- La extensión RC1 se carga manualmente en modo desarrollador hasta disponer de distribución firmada por tienda.
- La captura actual está orientada al audio de una pestaña del navegador; para Teams/Zoom se recomienda su versión web.
- Es una Release Candidate, no una versión estable final.

## Verificación

- `scripts/test_site.py` comprobará que la landing mantiene los enlaces de descarga RC1.
- El CI existente seguirá ejecutando frontend, motor IA, privacidad, Rust, Clippy, release build y NSIS.
- El workflow de publicación validará SHA-256 antes de subir assets a la Release.
