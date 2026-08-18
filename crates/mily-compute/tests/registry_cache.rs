use mily_compute::{
    BackendObservation, BackendRegistry, BenchmarkKey, CachedSelection, ComputeBackend,
    SelectionCache,
};
use tempfile::tempdir;

#[test]
fn registry_always_starts_with_cpu_ready() {
    let registry = BackendRegistry::new();
    let cpu = registry.capability(ComputeBackend::Cpu).unwrap();
    assert!(cpu.runtime_detected);
    assert!(cpu.adapter_ready);
}

#[test]
fn detected_runtime_is_not_ready_until_adapter_is_validated() {
    let mut registry = BackendRegistry::new();
    registry.register_runtime(ComputeBackend::DirectMl, "DirectML.dll");
    let detected = registry.capability(ComputeBackend::DirectMl).unwrap();
    assert!(detected.runtime_detected);
    assert!(!detected.adapter_ready);

    assert!(registry.mark_adapter_ready(ComputeBackend::DirectMl));
    assert!(registry.capability(ComputeBackend::DirectMl).unwrap().adapter_ready);
}

#[test]
fn cannot_mark_undetected_gpu_backend_ready() {
    let mut registry = BackendRegistry::new();
    assert!(!registry.mark_adapter_ready(ComputeBackend::Vulkan));
}

#[test]
fn cache_is_scoped_to_exact_hardware_and_model_version() {
    let dir = tempdir().unwrap();
    let cache = SelectionCache::new(dir.path().join("selection.json"));
    let key = BenchmarkKey {
        hardware_fingerprint: "i3-4130|8086:0412".into(),
        model_pack: "realtime-m2m100".into(),
        model_version: "1.0.0".into(),
    };
    let observation = BackendObservation {
        backend: ComputeBackend::Cpu,
        available: true,
        successful: true,
        latency_ms: 420.0,
        rtf: 0.71,
        memory_mb: 1250,
    };
    cache
        .save(&CachedSelection {
            key: key.clone(),
            backend: ComputeBackend::Cpu,
            observation,
        })
        .unwrap();

    assert_eq!(cache.load_for(&key).unwrap().unwrap().backend, ComputeBackend::Cpu);

    let changed_model = BenchmarkKey {
        model_version: "1.0.1".into(),
        ..key
    };
    assert!(cache.load_for(&changed_model).unwrap().is_none());
}
