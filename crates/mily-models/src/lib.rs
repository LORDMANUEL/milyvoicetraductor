//! Inventario y operaciones administrativas de packs de IA.
//!
//! Este crate es el límite entre el Desktop Rust y la CLI del motor local.
//! Conserva códigos de error públicos estructurados sin exponer stderr crudo a la UI.

use mily_config::AppPaths;
use mily_core::{ComponentState, ModelPackInfo};
use mily_engine::LaunchSpec;
use serde::Deserialize;
use std::fs;
use std::process::Stdio;
use thiserror::Error;

const MODEL_CATALOG: &str = include_str!("../../../resources/model-packs.json");
const FALLBACK_MODEL_MESSAGE: &str = "La operación sobre modelos no terminó correctamente.";

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
struct Catalog {
    packs: Vec<CatalogPack>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
struct CatalogPack {
    id: String,
    version: String,
    title: String,
    recommended_ram_gb: u64,
    commercial_use: bool,
    license_note: String,
}

/// Forma mínima que la CLI Python puede emitir cuando una operación falla.
#[derive(Debug, Clone, Deserialize)]
struct ModelCliErrorPayload {
    ok: bool,
    code: String,
    message: String,
}

/// Parsea únicamente JSON estructurado; texto arbitrario de stderr nunca cruza a la UI.
fn parse_model_cli_error(bytes: &[u8]) -> Option<ModelError> {
    let text = std::str::from_utf8(bytes).ok()?.trim();
    if text.is_empty() {
        return None;
    }

    // Algunas librerías pueden escribir líneas informativas antes del JSON. Se revisan
    // desde el final porque nuestra CLI escribe el resultado estructurado al terminar.
    for line in text.lines().rev() {
        let Ok(payload) = serde_json::from_str::<ModelCliErrorPayload>(line.trim()) else {
            continue;
        };
        if payload.ok || !valid_public_model_code(&payload.code) {
            continue;
        }
        let message = sanitize_public_message(&payload.message);
        return Some(ModelError::Structured {
            code: payload.code,
            message,
        });
    }
    None
}

fn valid_public_model_code(code: &str) -> bool {
    matches!(
        code,
        "MODEL_NO_NETWORK"
            | "MODEL_NO_SPACE"
            | "MODEL_PROVIDER_ERROR"
            | "MODEL_DOWNLOAD_INTERRUPTED"
            | "MODEL_HASH_MISMATCH"
            | "MODEL_RUNTIME_ERROR"
            | "MODEL_PERMISSION_ERROR"
            | "MODEL_LICENSE_BLOCKED"
    )
}

fn sanitize_public_message(message: &str) -> String {
    let trimmed = message.trim();
    if trimmed.is_empty() || trimmed.len() > 300 {
        return FALLBACK_MODEL_MESSAGE.to_string();
    }
    // Evita convertir accidentalmente rutas/secretos del proveedor en contenido público.
    if trimmed.contains("\\Users\\")
        || trimmed.contains("/home/")
        || trimmed.to_ascii_lowercase().contains("token=")
        || trimmed.to_ascii_lowercase().contains("authorization:")
    {
        return FALLBACK_MODEL_MESSAGE.to_string();
    }
    trimmed.to_string()
}

#[derive(Debug, Clone)]
pub struct ModelManagerService {
    paths: AppPaths,
}

impl ModelManagerService {
    pub fn new(paths: AppPaths) -> Self {
        Self { paths }
    }

    pub fn status(&self) -> ComponentState {
        if self.installed().iter().any(|pack| pack.active) {
            ComponentState::Ready
        } else {
            ComponentState::NotInstalled
        }
    }

    pub fn installed_count(&self) -> usize {
        self.installed().len()
    }

    pub fn catalog(&self) -> Vec<ModelPackInfo> {
        let parsed: Catalog =
            serde_json::from_str(MODEL_CATALOG).unwrap_or(Catalog { packs: vec![] });
        let installed = self.installed();
        parsed
            .packs
            .into_iter()
            .map(|definition| {
                let match_installed = installed.iter().find(|item| item.id == definition.id);
                ModelPackInfo {
                    id: definition.id,
                    version: definition.version,
                    title: definition.title,
                    installed: match_installed.is_some(),
                    active: match_installed.map(|item| item.active).unwrap_or(false),
                    recommended_ram_gb: definition.recommended_ram_gb,
                    commercial_use: definition.commercial_use,
                    license_note: definition.license_note,
                }
            })
            .collect()
    }

    pub fn installed(&self) -> Vec<ModelPackInfo> {
        let state = fs::read_to_string(self.paths.models_dir.join("current.json"))
            .ok()
            .and_then(|text| serde_json::from_str::<serde_json::Value>(&text).ok())
            .and_then(|value| {
                value
                    .get("active")
                    .and_then(|item| item.as_str())
                    .map(str::to_owned)
            });
        let parsed: Catalog =
            serde_json::from_str(MODEL_CATALOG).unwrap_or(Catalog { packs: vec![] });
        let mut output = Vec::new();
        for definition in parsed.packs {
            let metadata = self
                .paths
                .models_dir
                .join("packs")
                .join(&definition.id)
                .join(&definition.version)
                .join("pack.json");
            if !metadata.is_file() {
                continue;
            }
            output.push(ModelPackInfo {
                active: state.as_deref()
                    == Some(&format!("{}@{}", definition.id, definition.version)),
                installed: true,
                id: definition.id,
                version: definition.version,
                title: definition.title,
                recommended_ram_gb: definition.recommended_ram_gb,
                commercial_use: definition.commercial_use,
                license_note: definition.license_note,
            });
        }
        output
    }

    pub fn install(&self, pack_id: &str) -> Result<ModelPackInfo, ModelError> {
        self.run_engine_cli(["install", pack_id])?;
        self.catalog()
            .into_iter()
            .find(|pack| pack.id == pack_id && pack.installed)
            .ok_or(ModelError::InstallFailed)
    }

    pub fn rollback(&self) -> Result<ModelPackInfo, ModelError> {
        self.run_engine_cli(["rollback"])?;
        self.installed()
            .into_iter()
            .find(|pack| pack.active)
            .ok_or(ModelError::InstallFailed)
    }

    pub fn verify(&self, pack_id: &str, version: &str) -> Result<bool, ModelError> {
        match self.run_engine_cli(["verify", pack_id, version]) {
            Ok(()) => Ok(true),
            Err(ModelError::InstallFailed) => Ok(false),
            Err(error) => Err(error),
        }
    }

    pub fn remove(&self, pack_id: &str, version: &str) -> Result<(), ModelError> {
        self.run_engine_cli(["remove", pack_id, version])
    }

    fn run_engine_cli<const N: usize>(&self, args: [&str; N]) -> Result<(), ModelError> {
        let spec = LaunchSpec::discover(&self.paths).ok_or(ModelError::EngineMissing)?;
        let mut command = spec.command();
        command
            .arg("models")
            .arg("--data-dir")
            .arg(&self.paths.data_dir)
            .arg("--config-dir")
            .arg(&self.paths.config_dir)
            .arg("--cache-dir")
            .arg(&self.paths.cache_dir)
            .arg("--models-dir")
            .arg(&self.paths.models_dir)
            .args(args)
            .stdin(Stdio::null());

        // Capturamos salida para preservar códigos estructurados. Nunca se devuelve stderr
        // crudo; si no contiene nuestro contrato JSON se usa un error genérico seguro.
        let output = command.output()?;
        if output.status.success() {
            return Ok(());
        }
        if let Some(error) = parse_model_cli_error(&output.stderr)
            .or_else(|| parse_model_cli_error(&output.stdout))
        {
            return Err(error);
        }
        Err(ModelError::InstallFailed)
    }
}

#[derive(Debug, Error)]
pub enum ModelError {
    #[error("El runtime del motor no está instalado.")]
    EngineMissing,
    #[error("{message}")]
    Structured { code: String, message: String },
    #[error("La operación sobre modelos no terminó correctamente.")]
    InstallFailed,
    #[error("Error de sistema: {0}")]
    Io(#[from] std::io::Error),
}

impl ModelError {
    pub fn public_code(&self) -> &str {
        match self {
            Self::EngineMissing => "MODEL_RUNTIME_ERROR",
            Self::Structured { code, .. } => code,
            Self::InstallFailed => "MODEL_PROVIDER_ERROR",
            Self::Io(_) => "MODEL_RUNTIME_ERROR",
        }
    }

    pub fn public_message(&self) -> &str {
        match self {
            Self::EngineMissing => "El motor local no está instalado correctamente.",
            Self::Structured { message, .. } => message,
            Self::InstallFailed => FALLBACK_MODEL_MESSAGE,
            Self::Io(_) => "No se pudo ejecutar el motor local.",
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn embedded_catalog_contains_two_profiles() {
        let parsed: Catalog = serde_json::from_str(MODEL_CATALOG).unwrap();
        assert!(parsed.packs.iter().any(|pack| pack.id == "lite-nllb"));
        assert!(parsed.packs.iter().any(|pack| pack.id == "business-qwen"));
    }

    #[test]
    fn structured_engine_error_preserves_public_code() {
        let error = parse_model_cli_error(
            r#"{"ok":false,"code":"MODEL_NO_NETWORK","message":"No hay conexión a Internet."}"#
                .as_bytes(),
        )
        .expect("structured error");
        assert_eq!(error.public_code(), "MODEL_NO_NETWORK");
        assert_eq!(error.public_message(), "No hay conexión a Internet.");
    }

    #[test]
    fn arbitrary_stderr_never_becomes_public_message() {
        assert!(parse_model_cli_error(b"C:\\Users\\Alice\\secret token=abc crashed").is_none());
    }
}
