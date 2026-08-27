# MilyVoiceTraductor 2.1.1 Beta

## Qué cierra esta beta

MilyVoiceTraductor 2.1.1 Beta consolida la fase Tier 1 bidireccional de Engine Hub sin convertir el canal 2.1 en estable.

- Rutas prioritarias locales: **EN→ES, ES→EN, ZH→ES y ES→ZH**.
- `lite-es-en@1.0.1` usa Whisper Tiny multilingüe + Marian Tiny ES→EN INT8.
- `lite-es-zh@1.0.1` usa Whisper Tiny multilingüe + Marian directo ES→ZH INT8 con el prefijo de destino de chino simplificado fijado.
- Desktop prepara, instala, mide y activa una ruta compatible antes de iniciar la sesión.
- La extensión Chrome/Edge usa Native Messaging `prepare-route` antes de capturar audio.
- El bridge entrega una credencial efímera únicamente después de preparar la ruta solicitada.
- Se preservan números, IDs y negaciones mediante guardas de fidelidad antes de mostrar traducciones finales.

## Presupuesto y gates

Los perfiles Lite continúan sujetos a los mismos límites de producto: memoria total medida, RTF P95 y latencia E2E. No se relajaron gates para conseguir una certificación verde.

La publicación requiere un único SHA que complete el workflow **Certify exact SHA** con runtime privado Windows, benchmarks Lite bloqueantes EN→ES/ES→EN/ES→ZH, Rust/Clippy, Desktop Release, `WINDOWS_GUI`, NSIS, instalación real, extensión y `SHA256SUMS.txt`.

El benchmark ZH→ES Lite continúa como evidencia experimental y no bloquea ni forma parte del bundle público obligatorio.

## Trazabilidad

`v2.1.0` se conserva como beta histórica. **2.1.1 no reescribe ni retargetea tags/releases anteriores.** El tag `v2.1.1` sólo se crea para el SHA exacto certificado que llegue a `main`; una repetición del publicador debe verificar el mismo SHA y los mismos checksums en lugar de sobrescribir assets.

## Canal estable

La versión recomendada continúa siendo **2.0.2 Stable**. 2.1.1 permanece como **Beta** hasta una promoción explícita posterior.
