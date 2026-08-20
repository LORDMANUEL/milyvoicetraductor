# MilyVoiceTraductor 2.1.0

MilyVoiceTraductor 2.1 estabiliza la experiencia local EN→ES para Windows con un pipeline de baja latencia y límites estrictos de recursos.

## Motores estables

- Moonshine Lite EN→ES.
- Whisper Tiny Lite EN→ES.
- Sherpa Zipformer Lite EN→ES.
- Selección automática basada en benchmark real de la máquina.
- Mandarin ZH→ES permanece experimental y no bloquea la versión estable.

## Rendimiento y recursos

La release exige para cada ruta Lite estable:

- producto total ≤ 1536 MB durante el benchmark;
- RTF P95 < 0.80;
- E2E P95 ≤ 1500 ms;
- simulación objetivo de PC con 8 GiB RAM, 2 GiB para MilyVoice y GPU clase 512 MiB.

2.1 añade una caché segura partial→final para Marian EN→ES: cuando el ASR únicamente agrega un punto final, se reutiliza la traducción ya validada en lugar de ejecutar otra inferencia completa. Preguntas y exclamaciones siguen pasando por el modelo para no cambiar intención.

## Windows e instalación

La certificación exige:

- Rust tests y Clippy en Linux y Windows;
- Desktop Release y subsistema `WINDOWS_GUI`;
- bundle Tauri NSIS;
- parser real de Windows PowerShell 5.1 para scripts incluidos;
- instalación limpia silenciosa;
- arranque del EXE con ventana visible;
- Native Messaging para Chrome, Edge y Brave;
- reinstalación sobre configuración existente;
- reinstalación con runtime Python privado activo/bloqueado;
- extensión Chromium, SHA-256 y artefacto Windows final.

## Privacidad

El motor estable funciona localmente. Los proveedores cloud permanecen opcionales y requieren consentimiento explícito.
