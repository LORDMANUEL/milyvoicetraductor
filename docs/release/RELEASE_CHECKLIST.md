# Checklist de release

- [ ] `python scripts/verify_source.py`
- [ ] `npm ci` o instalación reproducible equivalente.
- [ ] `npm run typecheck`
- [ ] `npm test`
- [ ] `npm run build`
- [ ] `cargo fmt --all -- --check`
- [ ] `cargo test --workspace`
- [ ] `cargo clippy --workspace --all-targets -- -D warnings`
- [ ] Build release Windows y Linux en CI.
- [ ] Construir/validar sidecar.
- [ ] Revisar licencias y revisiones de modelos.
- [ ] Escaneo de secretos limpio.
- [ ] Firmar binarios/instalador fuera del repositorio.
- [ ] Generar SHA-256 de artefactos.
- [ ] Publicar release y luego probar actualización desde una instalación anterior.
