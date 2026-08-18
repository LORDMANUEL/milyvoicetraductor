use crate::{BackendCapability, ComputeBackend};
use std::collections::HashMap;

#[derive(Debug, Clone)]
pub struct BackendRegistry {
    capabilities: HashMap<ComputeBackend, BackendCapability>,
}

impl Default for BackendRegistry {
    fn default() -> Self {
        Self::new()
    }
}

impl BackendRegistry {
    pub fn new() -> Self {
        let mut capabilities = HashMap::new();
        capabilities.insert(ComputeBackend::Cpu, BackendCapability::cpu());
        Self { capabilities }
    }

    pub fn capability(&self, backend: ComputeBackend) -> Option<&BackendCapability> {
        self.capabilities.get(&backend)
    }

    pub fn register_runtime(&mut self, backend: ComputeBackend, evidence: impl Into<String>) {
        if backend == ComputeBackend::Cpu {
            return;
        }
        let evidence = evidence.into();
        let capability = self.capabilities.entry(backend).or_insert(BackendCapability {
            backend,
            runtime_detected: false,
            adapter_ready: false,
            evidence: Vec::new(),
        });
        capability.runtime_detected = true;
        if !evidence.trim().is_empty() && !capability.evidence.contains(&evidence) {
            capability.evidence.push(evidence);
        }
    }

    /// Solo permite marcar un adaptador listo si el runtime ya fue detectado.
    pub fn mark_adapter_ready(&mut self, backend: ComputeBackend) -> bool {
        if backend == ComputeBackend::Cpu {
            return true;
        }
        let Some(capability) = self.capabilities.get_mut(&backend) else {
            return false;
        };
        if !capability.runtime_detected {
            return false;
        }
        capability.adapter_ready = true;
        true
    }

    pub fn benchmark_candidates(&self) -> Vec<ComputeBackend> {
        let mut backends: Vec<_> = self
            .capabilities
            .values()
            .filter(|capability| capability.runtime_detected && capability.adapter_ready)
            .map(|capability| capability.backend)
            .collect();
        backends.sort_by_key(|backend| backend_rank(*backend));
        backends
    }
}

fn backend_rank(backend: ComputeBackend) -> u8 {
    match backend {
        ComputeBackend::Cpu => 0,
        ComputeBackend::Cuda => 1,
        ComputeBackend::WindowsMl => 2,
        ComputeBackend::DirectMl => 3,
        ComputeBackend::OpenVino => 4,
        ComputeBackend::Vulkan => 5,
    }
}
