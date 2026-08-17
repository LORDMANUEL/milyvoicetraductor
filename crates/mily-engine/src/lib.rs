//! Gestión del proceso local de IA y del token de emparejamiento.
//!
//! Este crate no conoce Tauri. Su responsabilidad es descubrir un runtime,
//! iniciar/detener el proceso y exponer estados honestos al resto de la app.

use mily_config::AppPaths;
use mily_core::{ComponentState, EngineRuntimeStatus};
use serde::{Deserialize, Serialize};
use std::fs;
use std::io;
use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::{Duration, SystemTime};
use thiserror::Error;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LaunchSpec {
    pub program: PathBuf,
    pub prefix_args: Vec<String>,
}

impl LaunchSpec {
    /// Busca primero un sidecar compilado y luego el runtime Python administrado.
    pub fn discover(paths: &AppPaths) -> Option<Self> {
        if let Ok(explicit) = std::env::var("MILYVOICE_ENGINE_PATH") {
            let path = PathBuf::from(explicit);
            if path.is_file() {
                return Some(Self {
                    program: path,
                    prefix_args: Vec::new(),
                });
            }
        }

        let compiled = paths.bin_dir.join(if cfg!(windows) {
            "mily-ai-engine.exe"
        } else {
            "mily-ai-engine"
        });
        if compiled.is_file() {
            return Some(Self {
                program: compiled,
                prefix_args: Vec::new(),
            });
        }

        let python_candidates = if cfg!(windows) {
            vec![
                paths.engine_dir.join("python").join("python.exe"),
                paths
                    .engine_dir
                    .join("python")
                    .join("Scripts")
                    .join("python.exe"),
            ]
        } else {
            vec![
                paths.engine_dir.join("python").join("bin").join("python3"),
                paths.engine_dir.join("python").join("bin").join("python"),
            ]
        };
        let script = paths.engine_dir.join("app").join("main.py");
        if script.is_file()
            && let Some(python) = python_candidates
                .into_iter()
                .find(|candidate| candidate.is_file())
        {
            return Some(Self {
                program: python,
                prefix_args: vec![script.to_string_lossy().into_owned()],
            });
        }
        None
    }

    pub fn command(&self) -> Command {
        let mut command = Command::new(&self.program);
        command.args(&self.prefix_args);
        command
    }
}

/// Maneja el secreto de puente sin imprimirlo ni incluirlo en diagnósticos.
#[derive(Debug, Clone)]
pub struct PairingTokenStore {
    path: PathBuf,
}

impl PairingTokenStore {
    pub fn new(path: impl Into<PathBuf>) -> Self {
        Self { path: path.into() }
    }

    pub fn get_or_create(&self) -> Result<String, EngineError> {
        if let Ok(existing) = fs::read_to_string(&self.path) {
            let token = existing.trim();
            if token.len() >= 40 {
                return Ok(token.to_owned());
            }
        }
        if let Some(parent) = self.path.parent() {
            fs::create_dir_all(parent)?;
        }
        let token = format!("{}{}", Uuid::new_v4().simple(), Uuid::new_v4().simple());
        let temp = self.path.with_extension("tmp");
        fs::write(&temp, token.as_bytes())?;
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            fs::set_permissions(&temp, fs::Permissions::from_mode(0o600))?;
        }
        fs::rename(temp, &self.path)?;
        Ok(token)
    }
}

/// Gestor clonable; el `Child` real queda protegido por un mutex interno.
#[derive(Debug, Clone)]
pub struct EngineProcessManager {
    paths: AppPaths,
    child: Arc<Mutex<Option<Child>>>,
}

impl EngineProcessManager {
    pub fn new(paths: AppPaths) -> Self {
        Self {
            paths,
            child: Arc::new(Mutex::new(None)),
        }
    }

    pub fn is_installed(&self) -> bool {
        LaunchSpec::discover(&self.paths).is_some()
    }

    pub fn pairing_token(&self) -> Result<String, EngineError> {
        PairingTokenStore::new(self.paths.config_dir.join("bridge-token.txt")).get_or_create()
    }

    pub fn status(&self, port: u16) -> EngineRuntimeStatus {
        if Self::port_open(port) {
            let pid = self
                .child
                .lock()
                .ok()
                .and_then(|guard| guard.as_ref().map(Child::id));
            return EngineRuntimeStatus {
                state: ComponentState::Ready,
                pid,
                port,
                message: "Motor local activo".into(),
            };
        }
        EngineRuntimeStatus {
            state: if self.is_installed() {
                ComponentState::Stopped
            } else {
                ComponentState::NotInstalled
            },
            pid: None,
            port,
            message: if self.is_installed() {
                "Motor local instalado y detenido".into()
            } else {
                "Motor local no instalado".into()
            },
        }
    }

    pub fn start(&self, port: u16) -> Result<EngineRuntimeStatus, EngineError> {
        if Self::port_open(port) {
            return Ok(self.status(port));
        }
        let spec = LaunchSpec::discover(&self.paths).ok_or(EngineError::NotInstalled)?;
        let _ = self.pairing_token()?;
        let mut command = spec.command();
        command
            .arg("serve")
            .arg("--port")
            .arg(port.to_string())
            .arg("--data-dir")
            .arg(&self.paths.data_dir)
            .arg("--config-dir")
            .arg(&self.paths.config_dir)
            .arg("--cache-dir")
            .arg(&self.paths.cache_dir)
            .arg("--models-dir")
            .arg(&self.paths.models_dir)
            .arg("--parent-pid")
            .arg(std::process::id().to_string())
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());

        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            command.creation_flags(CREATE_NO_WINDOW);
        }

        let child = command.spawn()?;
        let child_id = child.id();
        *self.child.lock().map_err(|_| EngineError::PoisonedLock)? = Some(child);

        // Espera breve al bind del servidor; cargar modelos ocurre después.
        for _ in 0..30 {
            if Self::port_open(port) {
                return Ok(EngineRuntimeStatus {
                    state: ComponentState::Ready,
                    pid: Some(child_id),
                    port,
                    message: "Motor local activo".into(),
                });
            }
            std::thread::sleep(Duration::from_millis(100));
        }
        Err(EngineError::StartupTimeout)
    }

    pub fn stop(&self, port: u16) -> Result<EngineRuntimeStatus, EngineError> {
        let mut guard = self.child.lock().map_err(|_| EngineError::PoisonedLock)?;
        if let Some(child) = guard.as_mut() {
            let _ = child.kill();
            let _ = child.wait();
        }
        *guard = None;
        Ok(self.status(port))
    }

    pub fn extension_connected(&self) -> bool {
        let heartbeat = self.paths.data_dir.join("extension-heartbeat.json");
        let Ok(modified) = fs::metadata(heartbeat).and_then(|metadata| metadata.modified()) else {
            return false;
        };
        SystemTime::now()
            .duration_since(modified)
            .map(|age| age < Duration::from_secs(30))
            .unwrap_or(false)
    }

    pub fn launch_spec(&self) -> Option<LaunchSpec> {
        LaunchSpec::discover(&self.paths)
    }

    fn port_open(port: u16) -> bool {
        let address = SocketAddr::from(([127, 0, 0, 1], port));
        TcpStream::connect_timeout(&address, Duration::from_millis(120)).is_ok()
    }
}

#[derive(Debug, Error)]
pub enum EngineError {
    #[error("El motor local no está instalado.")]
    NotInstalled,
    #[error("El motor no abrió el puerto local a tiempo.")]
    StartupTimeout,
    #[error("Estado interno no disponible.")]
    PoisonedLock,
    #[error("Error de sistema al gestionar el motor: {0}")]
    Io(#[from] io::Error),
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::tempdir;

    #[test]
    fn pairing_token_is_stable_and_long() {
        let dir = tempdir().unwrap();
        let store = PairingTokenStore::new(dir.path().join("token.txt"));
        let first = store.get_or_create().unwrap();
        let second = store.get_or_create().unwrap();
        assert_eq!(first, second);
        assert!(first.len() >= 40);
    }
}
