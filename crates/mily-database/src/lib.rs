//! SQLite local y migraciones monotónicas de MilyVoiceTraductor.

use rusqlite::{Connection, params};
use std::fs;
use std::path::{Path, PathBuf};
use thiserror::Error;

const MIGRATIONS: &[(i64, &str)] = &[
    (
        1,
        r#"
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS app_state (
            key TEXT PRIMARY KEY NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS session_index (
            id TEXT PRIMARY KEY NOT NULL,
            created_at TEXT NOT NULL,
            source_language TEXT NOT NULL,
            target_language TEXT NOT NULL,
            duration_seconds INTEGER NOT NULL DEFAULT 0
        );
        "#,
    ),
    (
        2,
        r#"
        CREATE TABLE IF NOT EXISTS component_versions (
            component TEXT PRIMARY KEY NOT NULL,
            version TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS model_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_pack TEXT NOT NULL,
            action TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        "#,
    ),
];

#[derive(Debug, Clone)]
pub struct DatabaseService {
    path: PathBuf,
}

impl DatabaseService {
    pub fn open(path: impl Into<PathBuf>) -> Result<Self, DatabaseError> {
        let service = Self { path: path.into() };
        if let Some(parent) = service.path.parent() {
            fs::create_dir_all(parent)?;
        }
        service.apply_migrations()?;
        Ok(service)
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    pub fn apply_migrations(&self) -> Result<(), DatabaseError> {
        let mut connection = Connection::open(&self.path)?;
        connection.pragma_update(None, "journal_mode", "WAL")?;
        connection.execute_batch(
            "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY NOT NULL);",
        )?;
        for (version, sql) in MIGRATIONS {
            let exists: bool = connection.query_row(
                "SELECT EXISTS(SELECT 1 FROM schema_migrations WHERE version = ?1)",
                [version],
                |row| row.get(0),
            )?;
            if exists {
                continue;
            }
            let tx = connection.transaction()?;
            tx.execute_batch(sql)?;
            tx.execute(
                "INSERT INTO schema_migrations(version) VALUES (?1)",
                [version],
            )?;
            tx.commit()?;
        }
        Ok(())
    }

    pub fn set_setting(&self, key: &str, value: &str) -> Result<(), DatabaseError> {
        let connection = Connection::open(&self.path)?;
        connection.execute(
            "INSERT INTO settings(key, value, updated_at) VALUES (?1, ?2, CURRENT_TIMESTAMP)\n             ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP",
            params![key, value],
        )?;
        Ok(())
    }

    pub fn get_setting(&self, key: &str) -> Result<Option<String>, DatabaseError> {
        let connection = Connection::open(&self.path)?;
        let mut statement = connection.prepare("SELECT value FROM settings WHERE key = ?1")?;
        let mut rows = statement.query([key])?;
        Ok(rows.next()?.map(|row| row.get(0)).transpose()?)
    }

    pub fn record_model_event(&self, model_pack: &str, action: &str) -> Result<(), DatabaseError> {
        let connection = Connection::open(&self.path)?;
        connection.execute(
            "INSERT INTO model_events(model_pack, action) VALUES (?1, ?2)",
            params![model_pack, action],
        )?;
        Ok(())
    }

    pub fn migration_version(&self) -> Result<i64, DatabaseError> {
        let connection = Connection::open(&self.path)?;
        Ok(connection.query_row(
            "SELECT COALESCE(MAX(version), 0) FROM schema_migrations",
            [],
            |row| row.get(0),
        )?)
    }
}

#[derive(Debug, Error)]
pub enum DatabaseError {
    #[error("Error de archivo de base de datos: {0}")]
    Io(#[from] std::io::Error),
    #[error("Error SQLite local: {0}")]
    Sqlite(#[from] rusqlite::Error),
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn migrations_reach_current_schema_and_are_idempotent() {
        let dir = tempdir().unwrap();
        let db = DatabaseService::open(dir.path().join("mily.db")).unwrap();
        assert_eq!(db.migration_version().unwrap(), 2);
        db.apply_migrations().unwrap();
        assert_eq!(db.migration_version().unwrap(), 2);
    }
}
