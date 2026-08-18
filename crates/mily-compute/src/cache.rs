use crate::{BackendObservation, ComputeBackend};
use serde::{Deserialize, Serialize};
use std::fs;
use std::io;
use std::path::PathBuf;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BenchmarkKey {
    pub hardware_fingerprint: String,
    pub model_pack: String,
    pub model_version: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CachedSelection {
    pub key: BenchmarkKey,
    pub backend: ComputeBackend,
    pub observation: BackendObservation,
}

#[derive(Debug, Clone)]
pub struct SelectionCache {
    path: PathBuf,
}

impl SelectionCache {
    pub fn new(path: impl Into<PathBuf>) -> Self {
        Self { path: path.into() }
    }

    pub fn load_for(&self, key: &BenchmarkKey) -> io::Result<Option<CachedSelection>> {
        let text = match fs::read_to_string(&self.path) {
            Ok(text) => text,
            Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(None),
            Err(error) => return Err(error),
        };
        let cached: CachedSelection = serde_json::from_str(&text)
            .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
        Ok((cached.key == *key).then_some(cached))
    }

    pub fn save(&self, selection: &CachedSelection) -> io::Result<()> {
        if let Some(parent) = self.path.parent() {
            fs::create_dir_all(parent)?;
        }
        let serialized = serde_json::to_vec_pretty(selection)
            .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
        let temporary = self.path.with_extension("tmp");
        fs::write(&temporary, serialized)?;
        fs::rename(temporary, &self.path)?;
        Ok(())
    }
}
