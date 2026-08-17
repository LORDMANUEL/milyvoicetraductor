//! Composición de dependencias de la aplicación.
//!
//! Tauri recibe un único `AppState`; cada servicio mantiene una responsabilidad
//! concreta y puede probarse fuera de la interfaz.

use mily_cache::CacheService;
use mily_config::{AppPaths, ConfigService};
use mily_database::DatabaseService;
use mily_engine::EngineProcessManager;
use mily_logging::LogService;
use mily_models::ModelManagerService;
use mily_sessions::SessionService;
use mily_system::SystemInfoService;

#[derive(Clone)]
pub struct AppState {
    pub paths: AppPaths,
    pub config: ConfigService,
    pub database: DatabaseService,
    pub cache: CacheService,
    pub logger: LogService,
    pub system: SystemInfoService,
    pub engine: EngineProcessManager,
    pub models: ModelManagerService,
    pub sessions: SessionService,
}

impl AppState {
    pub fn initialize() -> Result<Self, String> {
        let paths = AppPaths::discover().map_err(|_| "APP_PATHS".to_string())?;
        paths
            .ensure_exists()
            .map_err(|_| "APP_PATHS_CREATE".to_string())?;

        let config = ConfigService::new(paths.config_dir.join("config.json"));
        let loaded = config
            .load_or_default()
            .map_err(|_| "CONFIG_READ".to_string())?;
        config
            .save(&loaded)
            .map_err(|_| "CONFIG_WRITE".to_string())?;
        config
            .save_engine_config(&loaded)
            .map_err(|_| "ENGINE_CONFIG_WRITE".to_string())?;

        let database = DatabaseService::open(paths.data_dir.join("milyvoice.db"))
            .map_err(|_| "DATABASE_OPEN".to_string())?;
        let cache = CacheService::new(
            paths.cache_dir.clone(),
            loaded.cache_limit_mb.saturating_mul(1024 * 1024),
        );
        let logger = LogService::new(paths.log_dir.clone(), 2 * 1024 * 1024, 4);
        let _ = logger.write("info", "MilyVoiceTraductor inició su plataforma local.");
        let engine = EngineProcessManager::new(paths.clone());
        let models = ModelManagerService::new(paths.clone());
        let sessions = SessionService::new(paths.clone());

        Ok(Self {
            paths,
            config,
            database,
            cache,
            logger,
            system: SystemInfoService,
            engine,
            models,
            sessions,
        })
    }
}
