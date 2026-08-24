use crate::{BackendRegistry, ComputeBackend, MemoryBudget};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ModelComputeProfile {
    pub supported_backends: Vec<ComputeBackend>,
    pub resident_memory_mb: u64,
}

/// Returns only backends that the model supports, whose adapter is ready and
/// whose resident model footprint fits the current memory budget.
///
/// The order is the registry's deterministic benchmark order. CPU is not forced
/// into the result: it is eligible only when the model explicitly supports it
/// and the model fits in memory. Choosing a smaller fallback model belongs to
/// the model router, not to MilyCompute.
pub fn compatible_backends(
    registry: &BackendRegistry,
    profile: &ModelComputeProfile,
    budget: MemoryBudget,
) -> Vec<ComputeBackend> {
    if profile.resident_memory_mb > budget.max_model_resident_mb {
        return Vec::new();
    }

    registry
        .benchmark_candidates()
        .into_iter()
        .filter(|backend| profile.supported_backends.contains(backend))
        .collect()
}
