//! Rutas estándar y configuración persistente de MilyVoiceTraductor.

#[cfg(not(windows))]
use directories::ProjectDirs;
use serde::{Deserialize, Serialize};
use std::fs;
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use thiserror::Error;

const CONFIG_SCHEMA_VERSION: u32 = 2;

#[derive(Debug, Clone)]
pub struct AppPaths {
    pub data_dir: PathBuf,
    pub config_dir: PathBuf,
    pub cache_dir: PathBuf,
    pub log_dir: PathBuf,
    pub models_dir: PathBuf,
    pub sessions_dir: PathBuf,
    pub engine_dir: PathBuf,
    pub bin_dir: PathBuf,
    pub extension_dir: PathBuf,
}

impl AppPaths {
    pub fn discover() -> Result<Self, ConfigError> {
        #[cfg(windows)]
        let (data_dir, config_dir, cache_dir) = {
            let root = std::env::var_os("LOCALAPPDATA")
                .map(PathBuf::from)
                .ok_or(ConfigError::ProjectDirectoryUnavailable)?
                .join("MilyVoiceTraductor");
            (root.clone(), root.join("config"), root.join("cache"))
        };

        #[cfg(not(windows))]
        let (data_dir, config_dir, cache_dir) = {
            let project = ProjectDirs::from("com", "MilyVoice", "MilyVoiceTraductor")
                .ok_or(ConfigError::ProjectDirectoryUnavailable)?;
            (
                project.data_dir().to_path_buf(),
                project.config_dir().to_path_buf(),
                project.cache_dir().to_path_buf(),
            )
        };

        Ok(Self {
            log_dir: data_dir.join("logs"),
            models_dir: data_dir.join("models"),
            sessions_dir: data_dir.join("sessions"),
            engine_dir: data_dir.join("engine"),
            bin_dir: data_dir.join("bin"),
            extension_dir: data_dir.join("extension"),
            data_dir,
            config_dir,
            cache_dir,
        })
    }

    pub fn ensure_exists(&self) -> Result<(), ConfigError> {
        for path in [
            &self.data_dir,
            &self.config_dir,
            &self.cache_dir,
            &self.log_dir,
            &self.models_dir,
            &self.sessions_dir,
            &self.engine_dir,
            &self.bin_dir,
            &self.extension_dir,
        ] {
            fs::create_dir_all(path)?;
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", default)]
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
    pub persist_transcripts: bool,
    pub compute_profile: String,
    pub engine_port: u16,
    pub active_model_pack: String,
    pub show_original_subtitle: bool,
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
            persist_transcripts: false,
            compute_profile: "auto".into(),
            engine_port: 8765,
            active_model_pack: "realtime-m2m100".into(),
            show_original_subtitle: true,
        }
    }
}

impl AppConfig {
    pub fn normalized(mut self) -> Self {
        if !matches!(self.source_language.as_str(), "auto" | "en" | "zh") {
            self.source_language = "auto".into();
        }
        self.target_language = "es".into();
        if !matches!(self.theme.as_str(), "system" | "light" | "dark") {
            self.theme = "system".into();
        }
        if !matches!(self.log_level.as_str(), "error" | "warn" | "info" | "debug") {
            self.log_level = "info".into();
        }
        if !matches!(self.compute_profile.as_str(), "auto" | "cpu" | "gpu") {
            self.compute_profile = "auto".into();
        }
        if !matches!(
            self.active_model_pack.as_str(),
            "realtime-m2m100" | "lite-nllb" | "business-qwen"
        ) {
            self.active_model_pack = "realtime-m2m100".into();
        }
        self.cache_limit_mb = self.cache_limit_mb.clamp(64, 4096);
        self.engine_port = self.engine_port.clamp(1024, 65_535);
        self.schema_version = CONFIG_SCHEMA_VERSION;
        self
    }
}

#[cfg(windows)]
fn replacement_backup_path(destination: &Path) -> PathBuf {
    let stem = format!("{}.replace-backup", destination.display());
    let primary = PathBuf::from(&stem);
    if !primary.exists() {
        return primary;
    }
    for index in 1_u32.. {
        let candidate = PathBuf::from(format!("{stem}.{index}"));
        if !candidate.exists() {
            return candidate;
        }
    }
    unreachable!()
}

fn replace_file(source: &Path, destination: &Path) -> io::Result<()> {
    #[cfg(windows)]
    {
        if !destination.exists() {
            return fs::rename(source, destination);
        }

        let backup = replacement_backup_path(destination);
        fs::rename(destination, &backup)?;
        match fs::rename(source, destination) {
            Ok(()) => {
                let _ = fs::remove_file(backup);
                Ok(())
            }
            Err(error) => {
                if let Err(restore_error) = fs::rename(&backup, destination) {
                    return Err(io::Error::new(
                        restore_error.kind(),
                        format!(
                            "falló el reemplazo ({error}) y también la restauración del archivo previo ({restore_error}); respaldo conservado en {}",
                            backup.display()
                        ),
                    ));
                }
                Err(error)
            }
        }
    }

    #[cfg(not(windows))]
    {
        fs::rename(source, destination)
    }
}

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

    pub fn load_or_default(&self) -> Result<AppConfig, ConfigError> {
        if !self.path.exists() {
            return Ok(AppConfig::default());
        }
        let data = fs::read_to_string(&self.path)?;
        match serde_json::from_str::<AppConfig>(&data) {
            Ok(config) => Ok(config.normalized()),
            Err(_) => {
                let quarantine = self.path.with_extension("json.invalid");
                if quarantine.exists() {
                    fs::remove_file(&quarantine)?;
                }
                fs::rename(&self.path, quarantine)?;
                Ok(AppConfig::default())
            }
        }
    }

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
        replace_file(&temp_path, &self.path)?;
        Ok(())
    }

    pub fn save_engine_config(&self, config: &AppConfig) -> Result<(), ConfigError> {
        let parent = self
            .path
            .parent()
            .ok_or(ConfigError::ProjectDirectoryUnavailable)?;
        fs::create_dir_all(parent)?;
        let value = serde_json::json!({
            "sourceLanguage": config.source_language,
            "targetLanguage": "es",
            "computeProfile": config.compute_profile,
            "persistTranscripts": config.persist_transcripts,
            "activeModelPack": config.active_model_pack,
            "logLevel": config.log_level,
        });
        let path = parent.join("engine.json");
        let temp = parent.join("engine.json.tmp");
        fs::write(&temp, serde_json::to_vec_pretty(&value)?)?;
        replace_file(&temp, &path)?;
        Ok(())
    }
}

#[derive(Debug, Error)]
pub enum ConfigError {
    #[error("No se pudo resolver el directorio de la aplicación.")]
    ProjectDirectoryUnavailable,
    #[error("Error de archivo de configuración: {0}")]
    Io(#[from] io::Error),
    #[error("Configuración JSON inválida: {0}")]
    Json(#[from] serde_json::Error),
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn old_or_missing_fields_receive_safe_defaults() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("config.json");
        fs::write(&path, r#"{"schemaVersion":1,"sourceLanguage":"zh"}"#).unwrap();
        let config = ConfigService::new(path).load_or_default().unwrap();
        assert_eq!(config.source_language, "zh");
        assert_eq!(config.compute_profile, "auto");
        assert_eq!(config.active_model_pack, "realtime-m2m100");
        assert!(!config.persist_transcripts);
        assert_eq!(config.schema_version, 2);
    }

    #[test]
    fn malformed_prior_config_is_quarantined_and_defaults_are_loaded() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("config.json");
        fs::write(&path, b"{ definitely-not-valid-json").unwrap();
        let service = ConfigService::new(&path);

        let config = service
            .load_or_default()
            .expect("una configuración corrupta anterior no debe impedir el arranque");

        assert_eq!(config, AppConfig::default());
        assert!(!path.exists());
        assert!(dir.path().join("config.json.invalid").exists());
    }

    #[test]
    fn invalid_values_are_normalized() {
        let config = AppConfig {
            theme: "neon".into(),
            source_language: "xx".into(),
            compute_profile: "quantum".into(),
            engine_port: 1,
            active_model_pack: "unknown-pack".into(),
            ..AppConfig::default()
        }
        .normalized();
        assert_eq!(config.theme, "system");
        assert_eq!(config.source_language, "auto");
        assert_eq!(config.compute_profile, "auto");
        assert_eq!(config.engine_port, 1024);
        assert_eq!(config.active_model_pack, "realtime-m2m100");
    }

    #[cfg(windows)]
    #[test]
    fn save_replaces_an_existing_config_on_windows() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("config.json");
        fs::write(&path, r#"{"schemaVersion":2,"sourceLanguage":"zh"}"#).unwrap();
        let service = ConfigService::new(&path);
        let desired = AppConfig {
            source_language: "en".into(),
            ..AppConfig::default()
        };
        service
            .save(&desired)
            .expect("guardar debe reemplazar config existente");
        let loaded = service.load_or_default().unwrap();
        assert_eq!(loaded.source_language, "en");
    }

    #[cfg(windows)]
    #[test]
    fn engine_config_replaces_an_existing_file_on_windows() {
        let dir = tempdir().unwrap();
        let config_path = dir.path().join("config.json");
        let engine_path = dir.path().join("engine.json");
        fs::write(&engine_path, br#"{"sourceLanguage":"zh"}"#).unwrap();
        let service = ConfigService::new(config_path);
        service
            .save_engine_config(&AppConfig::default())
            .expect("guardar engine.json debe reemplazar el archivo existente");
        let payload = fs::read_to_string(engine_path).unwrap();
        assert!(payload.contains(r#""sourceLanguage": "auto""#));
    }

    #[cfg(windows)]
    #[test]
    fn failed_replacement_never_deletes_the_existing_destination() {
        let dir = tempdir().unwrap();
        let missing_source = dir.path().join("missing.tmp");
        let destination = dir.path().join("config.json");
        fs::write(&destination, b"important prior config").unwrap();

        let error = replace_file(&missing_source, &destination)
            .expect_err("reemplazar desde una fuente inexistente debe fallar");

        assert_eq!(error.kind(), io::ErrorKind::NotFound);
        assert!(destination.is_file());
        assert_eq!(fs::read(destination).unwrap(), b"important prior config");
    }
}
