use mily_compute::{BackendRegistry, ComputeBackend, RuntimeProbe, discover_runtime_backends};
use std::collections::HashSet;

struct FakeProbe {
    libraries: HashSet<&'static str>,
    windows_ml_catalog: bool,
}

impl RuntimeProbe for FakeProbe {
    fn library_available(&self, name: &str) -> bool {
        self.libraries.contains(name)
    }

    fn windows_ml_catalog_available(&self) -> bool {
        self.windows_ml_catalog
    }
}

#[test]
fn detects_runtimes_without_marking_adapters_ready() {
    #[cfg(windows)]
    let (libraries, expected) = (
        HashSet::from(["DirectML.dll", "vulkan-1.dll"]),
        vec![ComputeBackend::DirectMl, ComputeBackend::Vulkan],
    );

    #[cfg(target_os = "linux")]
    let (libraries, expected) = (
        HashSet::from(["libvulkan.so.1"]),
        vec![ComputeBackend::Vulkan],
    );

    #[cfg(not(any(windows, target_os = "linux")))]
    let (libraries, expected): (HashSet<&'static str>, Vec<ComputeBackend>) =
        (HashSet::new(), Vec::new());

    let probe = FakeProbe {
        libraries,
        windows_ml_catalog: false,
    };
    let registry = discover_runtime_backends(&probe);

    for backend in expected {
        let capability = registry
            .capability(backend)
            .expect("el runtime simulado debe detectarse en esta plataforma");
        assert!(capability.runtime_detected);
        assert!(!capability.adapter_ready);
    }
    assert!(registry.capability(ComputeBackend::Cuda).is_none());
}

#[test]
fn windows_ml_requires_catalog_evidence_not_generic_onnxruntime_dll() {
    let generic_ort_only = FakeProbe {
        libraries: HashSet::from(["onnxruntime.dll"]),
        windows_ml_catalog: false,
    };
    let registry = discover_runtime_backends(&generic_ort_only);
    assert!(registry.capability(ComputeBackend::WindowsMl).is_none());

    let catalog = FakeProbe {
        libraries: HashSet::new(),
        windows_ml_catalog: true,
    };
    let registry = discover_runtime_backends(&catalog);
    let capability = registry.capability(ComputeBackend::WindowsMl).unwrap();
    assert!(capability.runtime_detected);
    assert!(!capability.adapter_ready);
}

#[test]
fn cpu_remains_ready_when_no_optional_runtime_exists() {
    let probe = FakeProbe {
        libraries: HashSet::new(),
        windows_ml_catalog: false,
    };
    let registry: BackendRegistry = discover_runtime_backends(&probe);
    let cpu = registry.capability(ComputeBackend::Cpu).unwrap();
    assert!(cpu.runtime_detected && cpu.adapter_ready);
}
