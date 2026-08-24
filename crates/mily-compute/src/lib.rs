//! Selección de cómputo de MilyVoice.
//!
//! Este crate no ejecuta todavía CUDA, DirectML, Windows ML, OpenVINO ni Vulkan.
//! Mantiene el contrato liviano para detectar candidatos y escogerlos únicamente
//! después de medir inferencia real. CPU siempre existe como fallback seguro.

mod benchmark;
mod cache;
mod compatibility;
mod memory;
mod registry;
mod runtime;

pub use benchmark::{BenchmarkSample, summarize_benchmark};
pub use cache::{BenchmarkKey, CachedSelection, SelectionCache};
pub use compatibility::{ModelComputeProfile, compatible_backends};
pub use memory::{MemoryBudget, MemoryBudgetInput, MemoryTier, calculate_memory_budget};
pub use registry::BackendRegistry;
pub use runtime::{RuntimeProbe, SystemRuntimeProbe, discover_runtime_backends};

use serde::{Deserialize, Serialize};
use std::cmp::Ordering;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum ComputeBackend {
    Cpu,
    Cuda,
    DirectMl,
    WindowsMl,
    OpenVino,
    Vulkan,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum BackendStatus {
    Ready,
    DetectedNotReady,
    Unavailable,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BackendCapability {
    pub backend: ComputeBackend,
    /// El runtime/API parece presente en el equipo.
    pub runtime_detected: bool,
    /// Existe un adaptador MilyVoice capaz de ejecutar el modelo activo.
    pub adapter_ready: bool,
    /// Evidencia no sensible para diagnóstico local.
    pub evidence: Vec<String>,
}

impl BackendCapability {
    pub fn cpu() -> Self {
        Self {
            backend: ComputeBackend::Cpu,
            runtime_detected: true,
            adapter_ready: true,
            evidence: vec!["fallback nativo".into()],
        }
    }

    pub fn status(&self) -> BackendStatus {
        match (self.runtime_detected, self.adapter_ready) {
            (true, true) => BackendStatus::Ready,
            (true, false) => BackendStatus::DetectedNotReady,
            (false, _) => BackendStatus::Unavailable,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BackendCapabilityState {
    pub backend: ComputeBackend,
    pub status: BackendStatus,
    pub evidence: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BackendObservation {
    pub backend: ComputeBackend,
    pub available: bool,
    pub successful: bool,
    pub latency_ms: f32,
    pub rtf: f32,
    pub memory_mb: u64,
}

impl BackendObservation {
    fn is_valid_measurement(&self) -> bool {
        self.available
            && self.successful
            && self.latency_ms.is_finite()
            && self.rtf.is_finite()
            && self.latency_ms >= 0.0
            && self.rtf >= 0.0
    }
}

/// Escoge el backend que realmente rindió mejor en el equipo.
///
/// RTF es la métrica principal porque expresa si el pipeline sostiene tiempo
/// real. Latencia rompe empates y memoria queda como tercer criterio. Si no hay
/// ninguna medición válida, CPU es el fallback obligatorio.
pub fn select_best_backend(observations: &[BackendObservation]) -> ComputeBackend {
    observations
        .iter()
        .filter(|observation| observation.is_valid_measurement())
        .min_by(|left, right| compare_observations(left, right))
        .map(|observation| observation.backend)
        .unwrap_or(ComputeBackend::Cpu)
}

fn compare_observations(left: &BackendObservation, right: &BackendObservation) -> Ordering {
    left.rtf
        .total_cmp(&right.rtf)
        .then_with(|| left.latency_ms.total_cmp(&right.latency_ms))
        .then_with(|| left.memory_mb.cmp(&right.memory_mb))
}

/// Reporte inicial deliberadamente conservador. Detectar un runtime no significa
/// que el modelo activo sea compatible; esa bandera solo cambia cuando el
/// adaptador correspondiente existe y supera un benchmark real.
pub fn conservative_capability_report(
    detected_runtimes: &[(ComputeBackend, bool, String)],
) -> Vec<BackendCapability> {
    let mut report = vec![BackendCapability::cpu()];
    for (backend, detected, evidence) in detected_runtimes {
        if *backend == ComputeBackend::Cpu {
            continue;
        }
        report.push(BackendCapability {
            backend: *backend,
            runtime_detected: *detected,
            adapter_ready: false,
            evidence: if evidence.trim().is_empty() {
                Vec::new()
            } else {
                vec![evidence.clone()]
            },
        });
    }
    report
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn capability_detection_never_claims_unimplemented_gpu_adapter() {
        let report = conservative_capability_report(&[
            (ComputeBackend::DirectMl, true, "runtime Windows".into()),
            (ComputeBackend::Vulkan, true, "loader".into()),
        ]);
        assert!(report[0].adapter_ready);
        assert!(report[0].runtime_detected);
        assert!(report.iter().skip(1).all(|item| !item.adapter_ready));
    }
}
