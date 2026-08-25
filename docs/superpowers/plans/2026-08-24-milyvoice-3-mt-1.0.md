# MilyVoice 3 — F8B MT 1.0.0 Implementation Plan

## Task 1 — Establish isolated MT package and RED gate
- add `services/mt/COMPONENT.json` as `development`;
- add stdlib-only package metadata;
- add Linux/Windows workflow;
- write adapter tests before implementation;
- verify RED is caused only by missing `mily_mt`.

## Task 2 — Implement provider-neutral MT adapter
- lazy factory/budget imports;
- exact route validation;
- provider conflict validation;
- load/invoke/unload/health;
- quality/fidelity reports from Linguistic;
- no context prompt synthesis in 1.0.0.

## Task 3 — Integrate Engine Host + Linguistic
- create real `PreparedTranslationInput` through `prepare_translation_input`;
- register/load/invoke both candidate MT adapters through Engine Host;
- verify one failing adapter does not affect the other.

## Task 4 — Lock current provider/model-pack compatibility
- assert `TRANSLATION_BUILDERS` exposes `marian-ct2` and `marian-cascade-ct2`;
- assert `build_translation_provider` signature remains compatible;
- assert current lite packs map EN->ES and ZH->ES to those providers;
- explicitly assert no reverse-route pack is promoted accidentally.

## Task 5 — Publish `mt/v1`
- registry RED first;
- descriptor, compatibility lock, request/result fixtures;
- Contracts Kernel GREEN.

## Task 6 — Promote lifecycle and composition
- metadata RED then `development -> candidate`;
- composition RED then add MT to product manifest;
- product target `3.0.0-alpha.4-dev.3` unless a concurrent integration legitimately advances the line first.

## Task 7 — Exact-head certification
Require success on:
- V3 MT Linux/Windows + contract/composition;
- Contracts Kernel;
- Linguistic;
- Engine Host;
- ASR;
- Realtime;
- Audio;
- Compute;
- Supervisor.

Perform boundary check and merge only into `v3/integration`.
