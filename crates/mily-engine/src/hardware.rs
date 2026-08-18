use mily_system::SystemInfoService;

/// Contrato mínimo que Rust hereda al proceso de IA.
///
/// Python no vuelve a consultar topología física ni necesita `psutil`; el
/// launcher nativo es la fuente de verdad para núcleos y SIMD disponibles.
pub fn hardware_runtime_environment() -> Vec<(String, String)> {
    SystemInfoService.runtime_environment()
}
