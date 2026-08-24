# MilyVoice 3 Contracts

This directory is the language-neutral boundary between independently versioned MilyVoice components.

## Layout

```text
contracts/<name>/v<major>/contract.json
contracts/<name>/v<major>/compatibility.lock.json
contracts/<name>/v<major>/examples/*.json
```

`contracts/index.json` is the canonical registry.

## Compatibility

A consumer binds to a contract major such as `supervisor/v1`.

Within the same major, only backward-compatible evolution is allowed. Existing locked fields may not be removed, renamed, have their type/nullability/requiredness changed, and existing locked enum values may not be removed. New required fields in existing messages are forbidden. New optional fields are allowed.

A breaking change creates a new major (`v2`, `v3`, ...). Do **not** edit `compatibility.lock.json` to make an incompatible v1 change pass.

## Ownership

The domain module owns its contract. A module PR may add or evolve only its own contract unless an integration PR explicitly coordinates multiple contract majors.

## Lifecycle

Externally consumable contracts use `candidate`, `certified`, or `frozen`.

- `candidate`: surface is being exercised by consumers.
- `certified`: producer and consumer contract tests pass.
- `frozen`: the exact major surface is protected; breaking work moves to a new major.

Contract lifecycle is independent from runtime health.
