# MilyVoice 3 Foundation Supervisor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce `mily-supervisor 1.0.0` as the first independently versioned 3.x component, with manifest validation, health registry, its own Cargo lock and path-scoped CI, without changing the 2.1.x runtime graph.

**Architecture:** `crates/mily-supervisor` is a nested standalone Rust workspace. Foundation uses only `std`; no new dependency is added to the root workspace. A dedicated workflow validates this module while the existing repository CI proves 2.1.x remains untouched.

**Tech Stack:** Rust 2024, Cargo, GitHub Actions, Python stdlib for repository manifest validation.

**Spec:** `docs/superpowers/specs/2026-08-23-milyvoice-3-modular-architecture-design.md`

## Global Constraints

- Keep global `VERSION`, root Cargo workspace version, Desktop, Tauri and extension at 2.1.0.
- Do not modify root `Cargo.lock` or add Foundation to the root Cargo workspace.
- Keep product-wide <= 2 GiB RAM policy.
- Do not modify ASR, MT, TTS, audio, realtime, models, Desktop, extension or installer behavior.
- `mily-supervisor` version is independently `1.0.0`.
- Component versions use strict `MAJOR.MINOR.PATCH`.
- Contracts use `<name>/v<major>` with major >= 1.
- A frozen component version is immutable.

---

### Task 1: Scaffold standalone crate and prove RED

**Files:**
- Create: `crates/mily-supervisor/Cargo.toml`
- Create: `crates/mily-supervisor/Cargo.lock`
- Create: `crates/mily-supervisor/src/lib.rs`
- Create: `crates/mily-supervisor/tests/manifest_contract.rs`
- Create: `.github/workflows/v3-supervisor.yml`

**Interfaces:**
- Produces package `mily-supervisor` version `1.0.0` and future public domain types.

- [ ] **Step 1: Create isolated Cargo metadata**

```toml
[package]
name = "mily-supervisor"
version = "1.0.0"
edition = "2024"
license = "MIT"
repository = "https://github.com/LORDMANUEL/milyvoicetraductor"

[workspace]
```

The initial lock is deterministic because Foundation has no external crates:

```toml
version = 4

[[package]]
name = "mily-supervisor"
version = "1.0.0"
```

- [ ] **Step 2: Add an empty library target**

`src/lib.rs` contains only crate documentation. It must not define the tested API yet.

- [ ] **Step 3: Write failing manifest tests**

```rust
use mily_supervisor::{ComponentDescriptor, ComponentStage, ProductDescriptor, ProductManifest};

fn valid_manifest() -> ProductManifest {
    ProductManifest {
        product: ProductDescriptor { name: "MilyVoiceTraductor".into(), version: "3.0.0-alpha.1".into() },
        components: vec![ComponentDescriptor {
            id: "supervisor".into(), version: "1.0.0".into(), contract: "supervisor/v1".into(),
            stage: ComponentStage::Candidate, required: true,
        }],
    }
}

#[test] fn valid_manifest_is_accepted() { valid_manifest().validate().unwrap(); }
#[test] fn duplicate_component_ids_are_rejected() {
    let mut m = valid_manifest(); m.components.push(m.components[0].clone()); assert!(m.validate().is_err());
}
#[test] fn malformed_component_identity_is_rejected() {
    let mut m = valid_manifest(); m.components[0].id = "Bad_ID".into(); assert!(m.validate().is_err());
}
#[test] fn malformed_component_version_is_rejected() {
    let mut m = valid_manifest(); m.components[0].version = "1.0".into(); assert!(m.validate().is_err());
}
#[test] fn malformed_contract_is_rejected() {
    let mut m = valid_manifest(); m.components[0].contract = "supervisor/latest".into(); assert!(m.validate().is_err());
}
```

- [ ] **Step 4: Add path-scoped module CI**

Run:

```bash
cargo fmt --manifest-path crates/mily-supervisor/Cargo.toml -- --check
cargo test --manifest-path crates/mily-supervisor/Cargo.toml --locked
cargo clippy --manifest-path crates/mily-supervisor/Cargo.toml --all-targets --locked -- -D warnings
```

- [ ] **Step 5: Open draft PR and verify RED**

Expected failure: unresolved imports/methods from the intentionally empty library, not lock drift or workflow syntax.

### Task 2: Implement manifest domain and reach GREEN

**Files:**
- Modify: `crates/mily-supervisor/src/lib.rs`
- Test: `crates/mily-supervisor/tests/manifest_contract.rs`

**Interfaces produced:**
- `ComponentStage::{Experimental, Development, Candidate, Certified, Frozen}`
- `ComponentDescriptor { id, version, contract, stage, required }`
- `ProductDescriptor { name, version }`
- `ProductManifest { product, components }`
- `ProductManifest::validate() -> Result<(), ManifestError>`

- [ ] **Step 1: Implement public domain types using only std**
- [ ] **Step 2: Validate component IDs** — lowercase ASCII, begins with a letter, digits/hyphens allowed, no consecutive/trailing hyphen.
- [ ] **Step 3: Validate strict component versions** — exactly three numeric fields.
- [ ] **Step 4: Validate contracts** — `<valid-name>/v<positive-major>`.
- [ ] **Step 5: Reject empty product identity, empty component list and duplicate IDs.**
- [ ] **Step 6: Run module CI commands; all manifest tests must PASS.**

### Task 3: Health registry RED/GREEN

**Files:**
- Create: `crates/mily-supervisor/tests/health_registry.rs`
- Modify: `crates/mily-supervisor/src/lib.rs`

**Interfaces produced:**
- `HealthStatus::{Starting, Healthy, Degraded, Unhealthy, Disabled}`
- `ComponentHealth { component_id, status, reason }`
- `Supervisor::new(manifest) -> Result<Supervisor, ManifestError>`
- `Supervisor::report_health(report) -> Result<(), SupervisorError>`
- `Supervisor::snapshot() -> Vec<ComponentHealth>`

- [ ] **Step 1: Write tests first** proving known updates, unknown-ID rejection without mutation, and manifest-order snapshots.
- [ ] **Step 2: Verify RED** from missing health API.
- [ ] **Step 3: Implement minimal registry** — initialize all components `Starting`; update only known IDs; snapshots clone records in manifest order.
- [ ] **Step 4: Verify GREEN** with fmt/test/clippy.

### Task 4: Add machine-readable 3.x composition

**Files:**
- Create: `manifests/milyvoice-3.components.json`
- Create: `scripts/test_v3_component_manifest.py`
- Modify: `.github/workflows/v3-supervisor.yml`

**Interfaces:**
- Produces first composition declaration for `3.0.0-alpha.1` with Supervisor candidate.

- [ ] **Step 1: Write Python validation test before manifest**. It must fail if product name/version, component list, supervisor ID/version/contract/stage/required fields differ from the Foundation contract.
- [ ] **Step 2: Verify RED because manifest is absent.**
- [ ] **Step 3: Add manifest:**

```json
{
  "product": {"name": "MilyVoiceTraductor", "version": "3.0.0-alpha.1"},
  "components": [
    {"id": "supervisor", "version": "1.0.0", "contract": "supervisor/v1", "stage": "candidate", "required": true}
  ]
}
```

- [ ] **Step 4: Add `python scripts/test_v3_component_manifest.py` to module CI and verify GREEN.**

### Task 5: Integration and boundary gate

**Allowed changed paths:**

```text
.github/workflows/v3-supervisor.yml
crates/mily-supervisor/**
manifests/milyvoice-3.components.json
scripts/test_v3_component_manifest.py
docs/ROADMAP-3.0.0.md
docs/superpowers/specs/2026-08-23-milyvoice-3-modular-architecture-design.md
docs/superpowers/plans/2026-08-23-milyvoice-3-foundation-supervisor.md
```

- [ ] **Step 1:** Confirm no root `Cargo.toml`, root `Cargo.lock`, runtime, installer, Desktop, extension, ASR/MT/TTS/audio files changed.
- [ ] **Step 2:** Require `V3 Supervisor` workflow PASS on exact head SHA.
- [ ] **Step 3:** Require existing repository CI PASS on exact head SHA if the repository workflow triggers for the PR.
- [ ] **Step 4:** Mark PR ready only after both relevant gates are green.

Foundation ends with `mily-supervisor 1.0.0` at lifecycle `candidate`; promotion to `certified/frozen` occurs only after the first consumer contract is exercised in F2.