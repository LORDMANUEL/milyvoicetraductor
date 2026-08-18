use crate::{BackendObservation, ComputeBackend};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BenchmarkSample {
    pub latency_ms: f32,
    pub workload_ms: f32,
    pub memory_mb: u64,
    pub success: bool,
}

fn sample_valid(sample: &BenchmarkSample) -> bool {
    sample.success
        && sample.latency_ms.is_finite()
        && sample.workload_ms.is_finite()
        && sample.latency_ms >= 0.0
        && sample.workload_ms > 0.0
}

fn p95(mut values: Vec<f32>) -> f32 {
    if values.is_empty() {
        return 0.0;
    }
    values.sort_by(f32::total_cmp);
    let index = (((values.len() - 1) as f32) * 0.95).ceil() as usize;
    values[index.min(values.len() - 1)]
}

pub fn summarize_benchmark(
    backend: ComputeBackend,
    samples: &[BenchmarkSample],
) -> BackendObservation {
    let valid: Vec<_> = samples
        .iter()
        .filter(|sample| sample_valid(sample))
        .collect();
    let latency_ms = p95(valid.iter().map(|sample| sample.latency_ms).collect());
    let rtf = p95(valid
        .iter()
        .map(|sample| sample.latency_ms / sample.workload_ms)
        .collect());
    let memory_mb = valid
        .iter()
        .map(|sample| sample.memory_mb)
        .max()
        .unwrap_or(0);

    BackendObservation {
        backend,
        available: !samples.is_empty(),
        successful: samples.len() >= 3 && valid.len() == samples.len(),
        latency_ms,
        rtf,
        memory_mb,
    }
}
