use mily_config::{AppPaths, ConfigService};
use mily_core::ComponentState;
use mily_engine::EngineProcessManager;
use mily_models::ModelManagerService;
use serde::Serialize;
use std::fs;
use std::time::{SystemTime, UNIX_EPOCH};
use thiserror::Error;
use uuid::Uuid;

pub const EXTENSION_ORIGIN: &str = "chrome-extension://edcpjonegaempcifgodcmgejbcpdpddm/";
const CREDENTIAL_TTL_SECONDS: u64 = 300;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BridgeReply {
    pub protocol: u8,
    pub r#type: &'static str,
    pub desktop: &'static str,
    pub engine: &'static str,
    pub port: u16,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub credential: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub expires_at: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model_pack: Option<String>,
    pub message: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct EphemeralCredential<'a> {
    schema_version: u8,
    token: &'a str,
    expires_at: u64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct ExtensionHeartbeat {
    schema_version: u8,
    at: u64,
    transport: &'static str,
}

pub struct BridgeRuntime {
    paths: AppPaths,
    config: ConfigService,
    engine: EngineProcessManager,
    models: ModelManagerService,
}

impl BridgeRuntime {
    pub fn discover() -> Result<Self, BridgeRuntimeError> {
        let paths = AppPaths::discover()?;
        paths.ensure_exists()?;
        let config = ConfigService::new(paths.config_dir.join("config.json"));
        Ok(Self {
            engine: EngineProcessManager::new(paths.clone()),
            models: ModelManagerService::new(paths.clone()),
            paths,
            config,
        })
    }

    pub fn status(&self, ensure_started: bool) -> Result<BridgeReply, BridgeRuntimeError> {
        self.write_extension_heartbeat()?;
        let config = self.config.load_or_default()?;
        let mut engine_status = self.engine.status(config.engine_port);
        if ensure_started && matches!(engine_status.state, ComponentState::Stopped) {
            engine_status = self.engine.start(config.engine_port)?;
        }

        let model_pack = self
            .models
            .installed()
            .into_iter()
            .find(|pack| pack.active)
            .map(|pack| format!("{}@{}", pack.id, pack.version));

        // Una consulta de estado jamás debe crear credenciales. La credencial efímera
        // se emite únicamente para `hello`, que es la operación usada al iniciar captura.
        let (credential, expires_at) =
            if should_issue_credential(ensure_started, &engine_status.state) {
                let credential = self.issue_ephemeral_credential()?;
                (Some(credential.0), Some(credential.1))
            } else {
                (None, None)
            };

        let engine = component_state_name(&engine_status.state);
        let message = match engine_status.state {
            ComponentState::Ready if model_pack.is_some() => {
                "Aplicación, motor y modelo listos.".into()
            }
            ComponentState::Ready => "Motor conectado; el modelo todavía no está listo.".into(),
            ComponentState::Stopped => "Motor instalado y detenido.".into(),
            ComponentState::NotInstalled => "Runtime local no instalado.".into(),
            ComponentState::Error => "El motor local requiere reparación.".into(),
        };

        Ok(BridgeReply {
            protocol: 1,
            r#type: "bridge.ready",
            desktop: "ready",
            engine,
            port: config.engine_port,
            credential,
            expires_at,
            model_pack,
            message,
        })
    }

    fn write_extension_heartbeat(&self) -> Result<(), BridgeRuntimeError> {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|_| BridgeRuntimeError::Clock)?
            .as_secs();
        let payload = ExtensionHeartbeat {
            schema_version: 1,
            at: now,
            transport: "nativeMessaging",
        };
        let path = self.paths.data_dir.join("extension-heartbeat.json");
        let temp = self.paths.data_dir.join("extension-heartbeat.json.tmp");
        fs::write(&temp, serde_json::to_vec(&payload)?)?;
        fs::rename(temp, path)?;
        Ok(())
    }

    fn issue_ephemeral_credential(&self) -> Result<(String, u64), BridgeRuntimeError> {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|_| BridgeRuntimeError::Clock)?
            .as_secs();
        let expires_at = now.saturating_add(CREDENTIAL_TTL_SECONDS);
        let token = format!("{}{}", Uuid::new_v4().simple(), Uuid::new_v4().simple());
        let payload = EphemeralCredential {
            schema_version: 1,
            token: &token,
            expires_at,
        };
        let path = self.paths.config_dir.join("native-credential.json");
        let temp = self.paths.config_dir.join("native-credential.json.tmp");
        fs::write(&temp, serde_json::to_vec(&payload)?)?;
        fs::rename(temp, path)?;
        Ok((token, expires_at))
    }
}

fn should_issue_credential(ensure_started: bool, state: &ComponentState) -> bool {
    ensure_started && matches!(state, ComponentState::Ready)
}

pub fn caller_origin_allowed(origin: &str) -> bool {
    origin == EXTENSION_ORIGIN
}

fn component_state_name(state: &ComponentState) -> &'static str {
    match state {
        ComponentState::Ready => "ready",
        ComponentState::Stopped => "stopped",
        ComponentState::NotInstalled => "notInstalled",
        ComponentState::Error => "error",
    }
}

#[derive(Debug, Error)]
pub enum BridgeRuntimeError {
    #[error("rutas de aplicación no disponibles: {0}")]
    Config(#[from] mily_config::ConfigError),
    #[error("motor local no disponible: {0}")]
    Engine(#[from] mily_engine::EngineError),
    #[error("error de archivo local: {0}")]
    Io(#[from] std::io::Error),
    #[error("error serializando estado local: {0}")]
    Json(#[from] serde_json::Error),
    #[error("reloj del sistema inválido")]
    Clock,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_the_pinned_extension_origin_is_accepted() {
        assert!(caller_origin_allowed(EXTENSION_ORIGIN));
        assert!(!caller_origin_allowed(
            "chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/"
        ));
        assert!(!caller_origin_allowed("https://example.com"));
    }

    #[test]
    fn status_never_issues_a_credential() {
        assert!(!should_issue_credential(false, &ComponentState::Ready));
        assert!(!should_issue_credential(false, &ComponentState::Stopped));
    }

    #[test]
    fn hello_only_issues_a_credential_when_engine_is_ready() {
        assert!(should_issue_credential(true, &ComponentState::Ready));
        assert!(!should_issue_credential(true, &ComponentState::Stopped));
        assert!(!should_issue_credential(
            true,
            &ComponentState::NotInstalled
        ));
        assert!(!should_issue_credential(true, &ComponentState::Error));
    }
}
