# MilyVoice 3.0 — Contracts Kernel Design

## Purpose

F2 establishes the language-neutral contract layer that lets independently versioned MilyVoice modules communicate without importing each other's internals. It is intentionally data/tooling only: F2 does not modify `mily-supervisor`, AI engines, audio, Desktop, extension or the 2.1.x runtime.

## Boundary

The kernel owns:

- contract directory convention;
- contract registry/index;
- compatibility policy;
- machine-readable field descriptions;
- compatibility locks;
- producer/consumer examples;
- validation tooling and a path-scoped CI gate.

Domain modules own their own future contracts. F2 introduces only the already implemented `supervisor/v1` contract so the first candidate component has a real external boundary. `compute/v1`, `audio/v1`, `realtime/v1`, etc. will be introduced by their owning module PRs.

## Directory convention

```text
contracts/
  README.md
  index.json
  supervisor/
    v1/
      contract.json
      compatibility.lock.json
      examples/
        manifest.json
        health-report.json
        health-snapshot.json
```

A contract ID is `<name>/v<major>` and its repository path must be `contracts/<name>/v<major>/contract.json`.

## Contract descriptor

Each `contract.json` declares:

- `id` — e.g. `supervisor/v1`;
- `owner` — component ID;
- `status` — `candidate`, `certified` or `frozen` for externally consumable contracts;
- `encoding` — Foundation uses JSON-compatible data;
- `compatibility` — `additive-within-major`;
- `messages` — named structures with fields, types and required fields;
- `enums` — named enum values.

Foundation field types are a deliberately small portable vocabulary:

- `string`
- `boolean`
- `object`
- `array:<MessageName>`
- `enum:<EnumName>`
- nullable types expressed with `nullable: true`.

This is a contract manifest, not an implementation language binding.

## Supervisor v1 surface

The initial external surface reflects the already tested F1 behavior:

- `ProductDescriptor`
- `ComponentDescriptor`
- `ProductManifest`
- `ComponentHealth`
- `HealthSnapshot`

Enums:

- `ComponentStage`: experimental, development, candidate, certified, frozen.
- `HealthStatus`: starting, healthy, degraded, unhealthy, disabled.

A health report for an unknown component is rejected by the provider; that semantic rule is documented as an invariant rather than encoded as a field shape.

## Compatibility policy

A contract major is immutable with respect to already published consumer assumptions.

Within `v1`:

Allowed without a new major:

- add a new optional field;
- add a new message not referenced by existing required fields;
- clarify documentation without changing semantics.

Requires a new contract major:

- remove or rename a locked field;
- change a locked field type;
- change a locked field from optional to required or vice versa;
- add a new required field to an existing message;
- remove or rename a locked enum value;
- change the meaning of an existing field/event;
- change ordering/identity invariants that consumers rely on.

The compatibility lock captures the v1 surface that must remain available. CI validates the current contract against that lock. The lock is not a mechanism to approve breaking changes; a deliberate breaking change must create `v2` instead of editing the v1 lock.

## Registry

`contracts/index.json` is the canonical registry for discoverable contracts. Each entry has:

- `id`;
- `owner`;
- `status`;
- `path`.

The validator rejects duplicate IDs, duplicate paths, malformed IDs and path/id mismatch.

## Examples as producer/consumer fixtures

Each contract version carries JSON examples. CI validates the examples against the machine-readable contract descriptor using Python stdlib only.

This provides a portable contract test that Rust, Python and TypeScript implementations can reuse as fixtures without introducing a runtime dependency.

## Validation

`scripts/test_v3_contracts.py` validates:

1. registry shape and uniqueness;
2. contract path matches contract ID;
3. owner/status/encoding/compatibility values;
4. message definitions and portable field types;
5. required fields exist in the field map;
6. referenced message/enum types exist;
7. compatibility lock is a subset of and still identical to the current public surface;
8. no new required field is introduced outside the lock for an existing locked message;
9. all locked enum values remain present;
10. example fixtures satisfy required fields, types, enums and nullability.

## CI isolation

`.github/workflows/v3-contracts.yml` runs only for contract-kernel paths. It does not run model downloads, Windows packaging or the root Rust workspace because F2 changes no runtime implementation.

F1 remains untouched. That is an intentional proof of the 3.0 rule: a candidate module is consumed through its contract instead of being edited by the next module.

## Completion criteria

F2 is complete when:

- `supervisor/v1` exists and mirrors the F1 public surface;
- compatibility lock protects v1;
- all examples validate;
- intentional breaking mutations are covered by tests/fixtures in the validator self-test;
- the path-scoped Contracts Kernel CI is green;
- the PR changes no F1 source file and no 2.1.x runtime file.
