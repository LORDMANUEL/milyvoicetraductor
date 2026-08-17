//! Rutas estándar y configuración persistente de MilyVoiceTraductor.

use directories::ProjectDirs;
use serde::{Deserialize, Serialize};
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use thiserror::Error;

const CONFIG_SCHEMA_VERSION: u32 = 1;

/// Rutas de datos de la aplicación, resueltas usando convenciones del SO.
#[derive(Debug, Clone)]
pub struct AppPaths {
    pub data_dir: PathBuf,
    pub config_dir: PathBuf,
    pub cache_dir: PathBuf,
    pub log_dir: PathBuf,
}

impl AppPaths {
    /// Resuelve las carpetas de usuario sin codificar nombres de usuario.
    pub fn discover() -> Result<Self, ConfigError> {
        let project = ProjectDirs::from("com", "MilyVoice", "MilyVoiceTraductor")
            .ok_or(ConfigError::ProjectDirectoryUnavailable)?;
        Ok(Self {
            data_dir: project.data_dir().to_path_buf(),
            config_dir: project.config_dir().to_path_buf(),
            cache_dir: project.cache_dir().to_path_buf(),
            log_dir: project.data_dir().join("logs"),
        })
    }

    /// Crea únicamente los directorios requeridos por la aplicación.
    pub fn ensure_exists(&self) -> Result<(), ConfigError> {
        for path in [
            &self.data_dir,
            &self.config_dir,
            &self.cache_dir,
            &self.log_dir,
        ] {
            fs::create_dir_all(path)?;
        }
        Ok(())
    }
}

/// Preferencias persistentes y versionadas de Fase 1.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AppConfig {
    pub schema_version: u32,
    pub interface_language: String,
    pub source_language: String,
    pub target_language: String,
    pub theme: String,
    pub auto_start_engine: bool,
    pub cache_limit_mb: u64,
    pub log_level: String,
    pub microphone_consent: bool,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            schema_version: CONFIG_SCHEMA_VERSION,
            interface_language: "es".into(),
            source_language: "auto".into(),
            target_language: "es".into(),
            theme: "system".into(),
            auto_start_engine: false,
            cache_limit_mb: 256,
            log_level: "info".into(),
            microphone_consent: false,
        }
    }
}

impl AppConfig {
    /// Normaliza campos editables a un conjunto pequeño de valores válidos.
    pub fn normalized(mut self) -> Self {
        if !matches!(self.source_language.as_str(), "auto" | "en" | "zh") {
            self.source_language = "auto".into();
        }
        if self.target_language != "es" {
            self.target_language = "es".into();
        }
        if !matches!(self.theme.as_str(), "system" | "light" | "dark") {
            self.theme = "system".into();
        }
        if !matches!(self.log_level.as_str(), "error" | "warn" | "info" | "debug") {
            self.log_level = "info".into();
        }
        self.cache_limit_mb = self.cache_limit_mb.clamp(64, 4096);
        self.schema_version = CONFIG_SCHEMA_VERSION;
        self
    }
}

/// Servicio OOP pequeño: encapsula ruta y política de lectura/escritura.
#[derive(Debug, Clone)]
pub struct ConfigService {
    path: PathBuf,
}

impl ConfigService {
    pub fn new(path: impl Into<PathBuf>) -> Self {
        Self { path: path.into() }
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    /// Carga la configuración o usa defaults seguros cuando aún no existe.
    pub fn load_or_default(&self) -> Result<AppConfig, ConfigError> {
        if !self.path.exists() {
            return Ok(AppConfig::default());
        }
        let data = fs::read_to_string(&self.path)?;
        let config: AppConfig = serde_json::from_str(&data)?;
        Ok(config.normalized())
    }

    /// Guarda de forma atómica: escribe a temporal y luego renombra.
    pub fn save(&self, config: &AppConfig) -> Result<(), ConfigError> {
        let config = config.clone().normalized();
        if let Some(parent) = self.path.parent() {
            fs::create_dir_all(parent)?;
        }
        let temp_path = self.path.with_extension("json.tmp");
        let bytes = serde_json::to_vec_pretty(&config)?;
        let mut file = fs::File::create(&temp_path)?;
        file.write_all(&bytes)?;
        file.sync_all()?;
        fs::rename(temp_path, &self.path)?;
        Ok(())
    }
}

#[derive(Debug, Error)]
pub enum ConfigError {
    #[error("No se pudo resolver el directorio de la aplicación.")]
    ProjectDirectoryUnavailable,
    #[error("Error de archivo de configuración: {0}")]
    Io(#[from] std::io::Error),
    #[error("Configuración JSON inválida: {0}")]
    Json(#[from] serde_json::Error),
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn missing_config_returns_safe_defaults() {
        let dir = tempdir().unwrap();
        let service = ConfigService::new(dir.path().join("config.json"));
        let config = service.load_or_default().unwrap();
        assert_eq!(config.source_language, "auto");
        assert_eq!(config.target_language, "es");
        assert_eq!(config.cache_limit_mb, 256);
    }

    #[test]
    fn config_roundtrip_persists_normalized_values() {
        let dir = tempdir().unwrap();
        let service = ConfigService::new(dir.path().join("config.json"));
        let mut config = AppConfig::default();
        config.source_language = "zh".into();
        config.cache_limit_mb = 512;
        service.save(&config).unwrap();
        assert_eq!(service.load_or_default().unwrap(), config);
    }

    #[test]
    fn invalid_values_are_replaced_by_safe_defaults() {
        let mut config = AppConfig::default();
        config.theme = "neon".into();
        config.source_language = "xx".into();
        config.cache_limit_mb = 1;
        let normalized = config.normalized();
        assert_eq!(normalized.theme, "system");
        assert_eq!(normalized.source_language, "auto");
        assert_eq!(normalized.cache_limit_mb, 64);
    }
}
