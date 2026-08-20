//! Contratos de dominio y DTOs públicos de MilyVoiceTraductor.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum ComponentState {
    Ready,
    Stopped,
    NotInstalled,
    Error,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicError {
    pub code: String,
    pub message: String,
}

impl PublicError {
    pub fn new(code: impl Into<String>, message: impl Into<String>) -> Self {
        Self {
            code: code.into(),
            message: message.into(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EngineRuntimeStatus {
    pub state: ComponentState,
    pub pid: Option<u32>,
    pub port: u16,
    pub message: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ModelPackInfo {
    pub id: String,
    pub version: String,
    pub title: String,
    pub installed: bool,
    pub active: bool,
    pub recommended_ram_gb: u64,
    pub commercial_use: bool,
    pub license_note: String,
    pub tier: String,
    pub routes: Vec<String>,
    /// Huella declarada del motor/modelos sin la interfaz Tauri ni el bridge.
    pub ram_mb: u64,
    pub vram_mb: u64,
    /// Memoria de sistema que puede reservar una iGPU y cuenta contra los 2 GiB.
    pub shared_gpu_mb: u64,
    /// Reserva conservadora para Desktop + Native Messaging bridge.
    pub product_reserve_mb: u64,
    /// Motor + iGPU compartida + reserva base del producto.
    pub estimated_total_product_mb: u64,
    pub engine: String,
    pub supported_backends: Vec<String>,
    pub resource_allowed: bool,
    pub resource_reason: String,
    pub external_allowed: bool,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionSummary {
    pub id: String,
    pub created_at: String,
    pub source_language: String,
    pub target_language: String,
    pub duration_seconds: f64,
    pub segment_count: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AppStatus {
    pub version: String,
    pub engine: ComponentState,
    pub models: ComponentState,
    pub installed_models: usize,
    pub extension_connected: bool,
    pub active_model_pack: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn public_error_serialization_has_no_debug_fields() {
        let error = PublicError::new("CONFIG_READ", "No se pudo leer la configuración.");
        let json = serde_json::to_string(&error).unwrap();
        assert!(json.contains("CONFIG_READ"));
        assert!(!json.contains("backtrace"));
    }

    #[test]
    fn component_state_uses_stable_camel_case_values() {
        assert_eq!(
            serde_json::to_string(&ComponentState::NotInstalled).unwrap(),
            "\"notInstalled\""
        );
    }

    #[test]
    fn model_pack_memory_fields_use_camel_case() {
        let pack = ModelPackInfo {
            id: "lite".into(),
            version: "1".into(),
            title: "Lite".into(),
            installed: true,
            active: true,
            recommended_ram_gb: 2,
            commercial_use: true,
            license_note: "MIT".into(),
            tier: "lite".into(),
            routes: vec!["en-es".into()],
            ram_mb: 780,
            vram_mb: 0,
            shared_gpu_mb: 0,
            product_reserve_mb: 320,
            estimated_total_product_mb: 1100,
            engine: "local-moonshine-lite".into(),
            supported_backends: vec!["cpu".into()],
            resource_allowed: true,
            resource_reason: "OK".into(),
            external_allowed: true,
        };
        let json = serde_json::to_string(&pack).unwrap();
        assert!(json.contains("\"productReserveMb\":320"));
        assert!(json.contains("\"estimatedTotalProductMb\":1100"));
        assert!(!json.contains("product_reserve_mb"));
    }
}
