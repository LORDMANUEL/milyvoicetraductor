//! Punto de entrada de la aplicación de escritorio MilyVoiceTraductor.

mod bootstrap;
mod commands;

use bootstrap::AppState;
use commands::{
    clear_cache, get_app_status, get_cache_status, get_config, get_system_info, save_config,
};

/// Construye Tauri con el estado y comandos mínimos de la Fase 1.
pub fn run() {
    let state = match AppState::initialize() {
        Ok(state) => state,
        Err(code) => {
            eprintln!("MilyVoiceTraductor no pudo iniciar: {code}");
            return;
        }
    };

    tauri::Builder::default()
        .manage(state)
        .invoke_handler(tauri::generate_handler![
            get_app_status,
            get_system_info,
            get_config,
            save_config,
            get_cache_status,
            clear_cache
        ])
        .run(tauri::generate_context!())
        .expect("error no recuperable al ejecutar MilyVoiceTraductor");
}
