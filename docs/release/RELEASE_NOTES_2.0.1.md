# MilyVoiceTraductor 2.0.1

**Tag:** `v2.0.1`  
**Plataforma:** Windows x64  
**Sitio oficial:** [lordmanuel.github.io/milyvoicetraductor](https://lordmanuel.github.io/milyvoicetraductor/)  
**Release:** [GitHub Releases · v2.0.1](https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.0.1)

MilyVoiceTraductor `2.0.1` toma la base funcional de `2.0` y la consolida como una distribución local más estable, autónoma y preparada para reuniones, pestañas web, micrófono, audio de Windows y archivos multimedia.

La versión mantiene los modelos de producción conocidos y concentra sus cambios en experiencia de instalación, continuidad del audio, traducción realtime, integración con Teams y selección segura de hardware.

## Lo que incluye esta versión

- aplicación nativa para Windows x64 construida con Tauri y Rust;
- interfaz de escritorio para reuniones, archivos, aprendizaje y karaoke;
- extensión Manifest V3 para Chrome, Edge, Brave y otros navegadores Chromium;
- captura de pestaña, micrófono, archivos multimedia y audio del sistema mediante WASAPI;
- runtime Python 3.13 privado, sin depender del Python instalado por el usuario;
- Native Messaging automático entre Desktop y extensión;
- reconocimiento local mediante Faster-Whisper Small;
- traducción mediante M2M100 418M convertido a CTranslate2 INT8;
- subtítulos, TTS local, hablantes, sesiones y exportaciones;
- MilyCompute con CPU universal y NVIDIA CUDA compatible cuando el modelo puede ejecutarse de forma segura;
- MegaBench real de reconocimiento y traducción antes de publicar los artefactos.

## Mejoras agregadas sobre la base 2.0

### Instalación y experiencia Windows

- instalación autónoma con runtime, motor, bridge y herramientas de reparación incluidas;
- preparación automática de la integración con navegadores Chromium;
- reinstalación y actualización sobre una instalación existente;
- aplicación, bridge, motor y reparación ejecutados sin ventanas de consola negras;
- recuperación segura de configuración y base de datos locales;
- una única versión coherente en Desktop, extensión, motor, instalador, sitio y archivos publicados.

### Reuniones, audio y tiempo real

- Teams Web conserva el audio audible de la pestaña a su frecuencia nativa mientras crea una copia independiente a 16 kHz para ASR;
- Teams Desktop puede utilizar una salida WASAPI activa aunque el dispositivo predeterminado permanezca en silencio;
- continuidad de audio entre segmentos para conservar el final de las frases largas;
- colas limitadas y control de presión para priorizar resultados finales;
- inicio automático del motor local desde la extensión cuando está instalado y disponible;
- mejor recuperación de sesiones después de detener o reiniciar el motor.

### MilyCompute y rendimiento

- CPU permanece como backend universal y fallback obligatorio;
- NVIDIA CUDA se utiliza únicamente cuando CTranslate2 puede inicializar realmente los modelos;
- retorno automático a CPU cuando el modo automático no puede usar CUDA;
- inventario de hardware con topología de CPU, SIMD, RAM y adaptadores GPU mediante DXGI;
- medición basada en latencia, RTF y estabilidad en lugar de seleccionar por la marca del dispositivo;
- perfiles conservadores para equipos con pocos núcleos y prioridad de resultados finales;
- telemetría técnica local de ASR, traducción, colas y dispositivo realmente utilizado.

### Producto y publicación

- GitHub Pages presenta MilyVoiceTraductor como producto y enlaza directamente la versión `2.0.1`;
- README comercial con beneficios, usos, instalación y descargas oficiales;
- instalador, extensión, MegaBench y hashes generados desde una misma revisión verificada;
- tag estable definido como **`v2.0.1`**.

## Problemas resueltos en 2.0.1

- la actualización podía quedar incompleta cuando el runtime privado anterior seguía utilizando archivos;
- configuraciones JSON malformadas podían impedir el inicio normal de la aplicación;
- una base SQLite local dañada podía bloquear el arranque en lugar de recuperarse de forma segura;
- el remuestreo del AudioWorklet podía acumular deriva durante capturas largas;
- Teams Desktop podía escuchar la salida predeterminada aunque la reunión se reprodujera por otro dispositivo;
- el límite de duración de un segmento podía dejar fuera muestras PCM restantes;
- una inicialización CUDA fallida podía inutilizar la sesión en vez de volver a CPU;
- la extensión podía mantener bloqueado el inicio cuando el motor estaba instalado pero detenido;
- componentes auxiliares podían mostrar consolas de Windows durante preparación o reparación;
- diferentes componentes podían mostrar textos o enlaces de una versión anterior.

## Alcance exacto de aceleración

MilyVoiceTraductor `2.0.1` cuenta con ejecución real mediante:

- **CPU**, disponible en todos los equipos soportados;
- **NVIDIA CUDA compatible**, cuando CTranslate2 puede inicializar y ejecutar el modelo.

Windows ML, DirectML, OpenVINO y Vulkan forman parte de la arquitectura de MilyCompute y pueden detectarse como candidatos, pero `2.0.1` no los presenta todavía como backends activos de inferencia sin ejecución y benchmark real.

## Modelos de producción

Esta versión conserva el baseline estable:

```text
ASR: Systran/faster-whisper-small
MT : facebook/m2m100_418M → CTranslate2 INT8
```

Los Model Labs Quality, TriCore y Legacy permanecen como investigación y no sustituyen automáticamente estos pesos.

## Descargas

La release `v2.0.1` contiene:

- [MilyVoiceTraductor_2.0.1_x64-setup.exe](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.1/MilyVoiceTraductor_2.0.1_x64-setup.exe)
- [MilyVoiceTraductor-Chromium-Extension.zip](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.1/MilyVoiceTraductor-Chromium-Extension.zip)
- [MilyVoiceTraductor-2.0.1-MegaBench.json](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.1/MilyVoiceTraductor-2.0.1-MegaBench.json)
- [SHA256SUMS.txt](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.1/SHA256SUMS.txt)

## Actualización desde 2.0

1. Cierra MilyVoiceTraductor y sus sesiones activas.
2. Ejecuta `MilyVoiceTraductor_2.0.1_x64-setup.exe`.
3. El instalador actualizará los componentes privados y conservará la configuración compatible.
4. Abre la aplicación y confirma que el motor y el modelo aparezcan disponibles.
5. Actualiza la extensión Chromium con el ZIP de `v2.0.1` cuando utilices traducción de pestañas web.

## Integridad y firma

`SHA256SUMS.txt` permite comprobar la integridad de los archivos publicados. Los binarios no se anuncian como firmados con Authenticode mientras no exista una identidad legítima de firma de código configurada para el proyecto.
