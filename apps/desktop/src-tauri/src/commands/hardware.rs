use crate::bootstrap::AppState;
use mily_compute::{
    BackendCapability, ComputeBackend, SystemRuntimeProbe, conservative_capability_report,
    discover_runtime_backends,
};
use mily_system::{GpuAdapterInfo, GpuVendor, SystemSnapshot};
use serde::Serialize;
use tauri::State;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HardwareAdvisor {
    pub system: SystemSnapshot,
    pub backends: Vec<BackendCapability>,
    pub recommended_backend: ComputeBackend,
    pub recommended_profile: &'static str,
    pub legacy_haswell_compatible: bool,
    pub benchmark_required: bool,
    pub message: String,
}

fn cuda_candidate_is_valid(runtime_detected: bool, adapters: &[GpuAdapterInfo]) -> bool {
    runtime_detected
        && adapters
            .iter()
            .any(|adapter| !adapter.software && matches!(adapter.vendor, GpuVendor::Nvidia))
}

fn runtime_hints(adapters: &[GpuAdapterInfo]) -> Vec<(ComputeBackend, bool, String)> {
    let registry = discover_runtime_backends(&SystemRuntimeProbe);
    let physical_gpu = adapters.iter().any(|adapter| !adapter.software);

    [
        ComputeBackend::Cuda,
        ComputeBackend::WindowsMl,
        ComputeBackend::DirectMl,
        ComputeBackend::OpenVino,
        ComputeBackend::Vulkan,
    ]
    .into_iter()
    .map(|backend| {
        let capability = registry.capability(backend);
        let raw_detected = capability
            .map(|item| item.runtime_detected)
            .unwrap_or(false);
        let detected = match backend {
            ComputeBackend::Cuda => cuda_candidate_is_valid(raw_detected, adapters),
            ComputeBackend::DirectMl | ComputeBackend::Vulkan => raw_detected && physical_gpu,
            _ => raw_detected,
        };
        let mut evidence = capability
            .map(|item| item.evidence.join("; "))
            .filter(|item| !item.trim().is_empty())
            .unwrap_or_else(|| "runtime no detectado".into());

        if backend == ComputeBackend::Cuda && raw_detected && !detected {
            evidence.push_str("; no hay adaptador NVIDIA físico asociado");
        }
        if matches!(backend, ComputeBackend::DirectMl | ComputeBackend::Vulkan)
            && raw_detected
            && !physical_gpu
        {
            evidence.push_str("; no hay adaptador GPU físico asociado");
        }
        if detected {
            evidence.push_str("; adapter de modelo todavía requiere ejecución/benchmark");
        }
        (backend, detected, evidence)
    })
    .collect()
}

fn recommended_profile(snapshot: &SystemSnapshot) -> &'static str {
    match snapshot.physical_cpus {
        0..=2 => "legacy",
        3..=5 => "balanced",
        _ => "performance",
    }
}

#[tauri::command]
pub fn get_hardware_advisor(state: State<'_, AppState>) -> HardwareAdvisor {
    let system = state.system.snapshot();
    let adapters = state.system.gpu_inventory();
    let legacy_haswell_compatible = system.physical_cpus >= 2 && system.cpu_features.avx2;
    let backends = conservative_capability_report(&runtime_hints(&adapters));
    let profile = recommended_profile(&system);
    let detected_candidates = backends
        .iter()
        .filter(|item| item.backend != ComputeBackend::Cpu && item.runtime_detected)
        .count();

    HardwareAdvisor {
        system,
        backends,
        // CPU es el único backend que se puede declarar listo antes de que el
        // modelo activo ejecute un benchmark real. El motor Python puede elegir
        // CUDA en Auto únicamente cuando CTranslate2 lo inicializa con éxito.
        recommended_backend: ComputeBackend::Cpu,
        recommended_profile: profile,
        legacy_haswell_compatible,
        benchmark_required: true,
        message: format!(
            "Perfil {profile}: CPU es fallback verificado; {detected_candidates} runtime(s) acelerado(s) son candidatos y deben superar ejecución/benchmark."
        ),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use mily_system::CpuFeatures;

    fn snapshot(physical_cpus: usize, avx2: bool) -> SystemSnapshot {
        SystemSnapshot {
            operating_system: "test".into(),
            architecture: "x86_64".into(),
            cpu_brand: "test".into(),
            logical_cpus: physical_cpus.saturating_mul(2).max(1),
            physical_cpus: physical_cpus.max(1),
            total_memory_mb: 8192,
            available_memory_mb: 4096,
            cpu_features: CpuFeatures {
                avx2,
                ..CpuFeatures::default()
            },
            gpu: None,
        }
    }

    fn gpu(vendor: GpuVendor) -> GpuAdapterInfo {
        GpuAdapterInfo {
            name: "test gpu".into(),
            vendor,
            vendor_id: 0,
            device_id: 1,
            dedicated_video_memory_mb: 0,
            shared_system_memory_mb: 2048,
            software: false,
        }
    }

    #[test]
    fn dual_core_maps_to_legacy_profile() {
        assert_eq!(recommended_profile(&snapshot(2, true)), "legacy");
    }

    #[test]
    fn six_core_maps_to_performance_profile() {
        assert_eq!(recommended_profile(&snapshot(6, true)), "performance");
    }

    #[test]
    fn intel_gpu_never_becomes_cuda_candidate() {
        assert!(!cuda_candidate_is_valid(true, &[gpu(GpuVendor::Intel)]));
    }

    #[test]
    fn amd_gpu_never_becomes_cuda_candidate() {
        assert!(!cuda_candidate_is_valid(true, &[gpu(GpuVendor::Amd)]));
    }

    #[test]
    fn nvidia_requires_cuda_runtime_evidence() {
        assert!(!cuda_candidate_is_valid(false, &[gpu(GpuVendor::Nvidia)]));
        assert!(cuda_candidate_is_valid(true, &[gpu(GpuVendor::Nvidia)]));
    }
}
