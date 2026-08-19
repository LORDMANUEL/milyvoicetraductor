# MilyVoiceTraductor — registro de versiones

Este archivo conserva el historial público de versiones y las dos líneas beta actuales. La versión estable recomendada continúa siendo **v2.0.1**.

## Versiones publicadas

| Versión | Estado | Referencia | Descarga / registro |
|---|---|---|---|
| `v2.0.1` | Estable actual | Merge estable `c8ab5398a82379064de1ac1c9c71738e1e517bbd` | [Instalador](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.1/MilyVoiceTraductor_2.0.1_x64-setup.exe) · [Release/Tag](https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.0.1) · [Notas](RELEASE_NOTES_2.0.1.md) |
| `v2.0.0` | Histórica estable | Merge estable `a92b1b183343a0b17757d31d1b61be9f8de07fe6` | [Instalador](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.0/MilyVoiceTraductor_2.0.0_x64-setup.exe) · [Release/Tag](https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.0.0) · [Notas](RELEASE_NOTES_2.0.0.md) |
| `v1.0.5` | Histórica | Hito de publicación `0a9a8768de5b2b04d64f5f116a7771fdf61ddf12` | [Instalador](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.5/MilyVoiceTraductor_1.0.5_x64-setup.exe) · [Release/Tag](https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v1.0.5) · [Notas](RELEASE_NOTES_1.0.5.md) |
| `v1.0.0-rc.1` | Release Candidate histórica | Hito `d901c1b9534fcddb660a59534ad64434299e96b7` | [Instalador](https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.0-rc.1/MilyVoiceTraductor_1.0.0-rc.1_x64-setup.exe) · [Release/Tag](https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v1.0.0-rc.1) · [Notas](RELEASE_NOTES_RC1.md) |

## Líneas beta conservadas

Las dos betas se mantienen deliberadamente separadas para comparar enfoques distintos. Sus ramas pueden seguir avanzando, por eso este registro conserva además un **snapshot SHA inmutable**.

### Beta A — Engine Hub

- Rama viva: [`pruebas`](https://github.com/LORDMANUEL/milyvoicetraductor/tree/pruebas)
- Snapshot registrado: [`875c182c67bcc4c2984cf15de474602017129f99`](https://github.com/LORDMANUEL/milyvoicetraductor/commit/875c182c67bcc4c2984cf15de474602017129f99)
- Código ZIP de la rama: [pruebas.zip](https://github.com/LORDMANUEL/milyvoicetraductor/archive/refs/heads/pruebas.zip)
- Documento: [BETA_ENGINE_HUB.md](BETA_ENGINE_HUB.md)
- Enfoque: robustez multi-motor, selección automática, Resource Governor y perfiles Lite/Quality.

### Beta B — BetaAlpha

- Rama viva: [`betaalpha`](https://github.com/LORDMANUEL/milyvoicetraductor/tree/betaalpha)
- Snapshot registrado: [`1da9a1090535f8f69639c7def2cc760e4b76364d`](https://github.com/LORDMANUEL/milyvoicetraductor/commit/1da9a1090535f8f69639c7def2cc760e4b76364d)
- Código ZIP de la rama: [betaalpha.zip](https://github.com/LORDMANUEL/milyvoicetraductor/archive/refs/heads/betaalpha.zip)
- Documento: [BETAALPHA_ENGINE.md](BETAALPHA_ENGINE.md)
- Enfoque: rendimiento CPU-first, streaming adaptativo, VAD previo, traducción incremental y motores ASR pequeños.

## Política de registro

1. `main` representa la versión estable publicada.
2. `pruebas` y `betaalpha` son las dos líneas beta mientras dure la comparación.
3. Cada release estable conserva su tag/release y notas.
4. Cada beta conserva un SHA de referencia aunque la rama continúe avanzando.
5. No se mantiene un PR abierto permanentemente solo para representar una beta; la rama y este registro son la fuente histórica.
