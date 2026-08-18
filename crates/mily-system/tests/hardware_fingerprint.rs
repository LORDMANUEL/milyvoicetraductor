use mily_system::{CpuFeatures, GpuAdapterInfo, GpuVendor, SystemSnapshot, hardware_fingerprint};

fn snapshot() -> SystemSnapshot {
    SystemSnapshot {
        operating_system: "Windows".into(),
        architecture: "x86_64".into(),
        cpu_brand: "Intel Core i3-4130".into(),
        logical_cpus: 4,
        physical_cpus: 2,
        total_memory_mb: 8192,
        available_memory_mb: 5000,
        cpu_features: CpuFeatures {
            sse42: true,
            avx: true,
            avx2: true,
            fma: true,
            avx512f: false,
            neon: false,
        },
        gpu: Some("Intel HD Graphics 4400".into()),
    }
}

fn gpu(device_id: u32) -> GpuAdapterInfo {
    GpuAdapterInfo {
        name: "Intel HD Graphics".into(),
        vendor: GpuVendor::Intel,
        vendor_id: 0x8086,
        device_id,
        dedicated_video_memory_mb: 128,
        shared_system_memory_mb: 2048,
        software: false,
    }
}

#[test]
fn fingerprint_ignores_available_ram_because_it_changes_during_runtime() {
    let first = snapshot();
    let mut second = snapshot();
    second.available_memory_mb = 1200;
    assert_eq!(
        hardware_fingerprint(&first, &[gpu(0x041E)]),
        hardware_fingerprint(&second, &[gpu(0x041E)])
    );
}

#[test]
fn fingerprint_is_independent_of_gpu_enumeration_order() {
    let first = gpu(0x041E);
    let second = GpuAdapterInfo {
        name: "Second adapter".into(),
        vendor: GpuVendor::Nvidia,
        vendor_id: 0x10DE,
        device_id: 0x128B,
        dedicated_video_memory_mb: 2048,
        shared_system_memory_mb: 4096,
        software: false,
    };
    assert_eq!(
        hardware_fingerprint(&snapshot(), &[first.clone(), second.clone()]),
        hardware_fingerprint(&snapshot(), &[second, first])
    );
}

#[test]
fn changing_gpu_device_invalidates_fingerprint() {
    assert_ne!(
        hardware_fingerprint(&snapshot(), &[gpu(0x041E)]),
        hardware_fingerprint(&snapshot(), &[gpu(0x161E)])
    );
}
