//! Snapshot ligero del equipo. La GPU es opcional y nunca bloquea la app.

use serde::{Deserialize, Serialize};
use sysinfo::System;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SystemSnapshot {
    pub operating_system: String,
    pub architecture: String,
    pub cpu_brand: String,
    pub logical_cpus: usize,
    pub total_memory_mb: u64,
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

        SystemSnapshot {
            operating_system: System::name().unwrap_or_else(|| std::env::consts::OS.into()),
            architecture: std::env::consts::ARCH.into(),
            cpu_brand,
            logical_cpus: system.cpus().len().max(1),
            total_memory_mb: system.total_memory() / 1024 / 1024,
            gpu: detect_optional_gpu_hint(),
        }
    }
}

/// Fase 1 evita librerías GPU pesadas. Solo informa hints confiables disponibles.
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
    }
}
