//! Inventario y operaciones administrativas de packs de IA.
//!
//! Este crate separa descarga, activación, importación y selección automática.
//! Ningún stderr crudo ni ruta privada llega a la UI.

use mily_config::AppPaths;
use mily_core::{ComponentState, ModelPackInfo};
use mily_engine::LaunchSpec;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::Path;
use std::process::Stdio;
use thiserror::Error;

const MODEL_CATALOG: &str = include_str!("../../../resources/model-packs.json");
const FALLBACK_MODEL_MESSAGE: &str = "La operación sobre modelos no terminó correctamente.";
const PROCESS_LIMIT_MB: u64 = 2048;
const VRAM_LIMIT_MB: u64 = 384;
const DESKTOP_RESERVE_MB: u64 = 256;
const BRIDGE_RESERVE_MB: u64 = 64;
const PRODUCT_RESERVE_MB: u64 = DESKTOP_RESERVE_MB + BRIDGE_RESERVE_MB;

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
struct Catalog {
    packs: Vec<CatalogPack>,
}

#[derive(Debug, Clone, Default, Deserialize)]
#[serde(rename_all = "camelCase", default)]
struct CatalogPack {
    id: String,
    version: String,
    title: String,
    recommended_ram_gb: u64,
    commercial_use: bool,
    license_note: String,
    tier: String,
    routes: Vec<String>,
    ram_mb: u64,
    vram_mb: u64,
    shared_gpu_mb: u64,
    engine: String,
    supported_backends: Vec<String>,
    external_allowed: bool,
}

impl CatalogPack {
    fn estimated_total_product_mb(&self) -> u64 {
        self.ram_mb
            .saturating_add(self.shared_gpu_mb)
            .saturating_add(PRODUCT_RESERVE_MB)
    }

    fn resource_allowed(&self) -> bool {
        self.estimated_total_product_mb() <= PROCESS_LIMIT_MB && self.vram_mb <= VRAM_LIMIT_MB
    }

    fn resource_reason(&self) -> String {
        if self.estimated_total_product_mb() > PROCESS_LIMIT_MB {
            "PROCESS_MEMORY_LIMIT".into()
        } else if self.vram_mb > VRAM_LIMIT_MB {
            "VRAM_LIMIT".into()
        } else {
            "OK".into()
        }
    }

    fn into_info(self, installed: bool, active: bool) -> ModelPackInfo {
        let resource_allowed = self.resource_allowed();
        let resource_reason = self.resource_reason();
        let estimated_total_product_mb = self.estimated_total_product_mb();
        ModelPackInfo {
            id: self.id,
            version: self.version,
            title: self.title,
            installed,
            active,
            recommended_ram_gb: self.recommended_ram_gb,
            commercial_use: self.commercial_use,
            license_note: self.license_note,
            tier: self.tier,
            routes: self.routes,
            ram_mb: self.ram_mb,
            vram_mb: self.vram_mb,
            shared_gpu_mb: self.shared_gpu_mb,
            product_reserve_mb: PRODUCT_RESERVE_MB,
            estimated_total_product_mb,
            engine: self.engine,
            supported_backends: self.supported_backends,
            resource_allowed,
            resource_reason,
            external_allowed: self.external_allowed,
        }
    }

    fn from_external_manifest(path: &Path, expected_id: &str, expected_version: &str) -> Option<Self> {
        let text = fs::read_to_string(path).ok()?;
        let mut pack = serde_json::from_str::<Self>(&text).ok()?;
        if pack.id != expected_id || pack.version != expected_version {
            return None;
        }
        if pack.title.trim().is_empty()
            || pack.tier.trim().is_empty()
            || pack.routes.is_empty()
            || pack.engine.trim().is_empty()
            || pack.ram_mb == 0
            || !pack.external_allowed
        {
            return None;
        }
        if pack.supported_backends.is_empty() {
            pack.supported_backends.push("cpu".into());
        }
        Some(pack)
    }
}

#[derive(Debug, Clone, Deserialize)]
struct ModelCliErrorPayload {
    ok: bool,
    code: String,
    message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AutoSelectionResult {
    pub selected: String,
    pub backend: String,
    pub score: f64,
    #[serde(default)]
    pub rejected: serde_json::Value,
    #[serde(default)]
    pub benchmarks: serde_json::Value,
}

fn parse_model_cli_error(bytes: &[u8]) -> Option<ModelError> {
    let text = std::str::from_utf8(bytes).ok()?.trim();
    if text.is_empty() {
        return None;
    }
    for line in text.lines().rev() {
        let Ok(payload) = serde_json::from_str::<ModelCliErrorPayload>(line.trim()) else {
            continue;
        };
        if payload.ok || !valid_public_model_code(&payload.code) {
            continue;
        }
        return Some(ModelError::Structured {
            code: payload.code,
            message: sanitize_public_message(&payload.message),
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
            | "MODEL_CONVERSION_ERROR"
            | "MODEL_LICENSE_BLOCKED"
            | "MODEL_STATE_RESTORE"
            | "MODEL_EXTERNAL_UNSAFE"
            | "MODEL_EXTERNAL_MANIFEST"
            | "MODEL_EXTERNAL_INVALID"
            | "PROCESS_MEMORY_LIMIT"
            | "VRAM_LIMIT"
            | "NO_COMPATIBLE_ENGINE"
    )
}

fn sanitize_public_message(message: &str) -> String {
    let trimmed = message.trim();
    if trimmed.is_empty() || trimmed.len() > 300 {
        return FALLBACK_MODEL_MESSAGE.to_string();
    }
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

    fn definitions(&self) -> Vec<CatalogPack> {
        serde_json::from_str::<Catalog>(MODEL_CATALOG)
            .map(|catalog| catalog.packs)
            .unwrap_or_default()
    }

    fn active_ref(&self) -> Option<String> {
        fs::read_to_string(self.paths.models_dir.join("current.json"))
            .ok()
            .and_then(|text| serde_json::from_str::<serde_json::Value>(&text).ok())
            .and_then(|value| {
                value
                    .get("active")
                    .and_then(|item| item.as_str())
                    .map(str::to_owned)
            })
    }

    fn installed_entries(&self) -> Vec<(CatalogPack, bool)> {
        let active = self.active_ref();
        let definitions: HashMap<String, CatalogPack> = self
            .definitions()
            .into_iter()
            .map(|item| (item.id.clone(), item))
            .collect();
        let packs_root = self.paths.models_dir.join("packs");
        let Ok(pack_ids) = fs::read_dir(packs_root) else {
            return Vec::new();
        };
        let mut output = Vec::new();
        for pack_id_entry in pack_ids.flatten() {
            let Ok(kind) = pack_id_entry.file_type() else {
                continue;
            };
            if !kind.is_dir() {
                continue;
            }
            let pack_id = pack_id_entry.file_name().to_string_lossy().into_owned();
            let Ok(versions) = fs::read_dir(pack_id_entry.path()) else {
                continue;
            };
            for version_entry in versions.flatten() {
                let Ok(version_kind) = version_entry.file_type() else {
                    continue;
                };
                if !version_kind.is_dir() {
                    continue;
                }
                let version = version_entry.file_name().to_string_lossy().into_owned();
                if !version_entry.path().join("pack.json").is_file() {
                    continue;
                }
                let definition = definitions.get(&pack_id).cloned().or_else(|| {
                    CatalogPack::from_external_manifest(
                        &version_entry.path().join("manifest.json"),
                        &pack_id,
                        &version,
                    )
                });
                let Some(definition) = definition else {
                    continue;
                };
                let is_active = active.as_deref() == Some(&format!("{pack_id}@{version}"));
                output.push((definition, is_active));
            }
        }
        output.sort_by(|left, right| {
            (&left.0.id, &left.0.version).cmp(&(&right.0.id, &right.0.version))
        });
        output
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
        let installed = self.installed();
        let mut output: Vec<ModelPackInfo> = self
            .definitions()
            .into_iter()
            .map(|definition| {
                let local = installed
                    .iter()
                    .find(|item| item.id == definition.id && item.version == definition.version);
                let is_installed = local.is_some();
                let active = local.map(|item| item.active).unwrap_or(false);
                definition.into_info(is_installed, active)
            })
            .collect();
        for pack in installed {
            if !output
                .iter()
                .any(|item| item.id == pack.id && item.version == pack.version)
            {
                output.push(pack);
            }
        }
        output.sort_by(|left, right| (&left.id, &left.version).cmp(&(&right.id, &right.version)));
        output
    }

    pub fn installed(&self) -> Vec<ModelPackInfo> {
        self.installed_entries()
            .into_iter()
            .map(|(definition, active)| definition.into_info(true, active))
            .collect()
    }

    pub fn install(&self, pack_id: &str) -> Result<ModelPackInfo, ModelError> {
        self.run_engine_cli(&["install".into(), pack_id.into(), "--download-only".into()])?;
        self.catalog()
            .into_iter()
            .find(|pack| pack.id == pack_id && pack.installed)
            .ok_or(ModelError::InstallFailed)
    }

    pub fn activate(&self, pack_id: &str, version: &str) -> Result<ModelPackInfo, ModelError> {
        self.run_engine_cli(&["activate".into(), pack_id.into(), version.into()])?;
        self.catalog()
            .into_iter()
            .find(|pack| pack.id == pack_id && pack.version == version && pack.active)
            .ok_or(ModelError::InstallFailed)
    }

    pub fn import_pack(&self, path: &Path) -> Result<ModelPackInfo, ModelError> {
        self.run_engine_cli(&["import".into(), path.to_string_lossy().into_owned()])?;
        self.installed()
            .into_iter()
            .find(|pack| pack.active)
            .ok_or(ModelError::InstallFailed)
    }

    pub fn auto_select(
        &self,
        route: &str,
        force_benchmark: bool,
    ) -> Result<AutoSelectionResult, ModelError> {
        let mut args = vec!["auto-select".into(), "--route".into(), route.into()];
        if force_benchmark {
            args.push("--force-benchmark".into());
        }
        let bytes = self.run_engine_cli(&args)?;
        serde_json::from_slice(&bytes).map_err(|_| ModelError::InstallFailed)
    }

    pub fn rollback(&self) -> Result<ModelPackInfo, ModelError> {
        self.run_engine_cli(&["rollback".into()])?;
        self.installed()
            .into_iter()
            .find(|pack| pack.active)
            .ok_or(ModelError::InstallFailed)
    }

    pub fn verify(&self, pack_id: &str, version: &str) -> Result<bool, ModelError> {
        match self.run_engine_cli(&["verify".into(), pack_id.into(), version.into()]) {
            Ok(_) => Ok(true),
            Err(ModelError::InstallFailed) => Ok(false),
            Err(error) => Err(error),
        }
    }

    pub fn remove(&self, pack_id: &str, version: &str) -> Result<(), ModelError> {
        self.run_engine_cli(&["remove".into(), pack_id.into(), version.into()])?;
        Ok(())
    }

    fn run_engine_cli(&self, args: &[String]) -> Result<Vec<u8>, ModelError> {
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

        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            command.creation_flags(CREATE_NO_WINDOW);
        }

        let output = command.output()?;
        if output.status.success() {
            return Ok(output.stdout);
        }
        if let Some(error) =
            parse_model_cli_error(&output.stderr).or_else(|| parse_model_cli_error(&output.stdout))
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
    fn embedded_catalog_contains_lite_and_quality_profiles() {
        let parsed: Catalog = serde_json::from_str(MODEL_CATALOG).unwrap();
        let lite = parsed
            .packs
            .iter()
            .find(|pack| pack.id == "lite-en-es")
            .expect("lite profile");
        assert!(lite.resource_allowed());
        assert_eq!(lite.estimated_total_product_mb(), lite.ram_mb + PRODUCT_RESERVE_MB);
        let quality = parsed
            .packs
            .iter()
            .find(|pack| pack.id == "realtime-m2m100")
            .expect("quality profile");
        assert!(!quality.resource_allowed());
    }

    #[test]
    fn product_reserve_rejects_model_that_only_fits_in_isolation() {
        let pack = CatalogPack {
            ram_mb: 1800,
            ..CatalogPack::default()
        };
        assert_eq!(pack.estimated_total_product_mb(), 2120);
        assert!(!pack.resource_allowed());
        assert_eq!(pack.resource_reason(), "PROCESS_MEMORY_LIMIT");
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
    fn memory_limit_is_safe_for_ui() {
        let error = parse_model_cli_error(
            r#"{"ok":false,"code":"PROCESS_MEMORY_LIMIT","message":"El modelo no cabe."}"#
                .as_bytes(),
        )
        .expect("structured error");
        assert_eq!(error.public_code(), "PROCESS_MEMORY_LIMIT");
    }

    #[test]
    fn arbitrary_stderr_never_becomes_public_message() {
        assert!(parse_model_cli_error(b"C:\\Users\\Alice\\secret token=abc crashed").is_none());
    }
}
