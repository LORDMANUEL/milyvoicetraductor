use crate::{GpuAdapterInfo, SystemSnapshot};

/// Firma local y estable para invalidar benchmarks al cambiar hardware.
///
/// No incluye RAM disponible, nombres de usuario, rutas ni datos de sesión. Los
/// adaptadores se ordenan por PCI IDs para que el orden de enumeración no altere
/// la caché.
pub fn hardware_fingerprint(snapshot: &SystemSnapshot, gpus: &[GpuAdapterInfo]) -> String {
    let mut gpu_ids: Vec<String> = gpus
        .iter()
        .filter(|gpu| !gpu.software)
        .map(|gpu| format!("{:04x}:{:04x}", gpu.vendor_id, gpu.device_id))
        .collect();
    gpu_ids.sort();

    format!(
        "{}|{}|p{}|l{}|ram{}|avx2{}|fma{}|gpu:{}",
        snapshot.cpu_brand.trim().to_ascii_lowercase(),
        snapshot.architecture,
        snapshot.physical_cpus,
        snapshot.logical_cpus,
        snapshot.total_memory_mb,
        u8::from(snapshot.cpu_features.avx2),
        u8::from(snapshot.cpu_features.fma),
        gpu_ids.join(",")
    )
}
