# Arquitectura de Fase 1

La aplicación usa una arquitectura de puertos y servicios pequeña. La UI solamente consume DTOs públicos mediante comandos Tauri. Ningún componente Svelte abre archivos, ejecuta SQL o inspecciona el sistema directamente.

## Límites

- `mily-core`: contratos de dominio y estados públicos.
- `mily-config`: rutas de la aplicación y configuración JSON atómica.
- `mily-database`: SQLite y migraciones versionadas.
- `mily-logging`: sanitización y escritura/rotación de logs.
- `mily-cache`: almacenamiento regenerable con TTL y límite.
- `mily-system`: snapshot ligero del equipo.
- `src-tauri`: composición de servicios y adaptadores IPC.
- `src`: presentación Svelte y gateway tipado.

## Regla de dependencia

Los crates de infraestructura pueden depender de `mily-core` cuando sea necesario. `mily-core` no depende de Tauri, Svelte ni del sistema de ventanas.
