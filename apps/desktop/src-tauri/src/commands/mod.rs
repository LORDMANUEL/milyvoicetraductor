//! Adaptadores IPC. Nunca retornan backtraces, SQL, tokens salvo cuando el
//! usuario solicita explícitamente el token de emparejamiento.

use crate::bootstrap::AppState;
use mily_cache::CacheStatus;
use mily_config::AppConfig;
use mily_core::{AppStatus, EngineRuntimeStatus, ModelPackInfo, PublicError, SessionSummary};
use mily_system::SystemSnapshot;
use serde::Serialize;
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

#[tauri::command]
pub fn get_app_status(state: State<'_, AppState>) -> AppStatus {
    let config = state.config.load_or_default().unwrap_or_default();
    let installed = state.models.installed();
    let active_model_pack = installed
        .iter()
        .find(|pack| pack.active)
        .map(|pack| format!("{}@{}", pack.id, pack.version));
    AppStatus {
        version: env!("CARGO_PKG_VERSION").to_string(),
        engine: state.engine.status(config.engine_port).state,
        models: state.models.status(),
        installed_models: state.models.installed_count(),
        extension_connected: state.engine.extension_connected(),
        active_model_pack,
    }
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
pub fn get_pairing_token(state: State<'_, AppState>) -> Result<String, PublicError> {
    state.engine.pairing_token().map_err(|_| {
        public_error(
            "PAIRING_TOKEN",
            "No se pudo preparar el token local de emparejamiento.",
        )
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
                "MODEL_TASK",
                "La tarea de instalación terminó inesperadamente.",
            )
        })?
        .map(|pack| {
            let _ = database.record_model_event(&pack_id, "install");
            let _ = logger.write("info", "Pack de modelos instalado correctamente.");
            pack
        })
        .map_err(|_| {
            public_error(
                "MODEL_INSTALL",
                "No se pudo instalar el pack. Revisa conexión, espacio y licencia.",
            )
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
        .map_err(|_| public_error("MODEL_TASK", "La verificación terminó inesperadamente."))?
        .map_err(|_| public_error("MODEL_VERIFY", "No se pudo verificar el pack local."))
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
        .map_err(|_| public_error("MODEL_TASK", "La eliminación terminó inesperadamente."))?
        .map_err(|_| {
            public_error(
                "MODEL_REMOVE",
                "No se pudo eliminar el pack. El pack activo está protegido.",
            )
        })
}

#[tauri::command]
pub async fn rollback_model(state: State<'_, AppState>) -> Result<ModelPackInfo, PublicError> {
    let models = state.models.clone();
    tauri::async_runtime::spawn_blocking(move || models.rollback())
        .await
        .map_err(|_| {
            public_error(
                "MODEL_TASK",
                "La tarea de rollback terminó inesperadamente.",
            )
        })?
        .map_err(|_| {
            public_error(
                "MODEL_ROLLBACK",
                "No existe un pack anterior válido para restaurar.",
            )
        })
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
