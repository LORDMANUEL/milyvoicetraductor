# MilyVoiceTraductor 2.0.1

2.0.1 es una release correctiva y de optimización. Mantiene el baseline de modelos estable y corrige fallos de validación, actualización, audio realtime y cómputo que permitieron que 2.0 pareciera lista sin reproducir correctamente varios escenarios de uso real.

## Correcciones de release e instalación

- el test NSIS instala y **arranca realmente** `MilyVoiceTraductor.exe`;
- el gate exige una ventana Windows visible, no solamente que exista un proceso;
- el mismo NSIS se reinstala sobre estado previo y debe volver a abrir una ventana válida;
- la reinstalación termina únicamente procesos propiedad de MilyVoice antes de sustituir el runtime privado; no mata Python ajeno;
- configuración JSON anterior malformada se pone en cuarentena y la aplicación arranca con valores seguros;
- SQLite local corrupto (`NotADatabase`/`DatabaseCorrupt`) se conserva como evidencia `.corrupt` y se recrea sin bloquear el arranque;
- reemplazar `config.json`/`engine.json` en Windows usa respaldo y rollback para no perder el archivo anterior si falla la activación de la nueva copia;
- VERSION, Cargo, Node, Tauri, motor Python, paquete Python interno, extensión, CI, publicación y sitio deben declarar exactamente `2.0.1`;
- GitHub Pages ya no conserva textos `2.0 RC` ni enlaces de descarga `v2.0.0`;
- el artefacto y la release pública provienen del mismo SHA verificado;
- Desktop, bridge, motor Python y reparación mantienen ejecución sin consola visible.

## Teams, audio y realtime

- la captura de Teams Web conserva el audio de reproducción de la pestaña a su frecuencia nativa y crea por separado la rama PCM 16 kHz usada por ASR;
- una captura de Teams puede autoarrancar el motor local cuando está instalado y detenido;
- el inicio de captura se permite únicamente en estados de motor realmente arrancables;
- WASAPI loopback puede cambiar desde el dispositivo predeterminado silencioso hacia otra salida activa, cubriendo el caso donde Teams Desktop reproduce por otro dispositivo;
- alcanzar el límite duro de un segmento realtime ya no descarta el PCM restante: la voz continúa en el segmento siguiente;
- backpressure conserva resultados finales y degrada primero trabajo parcial/opcional.

## Optimización / MilyCompute

- CPU continúa siendo el fallback obligatorio y ejecutable en todos los equipos soportados;
- NVIDIA CUDA se usa únicamente cuando CTranslate2 confirma CUDA utilizable y el proveedor puede inicializar realmente el modelo;
- en perfil `auto`, si la inicialización CUDA falla, Faster-Whisper y M2M100 vuelven a CPU en vez de inutilizar la sesión;
- en perfil GPU forzado, un fallo CUDA se informa como fallo real y no se disfraza como aceleración;
- Intel/AMD no se clasifican falsamente como CUDA por el solo hecho de existir una GPU;
- el Hardware Profiler usa topología física, SIMD, RAM e inventario DXGI de GPU;
- DirectML, Windows ML, OpenVINO y Vulkan pueden detectarse como candidatos de arquitectura, pero **no se anuncian como adapters listos** sin ejecución/benchmark real del modelo activo;
- `RealtimePipeline` expone internamente qué dispositivo usaron realmente ASR y MT (`cpu`/`cuda`) y si ocurrió fallback, con causa sanitizada;
- la selección de backends medidos se basa en RTF, latencia y estabilidad, no en la marca del dispositivo;
- el perfil de CPU débil evita sobresuscripción y prioriza resultados finales sobre trabajo opcional.

### Estado exacto de aceleración en 2.0.1

2.0.1 tiene ejecución real verificada para **CPU** y soporte de ejecución **NVIDIA CUDA** cuando CTranslate2 dispone de CUDA compatible. En equipos Intel/AMD integrados o GPU no-CUDA, la aplicación sigue siendo funcional mediante CPU fallback. La detección de DirectML/OpenVINO/Vulkan no equivale todavía a afirmar inferencia acelerada por esas rutas.

## Modelos

No se cambian los pesos de producción en 2.0.1:

- ASR: `Systran/faster-whisper-small`;
- MT: `facebook/m2m100_418M` convertido a CTranslate2 INT8.

Los Model Labs Quality/TriCore/Legacy continúan como R&D/Features y no se promocionan automáticamente.

## i3 Haswell

2.0.1 mantiene una ruta CPU conservadora específica para pocos núcleos: en 2C/4T se prioriza ASR sin ejecutar simultáneamente las dos etapas pesadas. Sin embargo, el benchmark físico específico sobre un Intel Core i3 Haswell real **continúa pendiente**. El MegaBench de GitHub es un gate de regresión y no sustituye esa certificación física.

## Gates del candidato final

El mismo SHA debe superar:

1. consistencia de versión, privacidad, extensión y GitHub Pages;
2. Frontend typecheck/tests/build;
3. todos los tests del motor Python y `compileall`;
4. Rust format/tests/Clippy;
5. runtime Python 3.13 privado y bootstrap offline;
6. Native Messaging y flujo instalado;
7. MegaBench real Whisper Small + M2M100;
8. Windows Rust tests y Clippy;
9. Desktop Release y comprobación `WINDOWS_GUI`;
10. bundle Tauri NSIS;
11. instalación limpia del NSIS + ventana visible;
12. reinstalación sobre estado previo/runtime en uso + ventana visible;
13. extensión Chromium, hashes SHA-256 y artefacto final del mismo SHA.

## Artefactos

La release válida debe publicar desde un único SHA:

- `MilyVoiceTraductor_2.0.1_x64-setup.exe`;
- `MilyVoiceTraductor-Chromium-Extension.zip`;
- `MilyVoiceTraductor-2.0.1-MegaBench.json`;
- `SHA256SUMS.txt`.

Los binarios 2.0.1 no se presentan como Authenticode-firmados mientras no exista una identidad de firma legítima configurada; SHA-256 verifica integridad, pero no sustituye una firma de código.
