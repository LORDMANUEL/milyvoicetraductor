//! Lectura segura de sesiones persistidas por el motor local.

use mily_config::AppPaths;
use mily_core::SessionSummary;
use serde::Deserialize;
use std::fs;
use thiserror::Error;

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
struct SessionMetadata {
    id: String,
    created_at: String,
    source_language: String,
    target_language: String,
    duration_seconds: f64,
    segment_count: usize,
}

#[derive(Debug, Clone)]
pub struct SessionService {
    paths: AppPaths,
}

impl SessionService {
    pub fn new(paths: AppPaths) -> Self {
        Self { paths }
    }

    pub fn list(&self) -> Vec<SessionSummary> {
        let Ok(entries) = fs::read_dir(&self.paths.sessions_dir) else {
            return Vec::new();
        };
        let mut sessions = Vec::new();
        for entry in entries.flatten() {
            let metadata_path = entry.path().join("session.json");
            let Ok(text) = fs::read_to_string(metadata_path) else {
                continue;
            };
            let Ok(metadata) = serde_json::from_str::<SessionMetadata>(&text) else {
                continue;
            };
            sessions.push(SessionSummary {
                id: metadata.id,
                created_at: metadata.created_at,
                source_language: metadata.source_language,
                target_language: metadata.target_language,
                duration_seconds: metadata.duration_seconds,
                segment_count: metadata.segment_count,
            });
        }
        sessions.sort_by(|left, right| right.created_at.cmp(&left.created_at));
        sessions
    }

    pub fn export_text(&self, session_id: &str, format: &str) -> Result<String, SessionError> {
        if !valid_session_id(session_id) {
            return Err(SessionError::InvalidId);
        }
        let file_name = match format {
            "txt" => "translation.txt",
            "srt" => "translation.srt",
            _ => return Err(SessionError::InvalidFormat),
        };
        Ok(fs::read_to_string(
            self.paths.sessions_dir.join(session_id).join(file_name),
        )?)
    }

    pub fn delete(&self, session_id: &str) -> Result<(), SessionError> {
        if !valid_session_id(session_id) {
            return Err(SessionError::InvalidId);
        }
        let folder = self.paths.sessions_dir.join(session_id);
        if folder.is_dir() {
            fs::remove_dir_all(folder)?;
        }
        Ok(())
    }
}

fn valid_session_id(value: &str) -> bool {
    value.len() == 32 && value.bytes().all(|byte| byte.is_ascii_hexdigit())
}

#[derive(Debug, Error)]
pub enum SessionError {
    #[error("Identificador de sesión inválido.")]
    InvalidId,
    #[error("Formato de exportación inválido.")]
    InvalidFormat,
    #[error("No se pudo leer la sesión.")]
    Io(#[from] std::io::Error),
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn session_id_validation_blocks_path_traversal() {
        assert!(!valid_session_id("../../secret"));
        assert!(valid_session_id("0123456789abcdef0123456789abcdef"));
    }
}
