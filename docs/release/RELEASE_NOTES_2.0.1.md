# MilyVoiceTraductor 2.0.1

2.0.1 es una release correctiva y de optimización. Mantiene el baseline de modelos estable y corrige el proceso que permitió que 2.0 obtuviera un CI verde sin arrancar explícitamente el Desktop instalado.

## Correcciones de release

- el test NSIS instala y **arranca realmente** `MilyVoiceTraductor.exe`;
- el Desktop debe permanecer activo después del bootstrap inicial;
- VERSION, Cargo, Node, Tauri, motor Python, extensión, CI, publicación y sitio deben declarar exactamente `2.0.1`;
- GitHub Pages ya no conserva textos `2.0 RC` ni enlaces de descarga `v2.0.0`;
- el artefacto y la release pública provienen del mismo SHA verificado;
- Desktop, bridge, motor Python y reparación mantienen ejecución sin consola visible.

## Optimización / MilyCompute

- CPU continúa siendo fallback obligatorio;
- el Hardware Profiler conserva topología física, SIMD, RAM y GPUs DXGI;
- un runtime detectado no se anuncia como acelerador listo hasta existir adapter ejecutable y evidencia de benchmark/health;
- la selección se basa en RTF, latencia y estabilidad, no en la marca del dispositivo;
- el perfil de CPU débil evita sobresuscripción y prioriza resultados finales sobre trabajo opcional.

## Modelos

No se cambian los pesos de producción en 2.0.1:

- ASR: `Systran/faster-whisper-small`;
- MT: `facebook/m2m100_418M` convertido a CTranslate2 INT8.

Los Model Labs Quality/TriCore/Legacy continúan como R&D/Features y no se promocionan automáticamente.

## i3 Haswell

2.0.1 mantiene una ruta CPU conservadora y está diseñada para equipos de pocos núcleos, pero el benchmark físico específico sobre un Intel Core i3 Haswell real continúa pendiente. El MegaBench de GitHub es un gate de regresión, no sustituye esa certificación física.

## Artefactos

La release válida debe publicar desde un único SHA:

- `MilyVoiceTraductor_2.0.1_x64-setup.exe`;
- `MilyVoiceTraductor-Chromium-Extension.zip`;
- `MilyVoiceTraductor-2.0.1-MegaBench.json`;
- `SHA256SUMS.txt`.
