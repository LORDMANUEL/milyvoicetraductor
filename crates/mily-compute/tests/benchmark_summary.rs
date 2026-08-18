use mily_compute::{BenchmarkSample, ComputeBackend, summarize_benchmark};

#[test]
fn summarizes_valid_samples_using_p95_and_peak_memory() {
    let samples = vec![
        BenchmarkSample { latency_ms: 100.0, workload_ms: 1000.0, memory_mb: 500, success: true },
        BenchmarkSample { latency_ms: 120.0, workload_ms: 1000.0, memory_mb: 520, success: true },
        BenchmarkSample { latency_ms: 400.0, workload_ms: 1000.0, memory_mb: 510, success: true },
    ];
    let observation = summarize_benchmark(ComputeBackend::Cpu, &samples);
    assert!(observation.available);
    assert!(observation.successful);
    assert_eq!(observation.latency_ms, 400.0);
    assert!((observation.rtf - 0.4).abs() < 0.001);
    assert_eq!(observation.memory_mb, 520);
}

#[test]
fn benchmark_requires_at_least_three_clean_samples() {
    let samples = vec![
        BenchmarkSample { latency_ms: 100.0, workload_ms: 1000.0, memory_mb: 500, success: true },
        BenchmarkSample { latency_ms: 110.0, workload_ms: 1000.0, memory_mb: 500, success: true },
    ];
    assert!(!summarize_benchmark(ComputeBackend::Cpu, &samples).successful);
}

#[test]
fn any_failed_or_invalid_sample_rejects_candidate() {
    let failed = vec![
        BenchmarkSample { latency_ms: 100.0, workload_ms: 1000.0, memory_mb: 500, success: true },
        BenchmarkSample { latency_ms: 110.0, workload_ms: 1000.0, memory_mb: 500, success: false },
        BenchmarkSample { latency_ms: 120.0, workload_ms: 1000.0, memory_mb: 500, success: true },
    ];
    assert!(!summarize_benchmark(ComputeBackend::Vulkan, &failed).successful);

    let invalid = vec![
        BenchmarkSample { latency_ms: 100.0, workload_ms: 1000.0, memory_mb: 500, success: true },
        BenchmarkSample { latency_ms: f32::NAN, workload_ms: 1000.0, memory_mb: 500, success: true },
        BenchmarkSample { latency_ms: 120.0, workload_ms: 0.0, memory_mb: 500, success: true },
    ];
    assert!(!summarize_benchmark(ComputeBackend::DirectMl, &invalid).successful);
}
