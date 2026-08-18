# MilyVoice 4MT Legacy Models v0.3

## Objetivo

Construir cuatro traductores locales directos y especializados para las rutas prioritarias de MilyVoice:

- EN → ES
- ES → EN
- ZH → ES
- ES → ZH

El hardware mínimo de referencia es Intel Core i3 de 4.ª generación (Haswell), 2C/4T, AVX2, sin GPU dedicada. La aplicación no debe activar estos modelos hasta que existan checkpoints reales, exportación INT8 y benchmark físico aprobado.

## Gates obligatorios

- `beam_size=1` para realtime.
- INT8 como artefacto CPU de producción.
- MT P95 <= 500 ms en el perfil Haswell de referencia.
- Pipeline voz→traducción P95 <= 1500 ms.
- RTF P95 <= 0.80.
- La cola de audio no puede crecer sostenidamente.
- Números, cantidades y negaciones son errores críticos.
- Un candidato no se promueve si mejora BLEU/chrF pero rompe latencia realtime.

## Arquitectura

### EN → ES

Base: `Helsinki-NLP/opus-mt_tiny_eng-spa`, 25.4M parámetros, Apache-2.0. Se fine-tunea con corpus paralelo compatible y corpus crítico MilyVoice; posteriormente se exporta a INT8.

### ES → EN

Base: `Helsinki-NLP/opus-mt_tiny_spa-eng`, 25.4M parámetros, Apache-2.0. Sigue el mismo proceso de fine-tuning y exportación.

### ZH → ES

Checkpoint final directo Marian Tiny de aproximadamente 25–26M parámetros. Durante entrenamiento se permite distillation por teacher `zho→eng` Tiny + `eng→spa` Tiny para producir targets, pero la inferencia final NO debe pivotar por inglés.

### ES → ZH

Checkpoint final directo Marian Tiny de aproximadamente 25–26M parámetros. Durante entrenamiento se permite teacher `spa→eng` Tiny + `en→zh`; la inferencia final NO debe pivotar por inglés.

## Datos

- `Helsinki-NLP/tatoeba` CC-BY-2.0 es fuente admitida con atribución.
- Datos de entrenamiento y evaluación deben permanecer separados.
- Corpus crítico propio de MilyVoice cubre números, fechas, horas, negaciones, facturas, pedidos, reuniones, tecnología y conversación corta.
- No incorporar un dataset con licencia incierta o no comercial al checkpoint comercial.

## Integración

El archivo `resources/model-packs.pending.milyvoice-4mt-v0.3.json` registra los cuatro modelos con `enabled=false`.

Un modelo solo puede pasar al catálogo activo cuando:

1. el checkpoint real existe;
2. el hash SHA-256 queda fijado;
3. la exportación INT8 es reproducible;
4. pasa evaluación de calidad;
5. pasa benchmark Haswell;
6. CI valida el manifest/model pack.

## Estado de cómputo remoto al 18-08-2026

Hugging Face está autenticado para la cuenta `LordShadossama` y el conector dispone de acceso a Jobs. Un probe real de Job devolvió `402 Payment Required`, por lo que los checkpoints finales no deben marcarse como entrenados hasta que la cuenta tenga saldo positivo y los Jobs se ejecuten.
