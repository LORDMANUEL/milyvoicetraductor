//! Caché local regenerable, acotada y expirable.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs;
use std::path::PathBuf;
use std::sync::{
    Arc,
    atomic::{AtomicU64, Ordering},
};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use thiserror::Error;

#[derive(Debug, Clone, Serialize, Deserialize)]
struct CacheMeta {
    created_at: u64,
    expires_at: Option<u64>,
    size: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CacheStatus {
    pub bytes: u64,
    pub entries: usize,
    pub max_bytes: u64,
}

/// Servicio de caché por archivos. Las claves se hashean para impedir path traversal.
#[derive(Debug, Clone)]
pub struct CacheService {
    directory: PathBuf,
    max_bytes: Arc<AtomicU64>,
}

impl CacheService {
    pub fn new(directory: impl Into<PathBuf>, max_bytes: u64) -> Self {
        Self {
            directory: directory.into(),
            max_bytes: Arc::new(AtomicU64::new(max_bytes.max(1024 * 1024))),
        }
    }

    pub fn put(&self, key: &str, value: &[u8], ttl: Option<Duration>) -> Result<(), CacheError> {
        fs::create_dir_all(&self.directory)?;
        let stem = hashed_key(key);
        let now = unix_now();
        fs::write(self.data_path(&stem), value)?;
        let meta = CacheMeta {
            created_at: now,
            expires_at: ttl.map(|duration| now.saturating_add(duration.as_secs())),
            size: value.len() as u64,
        };
        fs::write(self.meta_path(&stem), serde_json::to_vec(&meta)?)?;
        self.prune()?;
        Ok(())
    }

    pub fn get(&self, key: &str) -> Result<Option<Vec<u8>>, CacheError> {
        let stem = hashed_key(key);
        let meta_path = self.meta_path(&stem);
        let data_path = self.data_path(&stem);
        if !meta_path.exists() || !data_path.exists() {
            return Ok(None);
        }
        let meta: CacheMeta = serde_json::from_slice(&fs::read(&meta_path)?)?;
        if meta.expires_at.is_some_and(|expiry| expiry <= unix_now()) {
            let _ = fs::remove_file(meta_path);
            let _ = fs::remove_file(data_path);
            return Ok(None);
        }
        Ok(Some(fs::read(data_path)?))
    }

    /// Actualiza el límite en caliente sin reconstruir el servicio.
    pub fn set_max_bytes(&self, max_bytes: u64) {
        self.max_bytes
            .store(max_bytes.max(1024 * 1024), Ordering::Relaxed);
        let _ = self.prune();
    }

    pub fn clear(&self) -> Result<(), CacheError> {
        if self.directory.exists() {
            fs::remove_dir_all(&self.directory)?;
        }
        fs::create_dir_all(&self.directory)?;
        Ok(())
    }

    pub fn status(&self) -> Result<CacheStatus, CacheError> {
        let entries = self.load_entries()?;
        Ok(CacheStatus {
            bytes: entries.iter().map(|(_, meta)| meta.size).sum(),
            entries: entries.len(),
            max_bytes: self.max_bytes.load(Ordering::Relaxed),
        })
    }

    /// Elimina expirados y, si es necesario, los más antiguos hasta respetar el límite.
    pub fn prune(&self) -> Result<(), CacheError> {
        if !self.directory.exists() {
            return Ok(());
        }
        let now = unix_now();
        let mut entries = self.load_entries()?;
        for (stem, meta) in &entries {
            if meta.expires_at.is_some_and(|expiry| expiry <= now) {
                self.remove_pair(stem);
            }
        }
        entries = self.load_entries()?;
        entries.sort_by_key(|(_, meta)| meta.created_at);
        let mut total: u64 = entries.iter().map(|(_, meta)| meta.size).sum();
        let max_bytes = self.max_bytes.load(Ordering::Relaxed);
        for (stem, meta) in entries {
            if total <= max_bytes {
                break;
            }
            self.remove_pair(&stem);
            total = total.saturating_sub(meta.size);
        }
        Ok(())
    }

    fn load_entries(&self) -> Result<Vec<(String, CacheMeta)>, CacheError> {
        if !self.directory.exists() {
            return Ok(Vec::new());
        }
        let mut entries = Vec::new();
        for entry in fs::read_dir(&self.directory)? {
            let entry = entry?;
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str()) != Some("json") {
                continue;
            }
            let Some(stem) = path.file_stem().and_then(|s| s.to_str()) else {
                continue;
            };
            if let Ok(meta) = serde_json::from_slice::<CacheMeta>(&fs::read(&path)?) {
                entries.push((stem.to_string(), meta));
            }
        }
        Ok(entries)
    }

    fn data_path(&self, stem: &str) -> PathBuf {
        self.directory.join(format!("{stem}.bin"))
    }

    fn meta_path(&self, stem: &str) -> PathBuf {
        self.directory.join(format!("{stem}.json"))
    }

    fn remove_pair(&self, stem: &str) {
        let _ = fs::remove_file(self.data_path(stem));
        let _ = fs::remove_file(self.meta_path(stem));
    }
}

fn hashed_key(key: &str) -> String {
    let digest = Sha256::digest(key.as_bytes());
    format!("{digest:x}")
}

fn unix_now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

#[derive(Debug, Error)]
pub enum CacheError {
    #[error("Error de caché local: {0}")]
    Io(#[from] std::io::Error),
    #[error("Metadatos de caché inválidos: {0}")]
    Json(#[from] serde_json::Error),
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn cache_roundtrip_and_clear_are_functional() {
        let dir = tempdir().unwrap();
        let cache = CacheService::new(dir.path(), 1024 * 1024);
        cache.put("status", b"ok", None).unwrap();
        assert_eq!(cache.get("status").unwrap(), Some(b"ok".to_vec()));
        cache.clear().unwrap();
        assert_eq!(cache.get("status").unwrap(), None);
    }

    #[test]
    fn expired_entry_is_removed_on_read() {
        let dir = tempdir().unwrap();
        let cache = CacheService::new(dir.path(), 1024 * 1024);
        cache.put("short", b"data", Some(Duration::ZERO)).unwrap();
        assert_eq!(cache.get("short").unwrap(), None);
    }

    #[test]
    fn status_reports_real_usage() {
        let dir = tempdir().unwrap();
        let cache = CacheService::new(dir.path(), 1024 * 1024);
        cache.put("a", b"1234", None).unwrap();
        let status = cache.status().unwrap();
        assert_eq!(status.entries, 1);
        assert_eq!(status.bytes, 4);
    }
}
