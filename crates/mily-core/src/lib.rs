//! Contratos de dominio y DTOs públicos de MilyVoiceTraductor.
//!
//! Este crate no conoce Tauri, SQLite ni detalles de la interfaz. Su objetivo
//! es mantener estable el lenguaje común entre servicios y adaptadores.

use serde::{Deserialize, Serialize};

/// Estado visible de un componente opcional de la plataforma.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum ComponentState {
    /// El componente existe y está listo para ser utilizado.
    Ready,
    /// El componente existe, pero actualmente está detenido.
    Stopped,
    /// El componente todavía no está instalado en el equipo.
    NotInstalled,
    /// Se detectó un fallo recuperable o permanente.
    Error,
}

/// Contrato mínimo que deberá implementar el motor local de IA en Fase 2.
pub trait EngineManager: Send + Sync {
    /// Devuelve el estado real del motor, sin simular disponibilidad.
    fn status(&self) -> ComponentState;
}

/// Contrato mínimo que deberá implementar el gestor de modelos en Fase 4.
pub trait ModelManager: Send + Sync {
    /// Devuelve el estado real del inventario/model manager.
    fn status(&self) -> ComponentState;
    /// Cantidad de modelos realmente instalados.
    fn installed_count(&self) -> usize;
}

/// Implementación de Fase 1: el motor aún no está instalado.
#[derive(Debug, Default)]
pub struct UnavailableEngineManager;

impl EngineManager for UnavailableEngineManager {
    fn status(&self) -> ComponentState {
        ComponentState::NotInstalled
    }
}

/// Implementación de Fase 1: no existen modelos instalados todavía.
#[derive(Debug, Default)]
pub struct UnavailableModelManager;

impl ModelManager for UnavailableModelManager {
    fn status(&self) -> ComponentState {
        ComponentState::NotInstalled
    }

    fn installed_count(&self) -> usize {
        0
    }
}

/// Error seguro que puede cruzar el límite IPC hacia la interfaz.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicError {
    pub code: String,
    pub message: String,
}

impl PublicError {
    /// Construye un error público con un código estable y mensaje no sensible.
    pub fn new(code: impl Into<String>, message: impl Into<String>) -> Self {
        Self {
            code: code.into(),
            message: message.into(),
        }
    }
}

/// Resumen de estado mostrado por el panel principal.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AppStatus {
    pub version: String,
    pub engine: ComponentState,
    pub models: ComponentState,
    pub installed_models: usize,
    pub extension_connected: bool,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn phase_one_engine_reports_not_installed() {
        let engine = UnavailableEngineManager;
        assert_eq!(engine.status(), ComponentState::NotInstalled);
    }

    #[test]
    fn phase_one_model_manager_is_truthful() {
        let models = UnavailableModelManager;
        assert_eq!(models.status(), ComponentState::NotInstalled);
        assert_eq!(models.installed_count(), 0);
    }

    #[test]
    fn public_error_contains_only_explicit_safe_fields() {
        let error = PublicError::new("CONFIG_READ", "No se pudo leer la configuración.");
        let json = serde_json::to_string(&error).expect("serialize public error");
        assert!(json.contains("CONFIG_READ"));
        assert!(!json.contains("backtrace"));
    }
}
