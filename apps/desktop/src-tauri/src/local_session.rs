//! Sesión privada Desktop → motor local.
//!
//! El token interno nunca se muestra al usuario ni se persiste en el frontend.
//! La extensión continúa usando credenciales efímeras mediante Native Messaging.

use crate::bootstrap::AppState;
use mily_core::PublicError;
use serde::Serialize;
use tauri::State;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LocalEngineSession {
    pub port: u16,
    pub credential: String,
}

fn public_error(code: &str, message: &str) -> PublicError {
    PublicError::new(code, message)
}

#[tauri::command]
pub fn get_local_engine_session(
    state: State<'_, AppState>,
) -> Result<LocalEngineSession, PublicError> {
    let config = state.config.load_or_default().map_err(|_| {
        public_error(
            "CONFIG_READ",
            "No se pudo leer la configuración para iniciar la sesión local.",
        )
    })?;

    state.engine.start(config.engine_port).map_err(|_| {
        public_error(
            "ENGINE_START",
            "No se pudo iniciar el motor local para esta fuente de audio.",
        )
    })?;

    let credential = state.engine.pairing_token().map_err(|_| {
        public_error(
            "ENGINE_CREDENTIAL",
            "No se pudo crear una sesión privada con el motor local.",
        )
    })?;

    Ok(LocalEngineSession {
        port: config.engine_port,
        credential,
    })
}
