#[cfg(any(windows, test))]
use serde::Deserialize;
#[cfg(windows)]
use mily_logging::{LogService, RepairStatus};
#[cfg(any(windows, test))]
use std::path::{Path, PathBuf};
#[cfg(windows)]
use std::process::{Command, Stdio};
use thiserror::Error;

#[cfg(any(windows, test))]
#[derive(Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
struct BootstrapStatus {
    #[serde(default)]
    code: String,
    #[serde(default)]
    message: String,
    #[serde(default)]
    stage: String,
}

#[cfg(any(windows, test))]
pub fn bundled_bootstrap_from_exe(executable: &Path) -> Option<PathBuf> {
    executable
        .parent()
        .map(|root| root.join("bootstrap").join("setup-installed.ps1"))
        .filter(|path| path.is_file())
}

#[cfg(any(windows, test))]
fn bootstrap_status_from_root(app_root: &Path) -> Option<BootstrapStatus> {
    let text = std::fs::read_to_string(app_root.join("bootstrap").join("status.json")).ok()?;
    serde_json::from_str(&text).ok()
}

#[cfg(windows)]
fn local_app_root() -> PathBuf {
    std::env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
        .join("MilyVoiceTraductor")
}

#[cfg(windows)]
fn repair_logger(app_root: &Path) -> LogService {
    LogService::new(app_root.join("logs"), 2 * 1024 * 1024, 4)
}

#[cfg(windows)]
pub fn repair_current_installation() -> Result<(), RepairError> {
    use std::os::windows::process::CommandExt;

    const CREATE_NO_WINDOW: u32 = 0x0800_0000;

    let app_root = local_app_root();
    let logger = repair_logger(&app_root);
    let incident_id = logger.new_incident_id("repair");
    let _ = logger.record_repair(
        &incident_id,
        RepairStatus::Started,
        "desktop",
        "REPAIR_START",
        "REPAIR_REQUESTED",
        "Se inició la reparación controlada de la instalación local.",
        "Ejecutar bootstrap incluido y volver a diagnosticar componentes.",
    );

    let executable = match std::env::current_exe() {
        Ok(value) => value,
        Err(error) => {
            let _ = logger.record_repair(
                &incident_id,
                RepairStatus::Failed,
                "desktop",
                "REPAIR_START",
                "REPAIR_EXE_LOOKUP_FAILED",
                "No se pudo localizar el ejecutable instalado.",
                "Reinstalar el mismo paquete de MilyVoice.",
            );
            return Err(RepairError::Io(error));
        }
    };
    let install_root = match executable.parent() {
        Some(value) => value,
        None => {
            let _ = logger.record_repair(
                &incident_id,
                RepairStatus::Failed,
                "desktop",
                "REPAIR_START",
                "REPAIR_INSTALL_ROOT_MISSING",
                "No se encontró la raíz de la instalación.",
                "Reinstalar el mismo paquete de MilyVoice.",
            );
            return Err(RepairError::InstallRootMissing);
        }
    };
    let script = match bundled_bootstrap_from_exe(&executable) {
        Some(value) => value,
        None => {
            let _ = logger.record_repair(
                &incident_id,
                RepairStatus::Failed,
                "desktop",
                "REPAIR_START",
                "REPAIR_BOOTSTRAP_MISSING",
                "No se encontró el bootstrap incluido junto al ejecutable.",
                "Reinstalar el mismo paquete para restaurar los componentes incluidos.",
            );
            return Err(RepairError::BootstrapMissing);
        }
    };
    let powershell = std::env::var_os("WINDIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(r"C:\Windows"))
        .join("System32")
        .join("WindowsPowerShell")
        .join("v1.0")
        .join("powershell.exe");

    let mut command = Command::new(powershell);
    command
        .arg("-NoProfile")
        .arg("-NonInteractive")
        .arg("-ExecutionPolicy")
        .arg("Bypass")
        .arg("-File")
        .arg(&script)
        .arg("-InstallRoot")
        .arg(install_root)
        .arg("-AppRoot")
        .arg(&app_root)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    command.creation_flags(CREATE_NO_WINDOW);

    let status = match command.status() {
        Ok(value) => value,
        Err(error) => {
            let _ = logger.record_repair(
                &incident_id,
                RepairStatus::Failed,
                "bootstrap",
                "REPAIR_SPAWN",
                "REPAIR_POWERSHELL_FAILED",
                "No se pudo iniciar el bootstrap de reparación.",
                "Comprobar Windows PowerShell 5.1 o reinstalar el paquete.",
            );
            return Err(RepairError::Io(error));
        }
    };

    if status.success() {
        let _ = logger.record_repair(
            &incident_id,
            RepairStatus::Succeeded,
            "bootstrap",
            "BOOTSTRAP_FINALIZE",
            "BOOTSTRAP_OK",
            "La reparación terminó y el runtime local volvió a quedar operativo.",
            "Ninguna; volver a abrir la traducción y validar el modelo activo.",
        );
        return Ok(());
    }

    let failure = bootstrap_status_from_root(&app_root);
    let stage = failure
        .as_ref()
        .map(|value| value.stage.as_str())
        .filter(|value| !value.is_empty())
        .unwrap_or("BOOTSTRAP_FAILED");
    let code = failure
        .as_ref()
        .map(|value| value.code.as_str())
        .filter(|value| !value.is_empty())
        .unwrap_or("BOOTSTRAP_FAILED");
    let message = failure
        .as_ref()
        .map(|value| value.message.as_str())
        .filter(|value| !value.is_empty())
        .unwrap_or("La preparación local no terminó correctamente.");
    let _ = logger.record_repair(
        &incident_id,
        RepairStatus::Failed,
        "bootstrap",
        stage,
        code,
        message,
        "Usar el código registrado para reparar el componente indicado y reintentar.",
    );
    Err(RepairError::BootstrapFailed)
}

#[cfg(not(windows))]
pub fn repair_current_installation() -> Result<(), RepairError> {
    Err(RepairError::UnsupportedPlatform)
}

#[derive(Debug, Error)]
pub enum RepairError {
    #[error("no se pudo localizar el ejecutable: {0}")]
    Io(#[from] std::io::Error),
    #[cfg(windows)]
    #[error("no se encontró la raíz de instalación")]
    InstallRootMissing,
    #[cfg(windows)]
    #[error("no se encontró el bootstrap incluido")]
    BootstrapMissing,
    #[cfg(windows)]
    #[error("el bootstrap devolvió error")]
    BootstrapFailed,
    #[cfg(not(windows))]
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
        let script = root.path().join("bootstrap").join("setup-installed.ps1");
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

    #[test]
    fn bootstrap_failure_reader_keeps_only_structured_public_fields() {
        let root = tempdir().unwrap();
        let status_root = root.path().join("bootstrap");
        std::fs::create_dir_all(&status_root).unwrap();
        std::fs::write(
            status_root.join("status.json"),
            r#"{"state":"failed","code":"RUNTIME_IMPORT_FAILED","message":"Falta ctranslate2","stage":"RUNTIME_IMPORT"}"#,
        )
        .unwrap();
        let parsed = bootstrap_status_from_root(root.path()).unwrap();
        assert_eq!(parsed.code, "RUNTIME_IMPORT_FAILED");
        assert_eq!(parsed.stage, "RUNTIME_IMPORT");
        assert_eq!(parsed.message, "Falta ctranslate2");
    }
}
