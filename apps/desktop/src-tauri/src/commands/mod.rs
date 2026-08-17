//! Adaptadores IPC. Solo devuelven DTOs públicos y mensajes sanitizados.

use crate::bootstrap::AppState;
use mily_cache::CacheStatus;
use mily_config::AppConfig;
use mily_core::{AppStatus, EngineManager, ModelManager, PublicError};
use mily_system::SystemSnapshot;
use tauri::State;

fn public_error(code: &str, message: &str) -> PublicError {
    PublicError::new(code, message)
}

#[tauri::command]
pub fn get_app_status(state: State<'_, AppState>) -> AppStatus {
    AppStatus {
        version: env!("CARGO_PKG_VERSION").to_string(),
        engine: state.engine.status(),
        models: state.models.status(),
        installed_models: state.models.installed_count(),
        extension_connected: false,
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
    // El valor en SQLite facilita diagnósticos/migraciones sin duplicar secretos.
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
