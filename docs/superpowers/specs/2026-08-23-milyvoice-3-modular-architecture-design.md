# MilyVoice 3.0.0 Modular Architecture Design

## Purpose

MilyVoice 3.0.0 migrates la base 2.1.x hacia componentes con versión, contrato, pruebas, health y ciclo de release independientes. La migración es incremental: 2.1.x permanece como baseline funcional mientras cada componente 3.x se certifica detrás de límites explícitos.

## Architectural choice

Use a **modular hybrid architecture**, not a pure microservice topology.

- Rust modules stay in-process when public APIs provide enough isolation.
- Python inference engines will live behind one lightweight Engine Host rather than one process per feature.
- Browser/Desktop boundaries keep Native Messaging/IPC where a process boundary already exists.
- Every component exposes versioned contracts and health metadata regardless of process placement.

This preserves most microservice isolation without unnecessary RAM/IPC overhead and keeps the product-wide <= 2 GiB target viable.

## Component identity

Every component declares:

- stable `id`;
- semantic `version`;
- versioned `contract` identifier;
- lifecycle `stage`;
- whether it is required for the selected product composition.

Product and component versions are independent. The product manifest pins the exact composition.

## Lifecycle

`experimental -> development -> candidate -> certified -> frozen`

`frozen` means the exact component release is immutable. New behavior requires a new semantic version; consumers may remain on the frozen release until a compatible successor is certified.

## Supervisor boundary

The first 3.x component is `mily-supervisor`. Foundation v1 does only this:

1. validate an in-memory product/component manifest;
2. reject duplicate component IDs;
3. reject malformed IDs, component versions and contract IDs;
4. keep current health for known components;
5. reject reports from unknown components without mutating state;
6. expose deterministic snapshots for future Desktop diagnostics/updater decisions.

It does **not** start/kill processes, choose models, touch audio, own updates or replace existing 2.1.x configuration.

## Manifest rules

Component ID: lowercase ASCII letters, digits and hyphens; begins with a letter; no consecutive or trailing hyphen.

Component version: strict release `MAJOR.MINOR.PATCH` with numeric non-negative fields. Product pre-release strings such as `3.0.0-alpha.1` remain allowed in the product descriptor.

Contract ID: `<name>/v<major>`, with major >= 1, for example `supervisor/v1`.

A manifest must have non-empty product identity, at least one component and unique component IDs.

## Health model

Health is independent from lifecycle stage:

- `starting`
- `healthy`
- `degraded`
- `unhealthy`
- `disabled`

A health report contains component ID, status and an optional machine-readable reason.

## Failure behavior

Invalid manifests fail closed before Supervisor construction. Unknown health reports return an error and preserve the prior snapshot. Process restart policy is deferred to a later supervisor release.

## Compatibility model

A consumer binds to a contract major. Additive compatible evolution can remain inside that major. Breaking changes create a new contract major and explicit compatibility entry.

## Repository migration

Foundation deliberately **does not add `mily-supervisor` to the existing root Cargo workspace**. It creates `crates/mily-supervisor` as an independent nested Cargo workspace with its own component version, lock file and path-scoped CI. This prevents F1 from changing the global `Cargo.lock` or rebuilding the existing 2.1.x Rust graph merely to introduce governance infrastructure.

Later integration may consume the certified Supervisor through a path dependency or process/IPC boundary chosen by the relevant contract phase. Existing 2.1.0 product metadata remains unchanged.

## Machine-readable composition

`manifests/milyvoice-3.components.json` records the intended 3.x composition separately from the 2.1.x runtime metadata. Foundation validates its required fields with a lightweight repository test; Rust JSON deserialization is intentionally deferred until a consuming runtime needs it, avoiding dependencies that do not yet provide runtime value.

## Testing strategy

Foundation uses TDD for:

- valid manifest acceptance;
- duplicate ID rejection;
- ID/version/contract validation;
- known component health update;
- unknown component rejection without mutation;
- deterministic snapshot order.

`mily-supervisor` gets a dedicated path-scoped workflow. The normal repository CI remains the regression gate for the unchanged 2.1.x product.

## Resource behavior

Supervisor Foundation uses only Rust `std`, loads no model runtime, audio stack or WebView, and has no long-running worker. It therefore adds no runtime dependency graph to 2.1.x. A measured process-memory gate becomes mandatory only if a later version introduces a process boundary.

## Non-goals for Foundation

- process orchestration/restart;
- hot updates;
- cryptographic manifest signing;
- engine/model selection;
- audio/realtime changes;
- UI changes;
- changing global product version to 3.0.0;
- refactoring existing root crates.

Those are sequenced in `docs/ROADMAP-3.0.0.md`.