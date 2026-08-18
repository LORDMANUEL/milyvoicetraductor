use crate::bootstrap::AppState;
use mily_compute::{BackendCapability, ComputeBackend, conservative_capability_report};
use mily_system::SystemSnapshot;
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

fn truthy_env(name: &str) -> bool {
    std::env::var(name)
        .map(|value| {
            matches!(
                value.trim().to_ascii_lowercase().as_str(),
                "1" | "true" | "yes" | "on"
            )
        })
        .unwrap_or(false)
}

fn runtime_hints(snapshot: &SystemSnapshot) -> Vec<(ComputeBackend, bool, String)> {
    let cuda = snapshot.gpu.is_some() || truthy_env("MILY_BACKEND_CUDA");
    let direct_ml = truthy_env("MILY_BACKEND_DIRECTML");
    let open_vino = truthy_env("MILY_BACKEND_OPENVINO");
    let vulkan = truthy_env("MILY_BACKEND_VULKAN");

    vec![
        (
            ComputeBackend::Cuda,
            cuda,
            if cuda {
                "hint CUDA/NVIDIA detectado; requiere benchmark del modelo activo".into()
            } else {
                "sin evidencia CUDA en el probe ligero".into()
            },
        ),
        (
            ComputeBackend::DirectMl,
            direct_ml,
            if direct_ml {
                "runtime DirectML reportado por el probe instalado".into()
            } else {
                "adaptador DirectML aún no validado en este equipo".into()
            },
        ),
        (
            ComputeBackend::OpenVino,
            open_vino,
            if open_vino {
                "runtime OpenVINO reportado por el probe instalado".into()
            } else {
                "adaptador OpenVINO aún no validado en este equipo".into()
            },
        ),
        (
            ComputeBackend::Vulkan,
            vulkan,
            if vulkan {
                "runtime Vulkan reportado por el probe instalado".into()
            } else {
                "adaptador Vulkan aún no validado en este equipo".into()
            },
        ),
    ]
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
    let legacy_haswell_compatible = system.physical_cpus >= 2 && system.cpu_features.avx2;
    let backends = conservative_capability_report(&runtime_hints(&system));
    let profile = recommended_profile(&system);

    HardwareAdvisor {
        system,
        backends,
        recommended_backend: ComputeBackend::Cpu,
        recommended_profile: profile,
        legacy_haswell_compatible,
        benchmark_required: true,
        message: format!(
            "Perfil {profile}: CPU es el fallback verificado; otros backends se habilitan solo tras benchmark real."
        ),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use mily_system::{CpuFeatures, GpuAdapterInfo, GpuVendor};

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
