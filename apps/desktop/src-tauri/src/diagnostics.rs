use crate::bootstrap::AppState;
use mily_logging::RepairEvent;
use tauri::State;

/// Devuelve únicamente eventos ya sanitizados por `mily-logging`.
#[tauri::command]
pub fn get_repair_history(state: State<'_, AppState>, limit: Option<usize>) -> Vec<RepairEvent> {
    let requested = limit.unwrap_or(40).clamp(1, 100);
    state.logger.recent_repairs(requested).unwrap_or_default()
}
