# MilyVoice 3 Contracts Kernel Implementation Plan

**Goal:** Establish `contracts/` as a language-neutral, versioned and compatibility-checked boundary, starting with `supervisor/v1` and without modifying the already integrated F1 Supervisor source.

**Architecture:** JSON contract manifests + compatibility locks + examples, validated with Python stdlib and a path-scoped GitHub Actions workflow. F2 is tooling/data only and does not join the 2.1.x runtime graph.

**Spec:** `docs/superpowers/specs/2026-08-23-milyvoice-3-contracts-kernel-design.md`

## Constraints

- Do not modify `crates/mily-supervisor/**`.
- Do not modify root Cargo workspace/lock or product `VERSION`.
- Do not modify ASR/MT/TTS/audio/realtime/models/Desktop/extension/installer.
- Only `supervisor/v1` is introduced in F2; domain contracts are owned by later module PRs.
- A compatibility lock for v1 is immutable; breaking evolution creates v2.

### Task 1 — Validator RED

Files:
- Create `scripts/test_v3_contracts.py`
- Create `.github/workflows/v3-contracts.yml`

Steps:
- [ ] Write validator expecting `contracts/index.json` and `supervisor/v1`.
- [ ] Add workflow that runs validator.
- [ ] Verify CI RED only because contract registry/files do not yet exist.

### Task 2 — Registry + contract GREEN

Files:
- Create `contracts/README.md`
- Create `contracts/index.json`
- Create `contracts/supervisor/v1/contract.json`

Steps:
- [ ] Define registry entry for `supervisor/v1`.
- [ ] Define portable messages/enums matching F1.
- [ ] Validator checks path/id, owner, status, type references and required fields.
- [ ] Verify next failure is specifically missing compatibility lock/examples, not descriptor syntax.

### Task 3 — Compatibility lock

Files:
- Create `contracts/supervisor/v1/compatibility.lock.json`

Steps:
- [ ] Lock every existing supervisor v1 field type/requiredness.
- [ ] Lock existing enum values.
- [ ] Reject removed/renamed/type-changed fields.
- [ ] Reject new required fields in existing locked messages.
- [ ] Allow new optional fields.

### Task 4 — Producer/consumer fixtures

Files:
- Create `contracts/supervisor/v1/examples/manifest.json`
- Create `contracts/supervisor/v1/examples/health-report.json`
- Create `contracts/supervisor/v1/examples/health-snapshot.json`

Steps:
- [ ] Validate each fixture against its declared message.
- [ ] Validate arrays, objects, enums, nullable strings and booleans.
- [ ] Confirm fixtures mirror F1 semantics and manifest order.

### Task 5 — Validator self-test + GREEN

Files:
- Extend `scripts/test_v3_contracts.py` with in-memory negative compatibility checks.

Steps:
- [ ] Prove field removal fails.
- [ ] Prove type change fails.
- [ ] Prove new required field fails.
- [ ] Prove optional additive field passes.
- [ ] Prove enum removal fails.
- [ ] Run workflow and require PASS.

### Task 6 — Boundary gate

Allowed F2 paths:

```text
.github/workflows/v3-contracts.yml
contracts/**
scripts/test_v3_contracts.py
docs/superpowers/specs/2026-08-23-milyvoice-3-contracts-kernel-design.md
docs/superpowers/plans/2026-08-23-milyvoice-3-contracts-kernel.md
```

Steps:
- [ ] Confirm `crates/mily-supervisor/**` unchanged from `v3/integration`.
- [ ] Confirm 2.1.x runtime files unchanged.
- [ ] Require Contracts Kernel CI green on exact head SHA.
- [ ] Merge only into `v3/integration`.

F2 completion promotes the **contract infrastructure** to candidate. `supervisor/v1` remains candidate until a second module consumes it in an integration test.