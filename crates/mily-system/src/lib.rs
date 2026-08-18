//! Snapshot ligero del equipo. La GPU es opcional y nunca bloquea la app.

use serde::{Deserialize, Serialize};
use sysinfo::System;

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CpuFeatures {
    pub sse42: bool,
    pub avx: bool,
    pub avx2: bool,
    pub fma: bool,
    pub avx512f: bool,
    pub neon: bool,
}

impl CpuFeatures {
    fn detect() -> Self {
        let mut features = Self::default();

        #[cfg(any(target_arch = "x86", target_arch = "x86_64"))]
        {
            features.sse42 = std::arch::is_x86_feature_detected!("sse4.2");
            features.avx = std::arch::is_x86_feature_detected!("avx");
            features.avx2 = std::arch::is_x86_feature_detected!("avx2");
            features.fma = std::arch::is_x86_feature_detected!("fma");
            features.avx512f = std::arch::is_x86_feature_detected!("avx512f");
        }

        // ASIMD/NEON es parte de la arquitectura base AArch64 en los equipos
        // objetivo; no necesitamos una librería de detección adicional.
        #[cfg(target_arch = "aarch64")]
        {
            features.neon = true;
        }

        features
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SystemSnapshot {
    pub operating_system: String,
    pub architecture: String,
    pub cpu_brand: String,
    pub logical_cpus: usize,
    pub physical_cpus: usize,
    pub total_memory_mb: u64,
    pub available_memory_mb: u64,
    pub cpu_features: CpuFeatures,
    pub gpu: Option<String>,
}

/// Servicio sin estado persistente; obtiene información bajo demanda.
#[derive(Debug, Default, Clone)]
pub struct SystemInfoService;

impl SystemInfoService {
    pub fn snapshot(&self) -> SystemSnapshot {
        let mut system = System::new_all();
        system.refresh_all();
        let cpu_brand = system
            .cpus()
            .first()
            .map(|cpu| cpu.brand().trim().to_string())
            .filter(|value| !value.is_empty())
            .unwrap_or_else(|| "Desconocido".into());
        let logical_cpus = system.cpus().len().max(1);
        let physical_cpus = System::physical_core_count()
            .unwrap_or_else(|| logical_cpus.saturating_div(2).max(1))
            .clamp(1, logical_cpus);
        let total_memory_mb = system.total_memory() / 1024 / 1024;
        let available_memory_mb = (system.available_memory() / 1024 / 1024).min(total_memory_mb);

        SystemSnapshot {
            operating_system: System::name().unwrap_or_else(|| std::env::consts::OS.into()),
            architecture: std::env::consts::ARCH.into(),
            cpu_brand,
            logical_cpus,
            physical_cpus,
            total_memory_mb,
            available_memory_mb,
            cpu_features: CpuFeatures::detect(),
            gpu: detect_optional_gpu_hint(),
        }
    }

    /// Variables heredables por el sidecar. Mantienen Python liviano y evitan
    /// que vuelva a inferir topología física con `logical/2`.
    pub fn runtime_environment(&self) -> Vec<(String, String)> {
        let snapshot = self.snapshot();
        vec![
            (
                "MILY_PHYSICAL_CPUS".into(),
                snapshot.physical_cpus.to_string(),
            ),
            (
                "MILY_LOGICAL_CPUS".into(),
                snapshot.logical_cpus.to_string(),
            ),
            (
                "MILY_CPU_AVX2".into(),
                bool_env(snapshot.cpu_features.avx2),
            ),
            (
                "MILY_CPU_FMA".into(),
                bool_env(snapshot.cpu_features.fma),
            ),
            (
                "MILY_CPU_NEON".into(),
                bool_env(snapshot.cpu_features.neon),
            ),
        ]
    }
}

fn bool_env(value: bool) -> String {
    if value { "1" } else { "0" }.into()
}

/// Fase actual evita librerías GPU pesadas. Solo informa hints confiables disponibles.
fn detect_optional_gpu_hint() -> Option<String> {
    for variable in ["NVIDIA_VISIBLE_DEVICES", "CUDA_VISIBLE_DEVICES"] {
        if let Ok(value) = std::env::var(variable)
            && !value.trim().is_empty()
            && value != "void"
            && value != "-1"
        {
            return Some("GPU NVIDIA/CUDA disponible (hint de entorno)".into());
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn snapshot_has_cpu_safe_fallbacks() {
        let snapshot = SystemInfoService.snapshot();
        assert!(!snapshot.operating_system.is_empty());
        assert!(!snapshot.architecture.is_empty());
        assert!(snapshot.logical_cpus >= 1);
        assert!(snapshot.physical_cpus >= 1);
        assert!(snapshot.physical_cpus <= snapshot.logical_cpus);
        assert!(snapshot.available_memory_mb <= snapshot.total_memory_mb);
    }

    #[test]
    fn cpu_feature_contract_is_always_serializable() {
        let snapshot = SystemInfoService.snapshot();
        let json = serde_json::to_string(&snapshot.cpu_features).unwrap();
        assert!(json.contains("avx2"));
        assert!(json.contains("fma"));
    }

    #[test]
    fn runtime_environment_contains_real_cpu_topology() {
        let env = SystemInfoService.runtime_environment();
        let physical = env
            .iter()
            .find(|(key, _)| key == "MILY_PHYSICAL_CPUS")
            .map(|(_, value)| value.parse::<usize>().unwrap())
            .unwrap();
        let logical = env
            .iter()
            .find(|(key, _)| key == "MILY_LOGICAL_CPUS")
            .map(|(_, value)| value.parse::<usize>().unwrap())
            .unwrap();
        assert!(physical >= 1);
        assert!(logical >= physical);
    }
}
