//! Punto de entrada de la aplicación de escritorio MilyVoiceTraductor.

mod bootstrap;
mod commands;
mod local_session;
mod repair;

use bootstrap::AppState;
use commands::*;
use local_session::*;

pub fn run() {
    let state = match AppState::initialize() {
        Ok(state) => state,
        Err(code) => {
            eprintln!("MilyVoiceTraductor no pudo iniciar: {code}");
            return;
        }
    };

    // El autoarranque es opt-in y nunca impide abrir la interfaz si el motor
    // no está instalado o tiene un problema recuperable.
    if let Ok(config) = state.config.load_or_default()
        && config.auto_start_engine
    {
        let _ = state.engine.start(config.engine_port);
    }

    tauri::Builder::default()
        .manage(state)
        .invoke_handler(tauri::generate_handler![
            get_app_status,
            get_onboarding_status,
            repair_installation,
            get_system_info,
            get_hardware_advisor,
            get_config,
            save_config,
            get_cache_status,
            clear_cache,
            get_engine_status,
            start_engine,
            stop_engine,
            get_local_engine_session,
            get_model_catalog,
            install_model,
            verify_model,
            remove_model,
            rollback_model,
            list_sessions,
            get_session_export,
            delete_session,
            get_runtime_locations
        ])
        .run(tauri::generate_context!())
        .expect("error no recuperable al ejecutar MilyVoiceTraductor");
}
