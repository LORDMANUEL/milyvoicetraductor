# MilyVoiceTraductor — registro de versiones

Este archivo conserva el historial público de releases y de las líneas experimentales del proyecto.

La versión estable recomendada es **v2.0.2**. Las versiones de la serie 2.1.x continúan como **beta** hasta una promoción explícita a estable.

## Versiones publicadas

| Versión | Estado | Referencia | Descarga / registro |
|---|---|---|---|
| `v2.0.2` | **Estable actual** | Merge estable `cfd3946644c41242e6345c2c593f4edb7a1047b4` · candidata certificada `83a68fb38389b34ec37de7407c5b014097991e0a` | [Instalador](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.2/MilyVoiceTraductor_2.0.2_x64-setup.exe) · [Extensión](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.2/MilyVoiceTraductor-Chromium-Extension.zip) · [MegaBench](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.2/MilyVoiceTraductor-2.0.2-MegaBench.json) · [Release/Tag](https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.0.2) · [Notas](RELEASE_NOTES_2.0.2.md) |
| `v2.1.0` | **Beta pública** | Merge beta `6645be5413a46d92e24b0c37c56b1bb851a94067` | [Instalador beta](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.1.0/MilyVoiceTraductor_2.1.0_x64-setup.exe) · [Extensión beta](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.1.0/MilyVoiceTraductor-Chromium-Extension.zip) · [Release/Tag](https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.1.0) · [Notas](RELEASE_NOTES_2.1.0.md) |
| `v2.0.1` | Histórica estable | Merge estable `c8ab5398a82379064de1ac1c9c71738e1e517bbd` | [Instalador](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.1/MilyVoiceTraductor_2.0.1_x64-setup.exe) · [Release/Tag](https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.0.1) · [Notas](RELEASE_NOTES_2.0.1.md) |
| `v2.0.0` | Histórica estable | Merge estable `a92b1b183343a0b17757d31d1b61be9f8de07fe6` | [Instalador](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.0/MilyVoiceTraductor_2.0.0_x64-setup.exe) · [Release/Tag](https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.0.0) · [Notas](RELEASE_NOTES_2.0.0.md) |
| `v1.0.5` | Histórica | Hito de publicación `0a9a8768de5b2b04d64f5f116a7771fdf61ddf12` | [Instalador](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.5/MilyVoiceTraductor_1.0.5_x64-setup.exe) · [Release/Tag](https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v1.0.5) · [Notas](RELEASE_NOTES_1.0.5.md) |
| `v1.0.0-rc.1` | Release Candidate histórica | Hito `d901c1b9534fcddb660a59534ad64434299e96b7` | [Instalador](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.0-rc.1/MilyVoiceTraductor_1.0.0-rc.1_x64-setup.exe) · [Release/Tag](https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v1.0.0-rc.1) · [Notas](RELEASE_NOTES_RC1.md) |

## Qué corrige v2.0.2

- el instalador prepara runtime, motor, bridge y extensión sin descargar modelos;
- la aplicación abre aunque todavía no exista un modelo activo y lleva al Gestor de modelos;
- un runtime o Native Messaging bridge realmente roto conserva el flujo de reparación;
- NSIS aborta cuando falla el bootstrap en lugar de mostrar una instalación exitosa falsa;
- Visual C++ Runtime se incluye app-local y sus hashes se verifican;
- un pack instalado con archivos corruptos puede repararse mediante reinstalación;
- Model Manager serializa operaciones y limpia errores públicos anteriores;
- instalación limpia, primer arranque sin descargas implícitas y reinstalación se ejercitan con el EXE real en Windows CI.

## Historia de Engine Hub y BetaAlpha

Engine Hub y BetaAlpha forman parte de la historia técnica del canal beta 2.1. Se conservan sus referencias para trazabilidad y comparación de rendimiento.

### Engine Hub

- Rama de desarrollo: [`pruebas`](https://github.com/LORDMANUEL/milyvoicetraductor/tree/pruebas)
- Snapshot histórico registrado: [`875c182c67bcc4c2984cf15de474602017129f99`](https://github.com/LORDMANUEL/milyvoicetraductor/commit/875c182c67bcc4c2984cf15de474602017129f99)
- Documento: [BETA_ENGINE_HUB.md](BETA_ENGINE_HUB.md)
- Enfoque: selección multi-motor, Resource Governor, perfiles Lite/Quality y validación de equipos de bajos recursos.

### BetaAlpha

- Rama experimental: [`betaalpha`](https://github.com/LORDMANUEL/milyvoicetraductor/tree/betaalpha)
- Snapshot histórico registrado: [`1da9a1090535f8f69639c7def2cc760e4b76364d`](https://github.com/LORDMANUEL/milyvoicetraductor/commit/1da9a1090535f8f69639c7def2cc760e4b76364d)
- Documento: [BETAALPHA_ENGINE.md](BETAALPHA_ENGINE.md)
- Enfoque: rendimiento CPU-first, streaming adaptativo y comparación de motores ASR pequeños.

## Política de canales

1. `v2.0.2` es la **estable recomendada**; `v2.0.1` y anteriores quedan como historial.
2. `v2.1.x` y las siguientes versiones nuevas se consideran **beta** mientras estén en validación externa.
3. La portada y README deben ofrecer primero la estable y, por separado, la beta vigente.
4. Cada release conserva tag, notas y hashes.
5. Los experimentos conservan SHA de referencia para trazabilidad.
6. Un release beta no debe convertirse automáticamente en “latest stable” solo porque su CI termine en verde.
