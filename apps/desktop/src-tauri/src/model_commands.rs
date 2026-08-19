//! Comandos Tauri específicos del Engine Hub 2.1.

use crate::bootstrap::AppState;
use mily_core::{ModelPackInfo, PublicError};
use mily_models::AutoSelectionResult;
use std::path::PathBuf;
use tauri::State;

fn public_error(code: &str, message: &str) -> PublicError {
    PublicError::new(code, message)
}

#[tauri::command]
pub async fn activate_model(
    state: State<'_, AppState>,
    pack_id: String,
    version: String,
) -> Result<ModelPackInfo, PublicError> {
    let models = state.models.clone();
    let logger = state.logger.clone();
    tauri::async_runtime::spawn_blocking(move || models.activate(&pack_id, &version))
        .await
        .map_err(|_| {
            public_error(
                "MODEL_RUNTIME_ERROR",
                "La activación terminó inesperadamente.",
            )
        })?
        .inspect(|pack| {
            let _ = logger.write(
                "info",
                &format!("Modelo activado por Engine Hub: {}", pack.id),
            );
        })
        .map_err(|error| public_error(error.public_code(), error.public_message()))
}

#[tauri::command]
pub async fn import_model_pack(
    state: State<'_, AppState>,
    path: String,
) -> Result<ModelPackInfo, PublicError> {
    let models = state.models.clone();
    let logger = state.logger.clone();
    let archive = PathBuf::from(path);
    tauri::async_runtime::spawn_blocking(move || models.import_pack(&archive))
        .await
        .map_err(|_| {
            public_error(
                "MODEL_RUNTIME_ERROR",
                "La importación terminó inesperadamente.",
            )
        })?
        .inspect(|pack| {
            let _ = logger.write("info", &format!("Pack externo validado: {}", pack.id));
        })
        .map_err(|error| public_error(error.public_code(), error.public_message()))
}

#[tauri::command]
pub async fn optimize_models(
    state: State<'_, AppState>,
    route: String,
    force_benchmark: bool,
) -> Result<AutoSelectionResult, PublicError> {
    let models = state.models.clone();
    let logger = state.logger.clone();
    tauri::async_runtime::spawn_blocking(move || models.auto_select(&route, force_benchmark))
        .await
        .map_err(|_| {
            public_error(
                "MODEL_RUNTIME_ERROR",
                "El benchmark terminó inesperadamente.",
            )
        })?
        .inspect(|selection| {
            let _ = logger.write(
                "info",
                &format!(
                    "Engine Hub seleccionó {} sobre {}.",
                    selection.selected, selection.backend
                ),
            );
        })
        .map_err(|error| public_error(error.public_code(), error.public_message()))
}
