# MilyVoice 3 — Linguistic 1.0 Component Design

## Purpose

F8A introduces `linguistic 1.0.0`, a deterministic stdlib-only text boundary used by MT and later UI/session components. It does not translate text. It centralizes text normalization, sentence segmentation, bounded ephemeral context, explicit terminology constraints, and the fidelity/anti-repetition guards already proven in the 2.x translation pipeline.

## Legacy behavior extracted without modification

`services/ai/mily_ai/translation_quality.py` already implements high-value deterministic protections:
- pathological repeated n-grams;
- repeated sentences;
- safe non-repetitive sentence/ngram prefix recovery;
- EN→ES negation preservation;
- number preservation;
- special handling for small numbers expressed as Spanish words;
- clock expressions such as 9:00/5:30 translated linguistically;
- exact preservation for identifiers/codes, leading-zero values, large numbers and ordinary decimals.

F8A copies that pure-stdlib behavior into `mily_linguistic.quality` and adds a parity corpus test against the legacy module. Legacy files remain untouched.

## Text normalization

`normalize_text(text)`:
- converts Unicode compatibility forms with NFKC;
- normalizes CRLF/CR to LF;
- collapses all whitespace runs to one ASCII space;
- trims surrounding whitespace;
- preserves punctuation/content otherwise;
- returns empty string for empty/whitespace-only input.

NFKC intentionally turns full-width Latin/digits into canonical equivalents before terminology/fidelity checks.

## Sentence segmentation

`segment_sentences(text)` first normalizes text, then splits on terminal punctuation `. ! ? 。 ！ ？` while retaining the punctuation with the segment. A trailing unterminated fragment is emitted as its own segment. It does not perform linguistic sentence inference beyond those deterministic boundaries.

## Terminology

A `TerminologyRule` contains:
- source text;
- target text;
- source language;
- target language;
- case-sensitive flag.

`TerminologyBook` validates non-empty rules and rejects duplicate source terms for the same language route/case mode. `select(text, source_language, target_language)` returns only rules actually present in the normalized source text.

Matching behavior:
- word/phrase terms that begin/end with Unicode word characters use boundaries so `VIN` does not match `VINTAGE`;
- punctuation-bearing terms use escaped substring matching;
- case-insensitive rules use Unicode casefold.

The component does **not** replace source text or translated text automatically. It emits constraints for MT, avoiding accidental semantic mutation before inference.

## Ephemeral context

`ContextBuffer(max_items, max_chars)` stores normalized source turns in memory only.

Rules:
- empty turns are ignored;
- newest turns are retained;
- eviction occurs until both item and total-character limits pass;
- an individual turn larger than `max_chars` is truncated from the left, retaining the most recent suffix;
- `snapshot()` returns immutable ordered items oldest→newest;
- no disk/network persistence.

MT may request context explicitly. F8A never appends the current source implicitly during `prepare`; callers control when a turn becomes history.

## Prepared translation input

`prepare_translation_input(text, source_language, target_language, terminology=None, context=None)` validates non-empty language codes and returns:
- normalized text;
- deterministic sentence segments;
- selected terminology constraints;
- current context snapshot.

This object is provider-neutral and contains no model prompt template. MT decides how much context/terminology a given provider can use.

## Quality/fidelity API

F8A exposes:
- `analyze_translation_quality`;
- `analyze_source_target_fidelity`;
- `non_repetitive_sentence_prefix`;
- `non_repetitive_ngram_prefix`.

Quality reasons remain compatible with legacy: `OK`, `EMPTY`, `REPEATED_SENTENCE`, `REPEATED_NGRAM`, `REPETITION_RATIO`.
Fidelity reasons remain `OK`, `NUMBER_LOST`, `NEGATION_LOST`.

## Contract `linguistic/v1`

Messages:
- TextSegment;
- TerminologyConstraint;
- ContextItem;
- PreparedTranslationInput;
- TranslationQualityReport;
- SourceTargetFidelityReport.

No translated text generation occurs in this contract.

## Lifecycle/composition

- component `linguistic` version `1.0.0`;
- development -> candidate after parity + Linux/Windows gates;
- composition advances `3.0.0-alpha.4-dev.1` -> `3.0.0-alpha.4-dev.2`.

F8B MT becomes the first production consumer of `linguistic/v1`; Linguistic remains candidate until that consumer gate passes.

## Resource/privacy behavior

Production dependencies: Python stdlib only. Context is bounded and memory-only. No audio, transcript history or terminology is persisted automatically.

## Non-goals

- translation/model inference;
- rewriting source text with glossary targets;
- automatic entity extraction/NER;
- semantic embeddings/RAG;
- persistent conversation memory;
- modifying legacy translation providers or quality guards;
- changing ASR/Engine Host/Realtime/Audio/Compute internals.
