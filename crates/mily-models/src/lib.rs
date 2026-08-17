//! Inventario y operaciones administrativas de packs de IA.

use mily_config::AppPaths;
use mily_core::{ComponentState, ModelPackInfo};
use mily_engine::LaunchSpec;
use serde::Deserialize;
use std::fs;
use std::process::Stdio;
use thiserror::Error;

const MODEL_CATALOG: &str = include_str!("../../../resources/model-packs.json");

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
        // Los argumentos de rutas pertenecen al parser `models` y por eso deben
        // aparecer antes del subcomando `install`/`rollback`/`remove`.
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
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        let status = command.status()?;
        if status.success() {
            Ok(())
        } else {
            Err(ModelError::InstallFailed)
        }
    }
}

#[derive(Debug, Error)]
pub enum ModelError {
    #[error("El runtime del motor no está instalado.")]
    EngineMissing,
    #[error("La operación sobre modelos no terminó correctamente.")]
    InstallFailed,
    #[error("Error de sistema: {0}")]
    Io(#[from] std::io::Error),
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
}
