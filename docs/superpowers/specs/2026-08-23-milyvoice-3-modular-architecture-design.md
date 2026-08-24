# MilyVoice 3.0.0 Modular Architecture Design

## Purpose

MilyVoice 3.0.0 will migrate the existing 2.1.x codebase into independently versioned modules with explicit contracts, certification and freeze rules. The migration is incremental: 2.1.x remains the functional baseline while 3.x components are introduced behind compatible boundaries.

## Architectural choice

Use a **modular hybrid architecture**, not a pure microservice topology.

- Rust crates remain in-process when isolation through public APIs is sufficient.
- Python inference engines are hosted behind one lightweight Engine Host instead of spawning one process per feature.
- Browser/Desktop boundaries continue to use Native Messaging/IPC where a process boundary already exists.
- Components expose versioned contracts and health metadata regardless of whether they run in-process or out-of-process.

This gives module-level isolation without violating the product-wide <= 2 GiB memory target through unnecessary process duplication.

## Component identity

Every component declares:

- stable `id`;
- semantic `version`;
- versioned `contract` identifier;
- lifecycle `stage`;
- whether it is required for the current composition.

The product manifest records an exact composition. Product version and component versions are independent.

## Lifecycle

`experimental -> development -> candidate -> certified -> frozen`

`frozen` means the exact released component version is immutable. New behavior requires a new semantic version. Consumers may continue using the frozen version until a newer compatible version is certified.

## Supervisor boundary

The first 3.x component is `mily-supervisor`. Its initial responsibilities are deliberately small:

1. validate a product/component manifest;
2. reject duplicate component IDs;
3. reject malformed component IDs, versions and contract IDs;
4. maintain current health information for known components;
5. reject health reports from unknown components;
6. expose deterministic snapshots suitable for Desktop diagnostics and future updater decisions.

It does **not** initially start/kill processes, download updates, choose AI models or own application configuration. Those behaviors belong to later modules.

## Manifest rules

A component ID uses lowercase ASCII letters, digits and hyphens, begins with a letter and has no consecutive/trailing hyphen.

A version is strict `MAJOR.MINOR.PATCH` with numeric non-negative fields. Pre-release product versions are allowed only in the product field; component v1 foundation stores release versions only so a frozen component is addressable unambiguously.

A contract ID uses `<name>/v<major>`, for example `supervisor/v1` or `audio/v1`.

The manifest must contain at least one component and component IDs must be unique.

## Health model

Health is orthogonal to lifecycle stage:

- `starting`
- `healthy`
- `degraded`
- `unhealthy`
- `disabled`

A health report contains component ID, status and an optional machine-readable reason. The supervisor only accepts reports for components present in its validated manifest.

## Failure behavior

Invalid manifests fail closed before registry construction. An invalid health report does not mutate the current snapshot. Future process restart policy will consume these states but is out of scope for Foundation v1.

## Compatibility model

Contracts are versioned independently. A consumer binds to a major contract version. Additive compatible evolution may happen within that major. Breaking changes create a new contract major and a new compatibility entry.

## Repository migration

The initial implementation adds `crates/mily-supervisor` to the existing Rust workspace. No existing crate is moved. Existing 2.1.0 product metadata remains unchanged on the foundation branch. Later phases introduce `contracts/` only after the supervisor manifest semantics are certified.

## Testing strategy

Foundation uses TDD and Rust integration/unit tests for:

- accepted valid manifest;
- duplicate ID rejection;
- ID/version/contract validation;
- known component health update;
- unknown component health rejection;
- snapshot stability.

The existing repository CI remains the final integration gate so adding the crate cannot silently break Desktop, Python, extension or installer builds.

## Resource behavior

`mily-supervisor` is a data/control-plane component and must not load model runtimes, audio devices or WebView resources. Its memory footprint should remain negligible relative to the 2 GiB application budget; an explicit process-level memory gate will be introduced only if/when Supervisor becomes a process boundary.

## Non-goals for Foundation

- process orchestration/restart;
- hot updates;
- cryptographic manifest signing;
- engine selection;
- model download;
- audio/realtime changes;
- UI changes;
- changing global product version to 3.0.0.

Those are sequenced in `docs/ROADMAP-3.0.0.md`.