# MilyVoice 3 — Linguistic 1.0 Implementation Plan

**Goal:** Extract proven deterministic translation guards into an independent stdlib-only Linguistic component and add bounded context/terminology preparation for MT.

**Spec:** `docs/superpowers/specs/2026-08-24-milyvoice-3-linguistic-1.0-design.md`

## Constraints

- Do not modify `services/ai/mily_ai/translation_quality.py` or translation providers.
- Production Linguistic has no dependency on `mily_ai`.
- Context is bounded, memory-only and caller-controlled.
- Terminology emits constraints; it never rewrites source/target automatically.
- Global VERSION remains 2.1.0.

### Task 1 — Package/workflow and normalization/context RED

Create:
- `services/linguistic/pyproject.toml`
- `services/linguistic/COMPONENT.json` development
- `.github/workflows/v3-linguistic.yml`
- tests for normalize/segment/terminology/context/preparation.

### Task 2 — Core GREEN

Create:
- `mily_linguistic/core.py`
- `mily_linguistic/__init__.py`

API:
- normalize_text
- segment_sentences
- TerminologyRule / TerminologyBook
- ContextBuffer / ContextItem
- PreparedTranslationInput / prepare_translation_input

### Task 3 — Quality extraction parity

Create:
- `mily_linguistic/quality.py`
- parity tests importing legacy `mily_ai.translation_quality` only in tests.

Require equivalent output for corpus covering repetition, negation, IDs, clocks, decimal prices, small-number words and safe prefix recovery.

### Task 4 — `linguistic/v1`

Register RED, then create contract/lock/fixtures.

### Task 5 — Candidate + alpha.4-dev.2 composition

Test-first metadata and composition promotion.

### Task 6 — Final boundary/gates

Allowed paths:
```text
.github/workflows/v3-linguistic.yml
services/linguistic/**
contracts/index.json
contracts/linguistic/**
manifests/milyvoice-3.components.json
scripts/test_v3_component_manifest.py
docs/superpowers/specs/2026-08-24-milyvoice-3-linguistic-1.0-design.md
docs/superpowers/plans/2026-08-24-milyvoice-3-linguistic-1.0.md
```

Require Linux/Windows Linguistic, parity, Contracts Kernel, composition and cross-gates exact-head. Merge only to `v3/integration`.
