use crate::{BackendRegistry, ComputeBackend};

pub trait RuntimeProbe {
    fn library_available(&self, name: &str) -> bool;

    /// Windows ML no se infiere por la presencia de un `onnxruntime.dll`
    /// genérico. La integración real debe consultar su catálogo de EPs.
    fn windows_ml_catalog_available(&self) -> bool {
        false
    }
}

#[derive(Debug, Default, Clone, Copy)]
pub struct SystemRuntimeProbe;

impl RuntimeProbe for SystemRuntimeProbe {
    fn library_available(&self, name: &str) -> bool {
        // Abrir y cerrar el loader es suficiente para discovery. No se resuelve
        // ningún símbolo ni se afirma que un modelo de MilyVoice pueda usarlo.
        unsafe { libloading::Library::new(name) }.is_ok()
    }
}

pub fn discover_runtime_backends(probe: &impl RuntimeProbe) -> BackendRegistry {
    let mut registry = BackendRegistry::new();

    for (backend, libraries) in runtime_library_candidates() {
        if let Some(library) = libraries
            .iter()
            .find(|library| probe.library_available(library))
        {
            registry.register_runtime(backend, format!("runtime loader: {library}"));
        }
    }

    if probe.windows_ml_catalog_available() {
        registry.register_runtime(
            ComputeBackend::WindowsMl,
            "Windows ML ExecutionProviderCatalog disponible",
        );
    }

    registry
}

#[cfg(windows)]
fn runtime_library_candidates() -> Vec<(ComputeBackend, &'static [&'static str])> {
    vec![
        (ComputeBackend::Cuda, &["nvcuda.dll"]),
        (ComputeBackend::DirectMl, &["DirectML.dll"]),
        (ComputeBackend::OpenVino, &["openvino_c.dll"]),
        (ComputeBackend::Vulkan, &["vulkan-1.dll"]),
    ]
}

#[cfg(target_os = "linux")]
fn runtime_library_candidates() -> Vec<(ComputeBackend, &'static [&'static str])> {
    vec![
        (ComputeBackend::Cuda, &["libcuda.so.1", "libcuda.so"]),
        (ComputeBackend::OpenVino, &["libopenvino_c.so"]),
        (ComputeBackend::Vulkan, &["libvulkan.so.1", "libvulkan.so"]),
    ]
}

#[cfg(not(any(windows, target_os = "linux")))]
fn runtime_library_candidates() -> Vec<(ComputeBackend, &'static [&'static str])> {
    Vec::new()
}
