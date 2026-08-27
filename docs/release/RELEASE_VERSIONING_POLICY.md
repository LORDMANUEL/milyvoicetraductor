# Política de versionado de MilyVoiceTraductor

## Versión de producto

La versión visible y publicable de MilyVoiceTraductor se define en `VERSION` y debe coincidir con los metadatos del paquete Desktop/Tauri, el motor Python, la extensión Chromium y los endpoints/eventos públicos del runtime.

## Versiones de módulos

Los crates Rust y otros módulos internos pueden conservar una versión propia cuando su API/artefacto no cambió. Un bump de producto no obliga a modificar artificialmente cada módulo ni sus lockfiles.

El Desktop no debe usar `CARGO_PKG_VERSION` como versión pública del producto; la versión pública debe derivarse de `VERSION`/Tauri.

## Releases inmutables

Un tag/release público nunca se retargetea ni se sobrescribe. Si una beta pública necesita un cambio funcional posterior, se crea una nueva versión patch. Los reruns del publicador sólo pueden verificar que el SHA y `SHA256SUMS.txt` coinciden con lo ya publicado.
