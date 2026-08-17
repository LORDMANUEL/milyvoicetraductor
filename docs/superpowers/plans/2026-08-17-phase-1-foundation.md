# MilyVoiceTraductor Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a functional, privacy-first Tauri 2 desktop foundation for MilyVoiceTraductor plus a static GitHub Pages landing site in the same repository.

**Architecture:** The desktop app is a Svelte 5 + TypeScript frontend hosted by Tauri 2. Rust owns privileged operations and exposes small commands backed by focused crates for configuration, SQLite, system information, logging, cache, and future engine/model contracts. The GitHub Pages site is a separate static app so it does not increase desktop runtime weight.

**Tech Stack:** Tauri 2, Rust 2024, Svelte 5, TypeScript, Vite, SQLite/rusqlite, serde, tracing, sysinfo, Vitest, GitHub Actions, static HTML/CSS/JS for Pages.

## Global Constraints

- Product version is `0.1.0`.
- Privacy by default; no telemetry and no meeting content in logs/cache.
- No secrets, tokens, usernames, email addresses, full user paths, or environment dumps may be persisted.
- CPU-only machines must work; GPU detection is informative and optional.
- UI, domain, and infrastructure responsibilities remain separated.
- Rust services use structs/traits for stateful responsibilities and substitution; pure functions remain pure.
- Public modules, services, commands, and non-obvious logic are documented in Spanish.
- No fake success states for AI engine/models/extension.
- Every functional module gets a failing test before implementation where executable logic exists.
- No `TODO`, `TBD`, or dead placeholder features in accepted Phase 1 code.

---

### Task 1: Repository foundation, brand tokens, and documentation

**Files:** root workspace manifests, `.gitignore`, `README.md`, `CHANGELOG.md`, `SECURITY.md`, `VERSION`, `packages/brand/*`, `docs/architecture/*`.

**Interfaces:**
- Produces product metadata `0.1.0` and CSS brand tokens used by desktop and website.

- [ ] Create workspace manifests and security-first ignore rules.
- [ ] Add brand palette and official zebra-headphones logo assets.
- [ ] Write README with architecture, prerequisites, development commands, privacy policy summary, and phase status.
- [ ] Add architecture/security documentation and changelog.
- [ ] Validate there are no secret-like values or private paths in tracked text.

### Task 2: Rust core contracts with TDD

**Files:** `crates/mily-core/src/*` and tests.

**Interfaces:**
- Produces `ComponentState`, `EngineManager`, `ModelManager`, `PublicError`, `AppStatus`.
- `EngineManager::status(&self) -> ComponentState`.
- `ModelManager::status(&self) -> ComponentState`.

- [ ] Write failing tests for unavailable engine/model states and safe public errors.
- [ ] Verify tests fail because contracts are absent.
- [ ] Implement minimal documented structs/traits and unavailable implementations.
- [ ] Verify workspace tests pass.

### Task 3: Configuration, cache, logging sanitization, and SQLite with TDD

**Files:** `crates/mily-config`, `crates/mily-cache`, `crates/mily-logging`, `crates/mily-database`.

**Interfaces:**
- `ConfigService::load_or_default() -> Result<AppConfig, ConfigError>`
- `ConfigService::save(&AppConfig) -> Result<(), ConfigError>`
- `CacheService::{put,get,clear,prune}`
- `sanitize_log_message(&str) -> String`
- `DatabaseService::open(path) -> Result<Self, DatabaseError>`

- [ ] Write failing config default/roundtrip tests.
- [ ] Implement atomic JSON configuration with schema version.
- [ ] Write failing sanitizer tests for tokens, emails, Windows/Linux user paths.
- [ ] Implement deterministic redaction and bounded log setup helpers.
- [ ] Write failing cache expiry/limit/clear tests.
- [ ] Implement file cache with metadata and conservative defaults.
- [ ] Write failing SQLite migration/idempotency tests.
- [ ] Implement migration runner and initial tables.
- [ ] Run all Rust tests and lint checks in CI.

### Task 4: System information and application bootstrap with TDD

**Files:** `crates/mily-system`, `apps/desktop/src-tauri/src/bootstrap/*`, Tauri commands.

**Interfaces:**
- `SystemInfoService::snapshot() -> SystemSnapshot`
- Tauri commands: `get_app_status`, `get_system_info`, `get_config`, `save_config`, `get_cache_status`, `clear_cache`.

- [ ] Write failing tests for normalized system snapshot and unknown GPU fallback.
- [ ] Implement lightweight CPU/RAM/OS/architecture detection.
- [ ] Compose services into `AppState`.
- [ ] Expose only safe DTOs through Tauri commands.
- [ ] Verify backend compile/tests in GitHub Actions.

### Task 5: Desktop Svelte UI with TDD

**Files:** `apps/desktop/src/*`, `apps/desktop/src-tauri/tauri.conf.json`, frontend tests.

**Interfaces:**
- Frontend gateway functions matching the Tauri commands in Task 4.
- Routes/views: Panel, Live Translation, Sessions, Models, Permissions, Devices, Settings, Help, About.

- [ ] Write failing component/store tests for navigation and truthful states.
- [ ] Implement typed Tauri gateway with browser-safe development fallback.
- [ ] Implement shell/sidebar, status cards, responsive layout, and brand tokens.
- [ ] Implement each page with functional Phase 1 controls; non-Phase-1 features show `No instalado`/`Disponible en fase posterior`, never false success.
- [ ] Implement Settings persistence and cache clear action.
- [ ] Verify typecheck/tests/build.

### Task 6: GitHub Pages landing site

**Files:** `apps/site/index.html`, `apps/site/styles.css`, `apps/site/app.js`, `apps/site/assets/*`.

**Interfaces:** Static website only; no API, tracking, cookies, or third-party runtime scripts.

- [ ] Write a lightweight DOM smoke-test script that checks required sections and privacy markers.
- [ ] Confirm it fails before the site exists.
- [ ] Implement accessible responsive landing page using emerald/sapphire/bone branding and zebra logo.
- [ ] Include product purpose, local/private architecture, English/Chinese→Spanish roadmap, current Phase 1 status, repository link, and install/build instructions.
- [ ] Verify static assets and links without external trackers.

### Task 7: CI, Pages deployment, secret scanning guards, and release checks

**Files:** `.github/workflows/ci.yml`, `.github/workflows/pages.yml`, scripts under `scripts/`.

**Interfaces:** CI must run Rust format/clippy/test, frontend typecheck/test/build, site smoke test, and repository privacy scan. Pages workflow uploads `apps/site` as Pages artifact.

- [ ] Add privacy scan script and fixture tests.
- [ ] Add CI workflow with pinned major official actions and minimal permissions.
- [ ] Add Pages workflow using official `configure-pages`, `upload-pages-artifact`, and `deploy-pages` actions.
- [ ] Ensure Pages deploy job has only `pages: write` and `id-token: write` plus read-only contents.
- [ ] Push branch and inspect GitHub Actions results; fix any reproducible failures.

### Task 8: Final verification and integration readiness

**Files:** all Phase 1 files.

**Interfaces:** Acceptance criteria from the approved design document.

- [ ] Search repository for `TODO|TBD`, secret patterns, personal paths, and accidental generated files.
- [ ] Verify all CI checks pass or document environment-only blockers with exact evidence.
- [ ] Verify Pages workflow configuration and static site structure.
- [ ] Update README Phase 1 status and CHANGELOG.
- [ ] Open a draft PR from `feat/phase-1` to `main` summarizing architecture, privacy, tests, and next phase.
