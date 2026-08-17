//! Contratos de dominio y DTOs públicos de MilyVoiceTraductor.
//!
//! No depende de Tauri, SQLite ni Python. Mantener estos tipos pequeños hace
//! que los límites entre UI, runtime y motor sean explícitos y testeables.

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
        assert_eq!(serde_json::to_string(&ComponentState::NotInstalled).unwrap(), "\"notInstalled\"");
    }
}
