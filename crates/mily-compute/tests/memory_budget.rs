use mily_compute::{MemoryBudgetInput, MemoryTier, calculate_memory_budget};

#[test]
fn four_gb_integrated_gpu_is_constrained_and_disables_heavy_parallelism() {
    let budget = calculate_memory_budget(MemoryBudgetInput {
        total_memory_mb: 4096,
        available_memory_mb: 2560,
        dedicated_gpu_memory_mb: 128,
        shared_gpu_memory_mb: 2048,
    });
    assert_eq!(budget.tier, MemoryTier::Constrained);
    assert!(!budget.allow_parallel_heavy_stages);
    assert!(budget.max_model_resident_mb <= 1536);
    assert!(budget.cache_limit_mb <= 128);
}

#[test]
fn eight_gb_machine_gets_standard_budget_without_consuming_all_free_ram() {
    let budget = calculate_memory_budget(MemoryBudgetInput {
        total_memory_mb: 8192,
        available_memory_mb: 6144,
        dedicated_gpu_memory_mb: 0,
        shared_gpu_memory_mb: 4096,
    });
    assert_eq!(budget.tier, MemoryTier::Standard);
    assert!(budget.max_model_resident_mb < 6144);
    assert!(budget.reserve_system_mb >= 1024);
    assert!(budget.cache_limit_mb <= 256);
}

#[test]
fn dedicated_gpu_does_not_reserve_shared_system_ram_like_an_igpu() {
    let integrated = calculate_memory_budget(MemoryBudgetInput {
        total_memory_mb: 8192,
        available_memory_mb: 6000,
        dedicated_gpu_memory_mb: 128,
        shared_gpu_memory_mb: 4096,
    });
    let dedicated = calculate_memory_budget(MemoryBudgetInput {
        total_memory_mb: 8192,
        available_memory_mb: 6000,
        dedicated_gpu_memory_mb: 4096,
        shared_gpu_memory_mb: 4096,
    });
    assert!(dedicated.max_model_resident_mb > integrated.max_model_resident_mb);
}

#[test]
fn sixteen_gb_machine_is_spacious() {
    let budget = calculate_memory_budget(MemoryBudgetInput {
        total_memory_mb: 16384,
        available_memory_mb: 12288,
        dedicated_gpu_memory_mb: 8192,
        shared_gpu_memory_mb: 8192,
    });
    assert_eq!(budget.tier, MemoryTier::Spacious);
    assert!(budget.allow_parallel_heavy_stages);
    assert!(budget.cache_limit_mb <= 512);
}
