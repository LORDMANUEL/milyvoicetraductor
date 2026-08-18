use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum MemoryTier {
    Constrained,
    Standard,
    Spacious,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct MemoryBudgetInput {
    pub total_memory_mb: u64,
    pub available_memory_mb: u64,
    pub dedicated_gpu_memory_mb: u64,
    pub shared_gpu_memory_mb: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MemoryBudget {
    pub tier: MemoryTier,
    pub reserve_system_mb: u64,
    pub reserve_shared_gpu_mb: u64,
    pub max_model_resident_mb: u64,
    pub cache_limit_mb: u64,
    pub allow_parallel_heavy_stages: bool,
}

pub fn calculate_memory_budget(input: MemoryBudgetInput) -> MemoryBudget {
    let total = input.total_memory_mb.max(1);
    let available = input.available_memory_mb.min(total);

    let reserve_system_mb = match total {
        0..=4096 => 768,
        4097..=8192 => 1280,
        8193..=16384 => 2048,
        _ => 3072,
    };

    // DXGI SharedSystemMemory es capacidad, no consumo actual. Solo reservamos
    // una fracción pequeña en equipos con perfil de iGPU; nunca restamos toda la
    // memoria compartida anunciada.
    let looks_integrated =
        input.dedicated_gpu_memory_mb < 512 && input.shared_gpu_memory_mb >= 1024;
    let reserve_shared_gpu_mb = if looks_integrated {
        (input.shared_gpu_memory_mb / 8).clamp(256, 512)
    } else {
        0
    };

    let max_model_resident_mb = available
        .saturating_sub(reserve_system_mb)
        .saturating_sub(reserve_shared_gpu_mb);
    let cache_limit_mb = (total / 32).clamp(64, 512);

    let tier = if total <= 4096 || available < 2048 {
        MemoryTier::Constrained
    } else if total <= 12288 || available < 8192 {
        MemoryTier::Standard
    } else {
        MemoryTier::Spacious
    };

    let allow_parallel_heavy_stages = tier != MemoryTier::Constrained
        && max_model_resident_mb >= 3072
        && available >= 4096;

    MemoryBudget {
        tier,
        reserve_system_mb,
        reserve_shared_gpu_mb,
        max_model_resident_mb,
        cache_limit_mb,
        allow_parallel_heavy_stages,
    }
}
