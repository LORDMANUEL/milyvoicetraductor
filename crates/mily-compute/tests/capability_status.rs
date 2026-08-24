use mily_compute::{BackendRegistry, BackendStatus, ComputeBackend};

#[test]
fn cpu_is_explicitly_ready() {
    let registry = BackendRegistry::new();
    assert_eq!(registry.status(ComputeBackend::Cpu), BackendStatus::Ready);
}

#[test]
fn detected_runtime_is_explicitly_not_ready_until_adapter_validation() {
    let mut registry = BackendRegistry::new();
    registry.register_runtime(ComputeBackend::DirectMl, "DirectML.dll");

    assert_eq!(
        registry.status(ComputeBackend::DirectMl),
        BackendStatus::DetectedNotReady
    );

    assert!(registry.mark_adapter_ready(ComputeBackend::DirectMl));
    assert_eq!(
        registry.status(ComputeBackend::DirectMl),
        BackendStatus::Ready
    );
}

#[test]
fn absent_optional_backend_is_explicitly_unavailable() {
    let registry = BackendRegistry::new();
    assert_eq!(
        registry.status(ComputeBackend::Vulkan),
        BackendStatus::Unavailable
    );
}

#[test]
fn capability_snapshot_contains_every_backend_once_in_stable_order() {
    let mut registry = BackendRegistry::new();
    registry.register_runtime(ComputeBackend::OpenVino, "openvino_c");

    let snapshot = registry.capability_snapshot();
    let backends: Vec<ComputeBackend> = snapshot.iter().map(|item| item.backend).collect();

    assert_eq!(
        backends,
        vec![
            ComputeBackend::Cpu,
            ComputeBackend::Cuda,
            ComputeBackend::WindowsMl,
            ComputeBackend::DirectMl,
            ComputeBackend::OpenVino,
            ComputeBackend::Vulkan,
        ]
    );
    assert_eq!(snapshot[0].status, BackendStatus::Ready);
    assert_eq!(snapshot[4].status, BackendStatus::DetectedNotReady);
    assert_eq!(snapshot[5].status, BackendStatus::Unavailable);
}
