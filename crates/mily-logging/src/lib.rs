//! Logging local con sanitización obligatoria antes de persistir.

use regex::Regex;
use serde::{Deserialize, Serialize};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};
use thiserror::Error;

static INCIDENT_COUNTER: AtomicU64 = AtomicU64::new(1);

/// Sanitiza datos frecuentes que nunca deben terminar en archivos de log.
pub fn sanitize_log_message(input: &str) -> String {
    let secret =
        Regex::new(r"(?i)\b(token|password|passwd|secret|api[_-]?key)\b\s*[:=]\s*[^\s,;]+")
            .expect("valid secret regex");
    let email =
        Regex::new(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b").expect("valid email regex");
    let windows_home =
        Regex::new(r"(?i)[A-Z]:\\Users\\[^\\\s]+").expect("valid windows path regex");
    let unix_home = Regex::new(r"/(?:home|Users)/[^/\s]+").expect("valid unix path regex");

    let output = secret.replace_all(input, "$1=<REDACTED>");
    let output = email.replace_all(&output, "<EMAIL>");
    let output = windows_home.replace_all(&output, "<USER_HOME>");
    unix_home.replace_all(&output, "<USER_HOME>").into_owned()
}

fn sanitize_identifier(input: &str, fallback: &str) -> String {
    let value: String = input
        .trim()
        .chars()
        .filter(|character| {
            character.is_ascii_alphanumeric() || matches!(character, '_' | '-' | '.')
        })
        .take(96)
        .collect();
    if value.is_empty() {
        fallback.to_string()
    } else {
        value
    }
}

fn unix_timestamp_seconds() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

/// Estado de un intento de reparación correlacionado.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub enum RepairStatus {
    Started,
    Succeeded,
    Failed,
}

/// Evento estructurado y sanitizado para diagnóstico/reparación.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct RepairEvent {
    pub schema_version: u8,
    pub incident_id: String,
    pub timestamp: u64,
    pub status: RepairStatus,
    pub component: String,
    pub stage: String,
    pub code: String,
    pub message: String,
    pub action: String,
}

/// Servicio local acotado. Mantiene log humano y un historial JSONL de reparación.
#[derive(Debug, Clone)]
pub struct LogService {
    directory: PathBuf,
    max_bytes: u64,
    keep_files: usize,
}

impl LogService {
    pub fn new(directory: impl Into<PathBuf>, max_bytes: u64, keep_files: usize) -> Self {
        Self {
            directory: directory.into(),
            max_bytes: max_bytes.max(64 * 1024),
            keep_files: keep_files.max(1),
        }
    }

    /// Persiste una línea sanitizada y rota el archivo cuando supera el límite.
    pub fn write(&self, level: &str, message: &str) -> Result<(), LogError> {
        fs::create_dir_all(&self.directory)?;
        self.rotate_if_needed("milyvoice.log", "milyvoice-", ".log")?;
        let log_path = self.directory.join("milyvoice.log");
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(log_path)?;
        let timestamp = unix_timestamp_seconds();
        writeln!(
            file,
            "{timestamp} [{}] {}",
            level.to_ascii_uppercase(),
            sanitize_log_message(message)
        )?;
        Ok(())
    }

    /// Genera un ID opaco local para correlacionar fallo, intento y resultado.
    pub fn new_incident_id(&self, component: &str) -> String {
        let component = sanitize_identifier(component, "incident");
        let counter = INCIDENT_COUNTER.fetch_add(1, Ordering::Relaxed);
        format!(
            "{component}-{}-{}-{counter}",
            unix_timestamp_seconds(),
            std::process::id()
        )
    }

    /// Añade un evento de reparación JSONL sin persistir secretos ni rutas de usuario.
    #[allow(clippy::too_many_arguments)]
    pub fn record_repair(
        &self,
        incident_id: &str,
        status: RepairStatus,
        component: &str,
        stage: &str,
        code: &str,
        message: &str,
        action: &str,
    ) -> Result<RepairEvent, LogError> {
        fs::create_dir_all(&self.directory)?;
        self.rotate_if_needed("repair-history.jsonl", "repair-history-", ".jsonl")?;
        let event = RepairEvent {
            schema_version: 1,
            incident_id: sanitize_identifier(incident_id, "incident-unknown"),
            timestamp: unix_timestamp_seconds(),
            status,
            component: sanitize_identifier(component, "unknown"),
            stage: sanitize_identifier(stage, "UNKNOWN"),
            code: sanitize_identifier(code, "UNKNOWN"),
            message: sanitize_log_message(message),
            action: sanitize_log_message(action),
        };
        let line = serde_json::to_string(&event)?;
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(self.directory.join("repair-history.jsonl"))?;
        writeln!(file, "{line}")?;
        Ok(event)
    }

    /// Devuelve los eventos más recientes primero, leyendo también rotaciones.
    pub fn recent_repairs(&self, limit: usize) -> Result<Vec<RepairEvent>, LogError> {
        if limit == 0 || !self.directory.is_dir() {
            return Ok(Vec::new());
        }
        let mut files: Vec<PathBuf> = fs::read_dir(&self.directory)?
            .filter_map(Result::ok)
            .map(|entry| entry.path())
            .filter(|path| {
                let Some(name) = path.file_name().and_then(|value| value.to_str()) else {
                    return false;
                };
                name == "repair-history.jsonl"
                    || (name.starts_with("repair-history-") && name.ends_with(".jsonl"))
            })
            .collect();
        files.sort_by_key(|path| {
            fs::metadata(path)
                .and_then(|metadata| metadata.modified())
                .ok()
        });
        files.reverse();

        let mut output = Vec::with_capacity(limit.min(64));
        for path in files {
            let text = match fs::read_to_string(path) {
                Ok(value) => value,
                Err(_) => continue,
            };
            for line in text.lines().rev() {
                let Ok(event) = serde_json::from_str::<RepairEvent>(line) else {
                    continue;
                };
                output.push(event);
                if output.len() >= limit {
                    return Ok(output);
                }
            }
        }
        Ok(output)
    }

    fn rotate_if_needed(
        &self,
        active_name: &str,
        rotated_prefix: &str,
        suffix: &str,
    ) -> Result<(), LogError> {
        let active = self.directory.join(active_name);
        if active.metadata().map(|m| m.len()).unwrap_or(0) < self.max_bytes {
            return Ok(());
        }
        let stamp = unix_timestamp_seconds();
        fs::rename(
            &active,
            self.directory
                .join(format!("{rotated_prefix}{stamp}{suffix}")),
        )?;
        self.prune_old_logs(rotated_prefix, suffix)?;
        Ok(())
    }

    fn prune_old_logs(&self, prefix: &str, suffix: &str) -> Result<(), LogError> {
        let mut rotated: Vec<_> = fs::read_dir(&self.directory)?
            .filter_map(Result::ok)
            .filter(|entry| {
                let name = entry.file_name();
                let name = name.to_string_lossy();
                name.starts_with(prefix) && name.ends_with(suffix)
            })
            .collect();
        rotated.sort_by_key(|entry| entry.metadata().and_then(|m| m.modified()).ok());
        let to_remove = rotated.len().saturating_sub(self.keep_files);
        for entry in rotated.into_iter().take(to_remove) {
            let _ = fs::remove_file(entry.path());
        }
        Ok(())
    }

    pub fn directory(&self) -> &Path {
        &self.directory
    }
}

#[derive(Debug, Error)]
pub enum LogError {
    #[error("No se pudo escribir o leer el log local: {0}")]
    Io(#[from] std::io::Error),
    #[error("No se pudo serializar el evento local: {0}")]
    Json(#[from] serde_json::Error),
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn sanitizer_redacts_secrets_emails_and_user_homes() {
        let unix_home = ["", "home", "sample-user", "data"].join("/");
        let input = format!(
            "token=abc123 contact=user@example.com path=C:\\Users\\SampleUser\\AppData unix={unix_home}"
        );
        let clean = sanitize_log_message(&input);
        assert!(!clean.contains("abc123"));
        assert!(!clean.contains("user@example.com"));
        assert!(!clean.contains("SampleUser"));
        assert!(!clean.contains("sample-user"));
        assert!(clean.contains("<REDACTED>"));
    }

    #[test]
    fn service_writes_only_sanitized_content() {
        let dir = tempdir().unwrap();
        let service = LogService::new(dir.path(), 64 * 1024, 2);
        service
            .write("info", "password=hunter2 user=test@example.com")
            .unwrap();
        let content = fs::read_to_string(dir.path().join("milyvoice.log")).unwrap();
        assert!(!content.contains("hunter2"));
        assert!(!content.contains("test@example.com"));
    }
}
