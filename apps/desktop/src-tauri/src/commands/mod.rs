//! Adaptadores IPC. Nunca retornan backtraces, SQL ni detalles sensibles.

mod hardware;
pub use hardware::*;

use crate::bootstrap::AppState;
use crate::repair;
use mily_cache::CacheStatus;
use mily_config::AppConfig;
use mily_core::{
    AppStatus, ComponentState, EngineRuntimeStatus, ModelPackInfo, PublicError, SessionSummary,
};
use mily_system::SystemSnapshot;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;
use tauri::State;

fn public_error(code: &str, message: &str) -> PublicError {
    PublicError::new(code, message)
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RuntimeLocations {
    pub models: String,
    pub sessions: String,
    pub extension: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct OnboardingStatus {
    pub runtime_ready: bool,
    pub bridge_ready: bool,
    pub extension_detected: bool,
    pub model_state: ComponentState,
    pub downloaded_bytes: u64,
    pub total_bytes: Option<u64>,
    pub model_phase: String,
    pub model_message: Option<String>,
    pub bootstrap_state: String,
    pub error_code: Option<String>,
    pub error_message: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct BootstrapStatusFile {
    state: String,
    #[serde(default)]
    code: String,
    #[serde(default)]
    message: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ModelOperationStatusFile {
    #[serde(default)]
    phase: String,
    #[serde(default)]
    message: String,
}

fn directory_size(path: &Path) -> u64 {
    let Ok(entries) = fs::read_dir(path) else {
        return 0;
    };
    entries
        .filter_map(Result::ok)
        .map(|entry| {
            let path = entry.path();
            match entry.metadata() {
                Ok(metadata) if metadata.is_file() => metadata.len(),
                Ok(metadata) if metadata.is_dir() => directory_size(&path),
                _ => 0,
            }
        })
        .sum()
}

fn bootstrap_status(state: &AppState) -> (String, Option<String>, Option<String>) {
    let path = state.paths.data_dir.join("bootstrap").join("status.json");
    let parsed = fs::read_to_string(path)
        .ok()
        .and_then(|text| serde_json::from_str::<BootstrapStatusFile>(&text).ok());
    match parsed {
        Some(status) if status.state == "failed" => (
            status.state,
            (!status.code.is_empty()).then_some(status.code),
            (!status.message.is_empty()).then_some(status.message),
        ),
        Some(status) => (status.state, None, None),
        None => ("unknown".into(), None, None),
    }
}

fn model_operation_status(state: &AppState) -> (String, Option<String>) {
    let path = state.paths.models_dir.join("operation.json");
    let parsed = fs::read_to_string(path)
        .ok()
        .and_then(|text| serde_json::from_str::<ModelOperationStatusFile>(&text).ok());
    match parsed {
        Some(status) => (
            if status.phase.is_empty() {
                "idle".into()
            } else {
                status.phase
            },
            (!status.message.is_empty()).then_some(status.message),
        ),
        None => ("idle".into(), None),
    }
}

#[tauri::command]
pub fn get_app_status(app: tauri::AppHandle, state: State<'_, AppState>) -> AppStatus {
    let config = state.config.load_or_default().unwrap_or_default();
    let installed = state.models.installed();
    let active_model_pack = installed
        .iter()
        .find(|pack| pack.active)
        .map(|pack| format!("{}@{}", pack.id, pack.version));
    AppStatus {
        version: app.package_info().version.to_string(),
        engine: state.engine.status(config.engine_port).state,
        models: state.models.status(),
        installed_models: state.models.installed_count(),
        extension_connected: state.engine.extension_connected(),
        active_model_pack,
    }
}

#[tauri::command]
pub fn get_onboarding_status(state: State<'_, AppState>) -> OnboardingStatus {
    let (bootstrap_state, error_code, error_message) = bootstrap_status(&state);
    let (model_phase, model_message) = model_operation_status(&state);
    let bridge_name = if cfg!(windows) {
        "milyvoice-bridge.exe"
    } else {
        "milyvoice-bridge"
    };
    OnboardingStatus {
        runtime_ready: state.engine.is_installed(),
        bridge_ready: state
            .paths
            .data_dir
            .join("bridge")
            .join(bridge_name)
            .is_file(),
        extension_detected: state.engine.extension_connected(),
        model_state: state.models.status(),
        downloaded_bytes: directory_size(&state.paths.models_dir.join(".staging")),
        total_bytes: None,
        model_phase,
        model_message,
        bootstrap_state,
        error_code,
        error_message,
    }
}

#[tauri::command]
pub async fn repair_installation(state: State<'_, AppState>) -> Result<(), PublicError> {
    let logger = state.logger.clone();
    let repair_result = tauri::async_runtime::spawn_blocking(repair::repair_current_installation)
        .await
        .map_err(|_| {
            public_error(
                "REPAIR_TASK",
                "La reparación local terminó inesperadamente.",
            )
        })?;

    if let Err(error) = repair_result {
        let _ = logger.write("warn", &format!("Reparación local falló: {error}"));
        let (_, bootstrap_code, bootstrap_message) = bootstrap_status(&state);
        let code = bootstrap_code.as_deref().unwrap_or("REPAIR_FAILED");
        let message = bootstrap_message.as_deref().unwrap_or(
            "No se pudo reparar la instalación. Reinstala el mismo paquete si el problema continúa.",
        );
        return Err(public_error(code, message));
    }

    let _ = logger.write("info", "Instalación local reparada correctamente.");
    Ok(())
}

#[tauri::command]
pub fn get_system_info(state: State<'_, AppState>) -> SystemSnapshot {
    state.system.snapshot()
}

#[tauri::command]
pub fn get_config(state: State<'_, AppState>) -> Result<AppConfig, PublicError> {
    state.config.load_or_default().map_err(|_| {
        let _ = state
            .logger
            .write("error", "No se pudo leer la configuración local.");
        public_error("CONFIG_READ", "No se pudo leer la configuración.")
    })
}

#[tauri::command]
pub fn save_config(
    state: State<'_, AppState>,
    config: AppConfig,
) -> Result<AppConfig, PublicError> {
    let normalized = config.normalized();
    state.config.save(&normalized).map_err(|_| {
        let _ = state
            .logger
            .write("error", "No se pudo guardar la configuración local.");
        public_error("CONFIG_WRITE", "No se pudo guardar la configuración.")
    })?;
    state.config.save_engine_config(&normalized).map_err(|_| {
        let _ = state.logger.write(
            "error",
            "No se pudo sincronizar la configuración del motor.",
        );
        public_error(
            "ENGINE_CONFIG_WRITE",
            "No se pudo preparar la configuración del motor.",
        )
    })?;
    state
        .cache
        .set_max_bytes(normalized.cache_limit_mb.saturating_mul(1024 * 1024));
    let _ = state
        .database
        .set_setting("config_schema", &normalized.schema_version.to_string());
    Ok(normalized)
}

#[tauri::command]
pub fn get_cache_status(state: State<'_, AppState>) -> Result<CacheStatus, PublicError> {
    state.cache.status().map_err(|_| {
        let _ = state
            .logger
            .write("warn", "No se pudo consultar el estado de caché.");
        public_error("CACHE_STATUS", "No se pudo consultar la caché.")
    })
}

#[tauri::command]
pub fn clear_cache(state: State<'_, AppState>) -> Result<CacheStatus, PublicError> {
    state.cache.clear().map_err(|_| {
        let _ = state.logger.write("error", "No se pudo limpiar la caché.");
        public_error("CACHE_CLEAR", "No se pudo limpiar la caché.")
    })?;
    let _ = state
        .logger
        .write("info", "Caché local limpiada por el usuario.");
    state.cache.status().map_err(|_| {
        public_error(
            "CACHE_STATUS",
            "La caché se limpió, pero no se pudo leer su estado.",
        )
    })
}

#[tauri::command]
pub fn get_engine_status(state: State<'_, AppState>) -> EngineRuntimeStatus {
    let config = state.config.load_or_default().unwrap_or_default();
    state.engine.status(config.engine_port)
}

#[tauri::command]
pub fn start_engine(state: State<'_, AppState>) -> Result<EngineRuntimeStatus, PublicError> {
    let config = state.config.load_or_default().unwrap_or_default();
    state.engine.start(config.engine_port).map_err(|error| {
        let _ = state
            .logger
            .write("error", &format!("No se pudo iniciar motor: {}", error));
        public_error(
            "ENGINE_START",
            "No se pudo iniciar el motor local. Revisa que el runtime esté instalado.",
        )
    })
}

#[tauri::command]
pub fn stop_engine(state: State<'_, AppState>) -> Result<EngineRuntimeStatus, PublicError> {
    let config = state.config.load_or_default().unwrap_or_default();
    state.engine.stop(config.engine_port).map_err(|_| {
        let _ = state
            .logger
            .write("warn", "No se pudo detener el motor local.");
        public_error("ENGINE_STOP", "No se pudo detener el motor local.")
    })
}

#[tauri::command]
pub fn get_model_catalog(state: State<'_, AppState>) -> Vec<ModelPackInfo> {
    state.models.catalog()
}

#[tauri::command]
pub async fn install_model(
    state: State<'_, AppState>,
    pack_id: String,
) -> Result<ModelPackInfo, PublicError> {
    let models = state.models.clone();
    let database = state.database.clone();
    let logger = state.logger.clone();
    let pack_id_for_task = pack_id.clone();
    tauri::async_runtime::spawn_blocking(move || models.install(&pack_id_for_task))
        .await
        .map_err(|_| {
            public_error(
                "MODEL_RUNTIME_ERROR",
                "La tarea de instalación terminó inesperadamente.",
            )
        })?
        .inspect(|_| {
            let _ = database.record_model_event(&pack_id, "install");
            let _ = logger.write("info", "Pack de modelos instalado correctamente.");
        })
        .map_err(|error| {
            let code = error.public_code();
            let message = error.public_message();
            let _ = logger.write("warn", &format!("Instalación de modelo falló: {code}"));
            public_error(code, message)
        })
}

#[tauri::command]
pub async fn verify_model(
    state: State<'_, AppState>,
    pack_id: String,
    version: String,
) -> Result<bool, PublicError> {
    let models = state.models.clone();
    tauri::async_runtime::spawn_blocking(move || models.verify(&pack_id, &version))
        .await
        .map_err(|_| {
            public_error(
                "MODEL_RUNTIME_ERROR",
                "La verificación terminó inesperadamente.",
            )
        })?
        .map_err(|error| public_error(error.public_code(), error.public_message()))
}

#[tauri::command]
pub async fn remove_model(
    state: State<'_, AppState>,
    pack_id: String,
    version: String,
) -> Result<(), PublicError> {
    let models = state.models.clone();
    tauri::async_runtime::spawn_blocking(move || models.remove(&pack_id, &version))
        .await
        .map_err(|_| {
            public_error(
                "MODEL_RUNTIME_ERROR",
                "La eliminación terminó inesperadamente.",
            )
        })?
        .map_err(|error| public_error(error.public_code(), error.public_message()))
}

#[tauri::command]
pub async fn rollback_model(state: State<'_, AppState>) -> Result<ModelPackInfo, PublicError> {
    let models = state.models.clone();
    tauri::async_runtime::spawn_blocking(move || models.rollback())
        .await
        .map_err(|_| {
            public_error(
                "MODEL_RUNTIME_ERROR",
                "La tarea de rollback terminó inesperadamente.",
            )
        })?
        .map_err(|error| public_error(error.public_code(), error.public_message()))
}

#[tauri::command]
pub fn list_sessions(state: State<'_, AppState>) -> Vec<SessionSummary> {
    state.sessions.list()
}

#[tauri::command]
pub fn get_session_export(
    state: State<'_, AppState>,
    session_id: String,
    format: String,
) -> Result<String, PublicError> {
    state
        .sessions
        .export_text(&session_id, &format)
        .map_err(|_| {
            public_error(
                "SESSION_EXPORT",
                "No se pudo leer la exportación solicitada.",
            )
        })
}

#[tauri::command]
pub fn delete_session(state: State<'_, AppState>, session_id: String) -> Result<(), PublicError> {
    state
        .sessions
        .delete(&session_id)
        .map_err(|_| public_error("SESSION_DELETE", "No se pudo eliminar la sesión."))
}

#[tauri::command]
pub fn get_runtime_locations(state: State<'_, AppState>) -> RuntimeLocations {
    RuntimeLocations {
        models: state.paths.models_dir.to_string_lossy().into_owned(),
        sessions: state.paths.sessions_dir.to_string_lossy().into_owned(),
        extension: state.paths.extension_dir.to_string_lossy().into_owned(),
    }
}
