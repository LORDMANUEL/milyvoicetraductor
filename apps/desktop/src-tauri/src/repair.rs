use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use thiserror::Error;

pub fn bundled_bootstrap_from_exe(executable: &Path) -> Option<PathBuf> {
    executable
        .parent()
        .map(|root| {
            root.join("resources")
                .join("bootstrap")
                .join("setup-installed.ps1")
        })
        .filter(|path| path.is_file())
}

#[cfg(windows)]
pub fn repair_current_installation() -> Result<(), RepairError> {
    let executable = std::env::current_exe()?;
    let install_root = executable.parent().ok_or(RepairError::InstallRootMissing)?;
    let script = bundled_bootstrap_from_exe(&executable).ok_or(RepairError::BootstrapMissing)?;
    let powershell = std::env::var_os("WINDIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(r"C:\Windows"))
        .join("System32")
        .join("WindowsPowerShell")
        .join("v1.0")
        .join("powershell.exe");

    let status = Command::new(powershell)
        .arg("-NoProfile")
        .arg("-NonInteractive")
        .arg("-ExecutionPolicy")
        .arg("Bypass")
        .arg("-File")
        .arg(&script)
        .arg("-InstallRoot")
        .arg(install_root)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()?;
    if status.success() {
        Ok(())
    } else {
        Err(RepairError::BootstrapFailed)
    }
}

#[cfg(not(windows))]
pub fn repair_current_installation() -> Result<(), RepairError> {
    Err(RepairError::UnsupportedPlatform)
}

#[derive(Debug, Error)]
pub enum RepairError {
    #[error("no se pudo localizar el ejecutable: {0}")]
    Io(#[from] std::io::Error),
    #[error("no se encontró la raíz de instalación")]
    InstallRootMissing,
    #[error("no se encontró el bootstrap incluido")]
    BootstrapMissing,
    #[error("el bootstrap devolvió error")]
    BootstrapFailed,
    #[error("reparación no soportada en esta plataforma")]
    UnsupportedPlatform,
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn repair_only_resolves_the_bundled_bootstrap_beside_the_executable() {
        let root = tempdir().unwrap();
        let exe = root.path().join("MilyVoiceTraductor.exe");
        let script = root.path().join("resources/bootstrap/setup-installed.ps1");
        std::fs::create_dir_all(script.parent().unwrap()).unwrap();
        std::fs::write(&exe, b"exe").unwrap();
        std::fs::write(&script, b"script").unwrap();
        assert_eq!(bundled_bootstrap_from_exe(&exe), Some(script));
    }

    #[test]
    fn repair_refuses_when_the_bundled_script_is_missing() {
        let root = tempdir().unwrap();
        let exe = root.path().join("MilyVoiceTraductor.exe");
        std::fs::write(&exe, b"exe").unwrap();
        assert_eq!(bundled_bootstrap_from_exe(&exe), None);
    }
}
