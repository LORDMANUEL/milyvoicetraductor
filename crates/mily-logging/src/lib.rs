//! Logging local con sanitización obligatoria antes de persistir.

use regex::Regex;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};
use thiserror::Error;

/// Sanitiza datos frecuentes que nunca deben terminar en archivos de log.
pub fn sanitize_log_message(input: &str) -> String {
    let secret = Regex::new(r"(?i)\b(token|password|passwd|secret|api[_-]?key)\b\s*[:=]\s*[^\s,;]+")
        .expect("valid secret regex");
    let email = Regex::new(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
        .expect("valid email regex");
    let windows_home = Regex::new(r"(?i)[A-Z]:\\Users\\[^\\\s]+")
        .expect("valid windows path regex");
    let unix_home = Regex::new(r"/(?:home|Users)/[^/\s]+")
        .expect("valid unix path regex");

    let output = secret.replace_all(input, "$1=<REDACTED>");
    let output = email.replace_all(&output, "<EMAIL>");
    let output = windows_home.replace_all(&output, "<USER_HOME>");
    unix_home.replace_all(&output, "<USER_HOME>").into_owned()
}

/// Servicio de archivo sencillo, acotado y sin logging asíncrono permanente.
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
        self.rotate_if_needed()?;
        let log_path = self.directory.join("milyvoice.log");
        let mut file = OpenOptions::new().create(true).append(true).open(log_path)?;
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        writeln!(
            file,
            "{timestamp} [{}] {}",
            level.to_ascii_uppercase(),
            sanitize_log_message(message)
        )?;
        Ok(())
    }

    fn rotate_if_needed(&self) -> Result<(), LogError> {
        let active = self.directory.join("milyvoice.log");
        if active.metadata().map(|m| m.len()).unwrap_or(0) < self.max_bytes {
            return Ok(());
        }
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        fs::rename(&active, self.directory.join(format!("milyvoice-{stamp}.log")))?;
        self.prune_old_logs()?;
        Ok(())
    }

    fn prune_old_logs(&self) -> Result<(), LogError> {
        let mut rotated: Vec<_> = fs::read_dir(&self.directory)?
            .filter_map(Result::ok)
            .filter(|entry| {
                let name = entry.file_name();
                let name = name.to_string_lossy();
                name.starts_with("milyvoice-") && name.ends_with(".log")
            })
            .collect();
        rotated.sort_by_key(|entry| entry.metadata().and_then(|m| m.modified()).ok());
        let to_remove = rotated.len().saturating_sub(self.keep_files);
        for entry in rotated.into_iter().take(to_remove) {
            let _ = fs::remove_file(entry.path());
        }
        Ok(())
    }
}

#[derive(Debug, Error)]
pub enum LogError {
    #[error("No se pudo escribir el log local: {0}")]
    Io(#[from] std::io::Error),
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn sanitizer_redacts_secrets_emails_and_user_homes() {
        let unix_home = ["", "home", "sample-user", "data"].join("/");
        let input = format!("token=abc123 contact=user@example.com path=C:\\Users\\SampleUser\\AppData unix={unix_home}");
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
        service.write("info", "password=hunter2 user=test@example.com").unwrap();
        let content = fs::read_to_string(dir.path().join("milyvoice.log")).unwrap();
        assert!(!content.contains("hunter2"));
        assert!(!content.contains("test@example.com"));
    }
}
