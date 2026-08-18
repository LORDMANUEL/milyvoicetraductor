# MilyVoiceTraductor 1.0.5

Versión corregida y validada del traductor local de reuniones para Windows x64.

## Cambios principales

- Versionado unificado a `1.0.5` en Desktop, Rust, Tauri, motor Python, extensión Chromium y publicación.
- Instalador NSIS con runtime Python 3.13 privado; no requiere Python, pip ni winget del usuario.
- Motor local y operaciones de modelos ejecutados sin consola visible en Windows.
- Preparación del pack `realtime-m2m100` integrada dentro de la app.
- Descarga fijada desde Hugging Face de `Systran/faster-whisper-small` y `facebook/m2m100_418M`.
- Conversión local de M2M100 a CTranslate2 INT8 con estados visibles dentro del onboarding.
- Pantalla de preparación con fases separadas: descarga ASR, descarga traducción, optimización INT8, verificación y listo.
- Native Messaging automático entre Desktop y extensión, sin token o puerto manual.
- Verificación SHA-256 del runtime y de los artefactos publicados.
- CI Windows/Linux con tests, Clippy estricto, Release build, bundle NSIS e instalación real del EXE generado.

## Privacidad

El audio, credenciales efímeras y traducción permanecen en el equipo. Los pesos de modelos se descargan desde los repositorios públicos fijados en Hugging Face y después se usan localmente.

## Archivos de release

- `MilyVoiceTraductor_1.0.5_x64-setup.exe`
- `MilyVoiceTraductor-Chromium-Extension.zip`
- `SHA256SUMS.txt`
