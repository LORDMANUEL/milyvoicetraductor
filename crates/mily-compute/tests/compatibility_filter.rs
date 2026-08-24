use mily_compute::{
    BackendRegistry, ComputeBackend, MemoryBudgetInput, ModelComputeProfile,
    calculate_memory_budget, compatible_backends,
};

fn standard_budget() -> mily_compute::MemoryBudget {
    calculate_memory_budget(MemoryBudgetInput {
        total_memory_mb: 8192,
        available_memory_mb: 6144,
        dedicated_gpu_memory_mb: 1024,
        shared_gpu_memory_mb: 0,
    })
}

#[test]
fn compatibility_requires_model_support_and_ready_adapter() {
    let mut registry = BackendRegistry::new();
    registry.register_runtime(ComputeBackend::Cuda, "nvcuda.dll");
    assert!(registry.mark_adapter_ready(ComputeBackend::Cuda));
    registry.register_runtime(ComputeBackend::DirectMl, "DirectML.dll");
    registry.register_runtime(ComputeBackend::OpenVino, "openvino_c");
    assert!(registry.mark_adapter_ready(ComputeBackend::OpenVino));

    let profile = ModelComputeProfile {
        supported_backends: vec![
            ComputeBackend::Cpu,
            ComputeBackend::Cuda,
            ComputeBackend::DirectMl,
        ],
        resident_memory_mb: 768,
    };

    assert_eq!(
        compatible_backends(&registry, &profile, standard_budget()),
        vec![ComputeBackend::Cpu, ComputeBackend::Cuda]
    );
}

#[test]
fn detected_not_ready_backend_is_excluded() {
    let mut registry = BackendRegistry::new();
    registry.register_runtime(ComputeBackend::Vulkan, "vulkan-1");

    let profile = ModelComputeProfile {
        supported_backends: vec![ComputeBackend::Vulkan],
        resident_memory_mb: 256,
    };

    assert!(compatible_backends(&registry, &profile, standard_budget()).is_empty());
}

#[test]
fn model_larger_than_budget_rejects_every_backend() {
    let registry = BackendRegistry::new();
    let budget = standard_budget();
    let profile = ModelComputeProfile {
        supported_backends: vec![ComputeBackend::Cpu],
        resident_memory_mb: budget.max_model_resident_mb + 1,
    };

    assert!(compatible_backends(&registry, &profile, budget).is_empty());
}

#[test]
fn cpu_remains_eligible_when_supported_and_memory_fits() {
    let registry = BackendRegistry::new();
    let profile = ModelComputeProfile {
        supported_backends: vec![ComputeBackend::Cpu],
        resident_memory_mb: 512,
    };

    assert_eq!(
        compatible_backends(&registry, &profile, standard_budget()),
        vec![ComputeBackend::Cpu]
    );
}

#[test]
fn compatible_results_keep_registry_order_not_profile_order() {
    let mut registry = BackendRegistry::new();
    registry.register_runtime(ComputeBackend::Cuda, "nvcuda.dll");
    assert!(registry.mark_adapter_ready(ComputeBackend::Cuda));
    registry.register_runtime(ComputeBackend::DirectMl, "DirectML.dll");
    assert!(registry.mark_adapter_ready(ComputeBackend::DirectMl));

    let profile = ModelComputeProfile {
        supported_backends: vec![
            ComputeBackend::DirectMl,
            ComputeBackend::Cuda,
            ComputeBackend::Cpu,
        ],
        resident_memory_mb: 512,
    };

    assert_eq!(
        compatible_backends(&registry, &profile, standard_budget()),
        vec![
            ComputeBackend::Cpu,
            ComputeBackend::Cuda,
            ComputeBackend::DirectMl,
        ]
    );
}
