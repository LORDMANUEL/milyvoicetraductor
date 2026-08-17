//! Composición de dependencias de la aplicación.
//!
//! Mantener este módulo pequeño evita que los comandos Tauri construyan o
//! conozcan detalles internos de cada servicio.

use mily_cache::CacheService;
use mily_config::{AppPaths, ConfigService};
use mily_core::{UnavailableEngineManager, UnavailableModelManager};
use mily_database::DatabaseService;
use mily_logging::LogService;
use mily_system::SystemInfoService;

/// Estado compartido e inmutable en estructura. Los servicios realizan I/O
/// breve bajo demanda y no mantienen threads de fondo en Fase 1.
pub struct AppState {
    pub config: ConfigService,
    pub database: DatabaseService,
    pub cache: CacheService,
    pub logger: LogService,
    pub system: SystemInfoService,
    pub engine: UnavailableEngineManager,
    pub models: UnavailableModelManager,
}

impl AppState {
    /// Inicializa directorios, migraciones y servicios con defaults seguros.
    pub fn initialize() -> Result<Self, String> {
        let paths = AppPaths::discover().map_err(|_| "APP_PATHS".to_string())?;
        paths.ensure_exists().map_err(|_| "APP_PATHS_CREATE".to_string())?;

        let config = ConfigService::new(paths.config_dir.join("config.json"));
        let loaded = config.load_or_default().map_err(|_| "CONFIG_READ".to_string())?;
        // Persistir defaults desde el primer inicio deja el esquema explícito.
        config.save(&loaded).map_err(|_| "CONFIG_WRITE".to_string())?;

        let database = DatabaseService::open(paths.data_dir.join("milyvoice.db"))
            .map_err(|_| "DATABASE_OPEN".to_string())?;
        let cache = CacheService::new(
            paths.cache_dir,
            loaded.cache_limit_mb.saturating_mul(1024 * 1024),
        );
        let logger = LogService::new(paths.log_dir, 2 * 1024 * 1024, 4);
        let _ = logger.write("info", "MilyVoiceTraductor inició la Fase 1.");

        Ok(Self {
            config,
            database,
            cache,
            logger,
            system: SystemInfoService,
            engine: UnavailableEngineManager,
            models: UnavailableModelManager,
        })
    }
}
