# MilyVoice 3 Foundation Supervisor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce the first independently versioned MilyVoice 3 component, `mily-supervisor 1.0.0`, providing validated component manifests and a deterministic health registry without changing the global 2.1.0 product version.

**Architecture:** Add one focused Rust crate to the existing workspace. The crate owns only component identity/lifecycle/manifest validation and health snapshots; it does not start processes, choose models, touch audio, or update files. Existing product modules remain unchanged and the repository MegaGate remains the integration boundary.

**Tech Stack:** Rust 2024, serde, serde_json, thiserror, existing Cargo workspace and GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-23-milyvoice-3-modular-architecture-design.md`

## Global Constraints

- Keep global `VERSION`, workspace package version, Desktop, Tauri and extension at 2.1.0 during Foundation.
- Keep the existing product-wide <= 2 GiB RAM policy.
- Do not modify ASR, MT, TTS, audio, realtime, models or installer behavior.
- `mily-supervisor` has independent component version `1.0.0`.
- Foundation manifest component versions use strict `MAJOR.MINOR.PATCH`.
- Component contract identifiers use `<name>/v<major>`.
- A frozen component version is immutable; new behavior requires a new semantic version.

---

### Task 1: Scaffold the independent supervisor crate and prove RED

**Files:**
- Modify: `Cargo.toml`
- Modify: `Cargo.lock`
- Create: `crates/mily-supervisor/Cargo.toml`
- Create: `crates/mily-supervisor/src/lib.rs`
- Create: `crates/mily-supervisor/tests/manifest_contract.rs`

**Interfaces:**
- Consumes: existing Rust workspace.
- Produces: package `mily-supervisor` version `1.0.0`; future public types `ComponentStage`, `ComponentDescriptor`, `ProductDescriptor`, `ProductManifest`, `ManifestError`.

- [ ] **Step 1: Add crate metadata and empty library target**

`crates/mily-supervisor/Cargo.toml`:

```toml
[package]
name = "mily-supervisor"
version = "1.0.0"
edition.workspace = true
license.workspace = true
repository.workspace = true

[dependencies]
serde = { version = "1", features = ["derive"] }
thiserror = "2"
```

`src/lib.rs` contains only module-level documentation so behavior is still absent.

- [ ] **Step 2: Write failing manifest contract tests**

```rust
use mily_supervisor::{
    ComponentDescriptor, ComponentStage, ProductDescriptor, ProductManifest,
};

fn valid_manifest() -> ProductManifest {
    ProductManifest {
        product: ProductDescriptor {
            name: "MilyVoiceTraductor".into(),
            version: "3.0.0-alpha.1".into(),
        },
        components: vec![ComponentDescriptor {
            id: "supervisor".into(),
            version: "1.0.0".into(),
            contract: "supervisor/v1".into(),
            stage: ComponentStage::Candidate,
            required: true,
        }],
    }
}

#[test]
fn valid_manifest_is_accepted() {
    valid_manifest().validate().unwrap();
}

#[test]
fn duplicate_component_ids_are_rejected() {
    let mut manifest = valid_manifest();
    manifest.components.push(manifest.components[0].clone());
    assert!(manifest.validate().is_err());
}

#[test]
fn malformed_component_identity_is_rejected() {
    let mut manifest = valid_manifest();
    manifest.components[0].id = "Bad_ID".into();
    assert!(manifest.validate().is_err());
}

#[test]
fn malformed_component_version_is_rejected() {
    let mut manifest = valid_manifest();
    manifest.components[0].version = "1.0".into();
    assert!(manifest.validate().is_err());
}

#[test]
fn malformed_contract_is_rejected() {
    let mut manifest = valid_manifest();
    manifest.components[0].contract = "supervisor/latest".into();
    assert!(manifest.validate().is_err());
}
```

- [ ] **Step 3: Open a draft PR and run CI to verify RED**

Expected failure: Rust compile errors for missing supervisor public types/methods. A failure caused only by Cargo lock drift must be fixed as scaffolding before accepting RED.

### Task 2: Implement manifest domain and reach GREEN

**Files:**
- Modify: `crates/mily-supervisor/src/lib.rs`
- Test: `crates/mily-supervisor/tests/manifest_contract.rs`

**Interfaces:**
- Produces:
  - `pub enum ComponentStage { Experimental, Development, Candidate, Certified, Frozen }`
  - `pub struct ComponentDescriptor { id, version, contract, stage, required }`
  - `pub struct ProductDescriptor { name, version }`
  - `pub struct ProductManifest { product, components }`
  - `pub fn ProductManifest::validate(&self) -> Result<(), ManifestError>`

- [ ] **Step 1: Implement serializable lifecycle/domain types**

Use `#[serde(rename_all = "camelCase")]` for structs and `#[serde(rename_all = "lowercase")]` for lifecycle values.

- [ ] **Step 2: Implement component ID validation**

Accepted examples: `supervisor`, `mily-audio`, `asr2`. Rejected: empty, starts with digit/hyphen, uppercase, underscore, consecutive/trailing hyphen.

- [ ] **Step 3: Implement strict component release-version validation**

Accept exactly three dot-separated numeric fields (`1.0.0`, `12.3.45`). Reject pre-release/build metadata in component Foundation v1.

- [ ] **Step 4: Implement contract validation**

Accept `<component-like-name>/v<positive-major>`, such as `supervisor/v1`; reject missing slash, `v0`, suffixes and malformed names.

- [ ] **Step 5: Implement manifest invariants**

Reject empty product name/version, empty component list, duplicate IDs and invalid component fields.

- [ ] **Step 6: Run targeted crate tests**

Run:

```bash
cargo test -p mily-supervisor --locked
```

Expected: PASS.

### Task 3: Add health registry with a second RED/GREEN cycle

**Files:**
- Modify: `crates/mily-supervisor/src/lib.rs`
- Create: `crates/mily-supervisor/tests/health_registry.rs`

**Interfaces:**
- Consumes: validated `ProductManifest`.
- Produces:
  - `pub enum HealthStatus { Starting, Healthy, Degraded, Unhealthy, Disabled }`
  - `pub struct ComponentHealth { component_id, status, reason }`
  - `pub struct Supervisor`
  - `Supervisor::new(manifest) -> Result<Self, ManifestError>`
  - `Supervisor::report_health(report) -> Result<(), SupervisorError>`
  - `Supervisor::snapshot() -> Vec<ComponentHealth>`

- [ ] **Step 1: Write failing tests**

Tests must prove:

```rust
#[test]
fn known_component_health_can_be_updated() { /* healthy replaces starting */ }

#[test]
fn unknown_component_health_is_rejected_without_mutating_snapshot() { /* error + identical snapshot */ }

#[test]
fn snapshot_order_is_manifest_order() { /* deterministic diagnostics */ }
```

- [ ] **Step 2: Verify RED**

Run `cargo test -p mily-supervisor --locked`; expected compile failure because health API is absent.

- [ ] **Step 3: Implement minimal health registry**

On `Supervisor::new`, initialize every manifest component as `Starting` with no reason. `report_health` updates only known IDs. `snapshot` returns cloned health records in manifest order.

- [ ] **Step 4: Verify GREEN**

Run `cargo test -p mily-supervisor --locked`; expected PASS.

### Task 4: Add the first V3 composition manifest

**Files:**
- Create: `manifests/milyvoice-3.components.json`
- Create: `crates/mily-supervisor/tests/serialization.rs`

**Interfaces:**
- Produces a machine-readable composition declaration for `3.0.0-alpha.1` containing only the Foundation component initially.

- [ ] **Step 1: Write serialization/round-trip test first**

The test serializes/deserializes a `ProductManifest`, then validates it and asserts lifecycle/required values survive the round trip.

- [ ] **Step 2: Verify RED if serde JSON support is not yet present**

Expected failure: missing serde_json dev dependency or missing derives.

- [ ] **Step 3: Add only the required serde JSON test dependency and manifest file**

Manifest:

```json
{
  "product": {"name": "MilyVoiceTraductor", "version": "3.0.0-alpha.1"},
  "components": [
    {
      "id": "supervisor",
      "version": "1.0.0",
      "contract": "supervisor/v1",
      "stage": "candidate",
      "required": true
    }
  ]
}
```

- [ ] **Step 4: Run targeted tests**

`cargo test -p mily-supervisor --locked` -> PASS.

### Task 5: Repository integration gate

**Files:**
- Modify only if required by existing verification: source-verification allowlists or CI path filters.

**Interfaces:**
- Produces evidence that Foundation does not regress 2.1.x.

- [ ] **Step 1: Run Rust workspace gate**

```bash
cargo fmt --all -- --check
cargo test --workspace --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
```

Expected: PASS.

- [ ] **Step 2: Run repository CI/MegaGate on the PR**

Expected: all existing Frontend, Python AI, Rust, privacy/site/extension and Windows release smoke jobs PASS.

- [ ] **Step 3: Review changed-file boundary**

Allowed paths for F1:

```text
docs/ROADMAP-3.0.0.md
docs/superpowers/specs/2026-08-23-milyvoice-3-modular-architecture-design.md
docs/superpowers/plans/2026-08-23-milyvoice-3-foundation-supervisor.md
Cargo.toml
Cargo.lock
crates/mily-supervisor/**
manifests/milyvoice-3.components.json
```

No ASR/MT/TTS/audio/Desktop/extension/installer behavior files may be part of the PR.

- [ ] **Step 4: Mark PR ready only after green CI**

Foundation is considered complete when the PR carries a green full repository gate and the exact tested head SHA is known.