use mily_compute::{select_best_backend, BackendObservation, ComputeBackend};

fn observation(
    backend: ComputeBackend,
    available: bool,
    successful: bool,
    latency_ms: f32,
    rtf: f32,
    memory_mb: u64,
) -> BackendObservation {
    BackendObservation {
        backend,
        available,
        successful,
        latency_ms,
        rtf,
        memory_mb,
    }
}

#[test]
fn cpu_is_the_safe_fallback_when_no_measured_backend_succeeds() {
    let observations = vec![
        observation(ComputeBackend::Cuda, true, false, 0.0, 0.0, 0),
        observation(ComputeBackend::DirectMl, false, false, 0.0, 0.0, 0),
    ];
    assert_eq!(select_best_backend(&observations), ComputeBackend::Cpu);
}

#[test]
fn fastest_successful_measured_backend_wins_even_if_it_is_not_cuda() {
    let observations = vec![
        observation(ComputeBackend::Cpu, true, true, 480.0, 0.72, 700),
        observation(ComputeBackend::Cuda, true, true, 170.0, 0.30, 900),
        observation(ComputeBackend::DirectMl, true, true, 120.0, 0.21, 760),
        observation(ComputeBackend::Vulkan, true, true, 150.0, 0.25, 720),
    ];
    assert_eq!(
        select_best_backend(&observations),
        ComputeBackend::DirectMl
    );
}

#[test]
fn failed_or_non_finite_measurements_are_never_selected() {
    let observations = vec![
        observation(ComputeBackend::Cpu, true, true, 410.0, 0.65, 650),
        observation(ComputeBackend::OpenVino, true, false, 80.0, 0.10, 600),
        observation(ComputeBackend::Vulkan, true, true, f32::NAN, 0.11, 500),
    ];
    assert_eq!(select_best_backend(&observations), ComputeBackend::Cpu);
}

#[test]
fn rtf_is_primary_and_latency_breaks_close_ties() {
    let observations = vec![
        observation(ComputeBackend::Cpu, true, true, 190.0, 0.31, 500),
        observation(ComputeBackend::OpenVino, true, true, 160.0, 0.31, 700),
    ];
    assert_eq!(
        select_best_backend(&observations),
        ComputeBackend::OpenVino
    );
}
