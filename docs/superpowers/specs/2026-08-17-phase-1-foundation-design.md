# MilyVoiceTraductor — Fase 1: Fundación de escritorio

Fecha: 2026-08-17
Versión de diseño: 1.0
Estado: aprobado para planificación

## 1. Objetivo

Construir la primera fase funcional de MilyVoiceTraductor como una aplicación de escritorio ligera y mantenible, preparada para operar en equipos Windows con o sin GPU. La Fase 1 no ejecutará modelos de IA todavía; sí dejará completamente operativos la aplicación Tauri, la interfaz, persistencia, configuración, logging seguro, caché, diagnóstico de hardware, estructura de módulos y contratos necesarios para integrar el motor de IA y la extensión Chromium en fases posteriores.

## 2. Principios obligatorios

1. **Privacidad por defecto.** No se envían transcripciones, audio, credenciales, diagnósticos identificables ni contenidos de reuniones a terceros. La aplicación no tendrá telemetría en Fase 1.
2. **No exponer datos de terceros.** Los logs nunca incluirán contenido de reuniones, tokens, rutas sensibles completas, correos, nombres de usuario del sistema ni secretos. Toda salida diagnóstica debe ser sanitizada.
3. **Limpieza y orden.** Directorios, módulos, nombres, responsabilidades y dependencias deben permanecer organizados. No se aceptan archivos monolíticos ni lógica mezclada entre UI, dominio e infraestructura.
4. **Ligereza.** El proceso principal debe mantener el menor consumo razonable de RAM/CPU. No se incluirán frameworks o servicios adicionales sin necesidad funcional.
5. **CPU-first con aceleración opcional.** La aplicación debe iniciar y operar su Fase 1 en un equipo sin GPU. La detección de GPU solo informa capacidades futuras; nunca bloquea el uso.
6. **Código segmentado y comprensible.** Cada módulo tiene una responsabilidad clara y una interfaz explícita.
7. **Programación orientada a objetos con criterio.** Se usarán structs, traits y servicios encapsulados en Rust; clases/servicios únicamente donde aporten estado, contratos o sustitución clara. No se forzará OOP sobre funciones puras.
8. **Código comentado.** Cada módulo público, estructura principal, trait, servicio, comando Tauri y bloque de lógica no obvia tendrá comentarios/documentación en español. No se agregarán comentarios redundantes a sintaxis trivial.
9. **Sin secretos en repositorio.** Ninguna clave, token, contraseña, endpoint privado o dato personal se versiona. `.env` queda ignorado y solo se incluye `.env.example` sin secretos.
10. **Errores observables y recuperables.** Los errores se tipan, se registran de forma sanitizada y se muestran al usuario con mensajes claros sin exponer información interna.
11. **Versionado desde el inicio.** Aplicación `0.1.0`, esquema de base de datos versionado y configuración versionada.
12. **Criterio de terminado.** Una función no se marca como completa hasta que compile, tenga prueba pertinente y pase el flujo de verificación definido.

## 3. Alcance de Fase 1

### Incluido

- Tauri 2 + Rust 2024.
- Svelte 5 + TypeScript + Vite.
- Branding MilyVoiceTraductor: verde esmeralda, azul zafiro, blanco hueso, azul marino de contraste y logo oficial de zebra con audífonos.
- Navegación funcional entre Panel, Traducción en vivo, Sesiones, Modelos, Permisos, Dispositivos, Ajustes, Ayuda y Acerca de.
- Persistencia SQLite local.
- Migraciones de base de datos.
- Configuración persistente.
- Servicio de rutas de aplicación.
- Logs estructurados y sanitizados con rotación y retención limitada.
- Caché local con límite de tamaño y limpieza.
- Detección de sistema operativo, arquitectura, RAM, CPU y GPU disponible cuando sea detectable sin dependencias pesadas.
- Estado de componentes futuros: motor IA, extensión y modelos.
- Interfaz `EngineManager` preparada para Fase 2.
- Interfaz `ModelManager` preparada para Fase 4.
- Pantalla de diagnóstico.
- Pruebas unitarias Rust.
- Pruebas de frontend.
- GitHub Actions para build, lint y tests.
- Documentación de arquitectura, desarrollo, privacidad y versionado.

### Excluido deliberadamente

- Descarga o ejecución real de modelos.
- Whisper/Qwen/Python sidecar.
- Captura de audio.
- Traducción en tiempo real.
- Extensión Chromium.
- Updater remoto de producción.
- Telemetría.
- Cuentas de usuario o servicios cloud.

Estas funciones pertenecen a fases posteriores y solo tendrán contratos/stubs de estado reales, nunca simulaciones que indiquen funcionamiento inexistente.

## 4. Arquitectura

```text
apps/desktop
  Svelte/TypeScript UI
        |
        | invoke()
        v
  Tauri command adapters
        |
        v
crates/mily-core
  Application services / domain contracts
        |
        +--> crates/mily-config
        +--> crates/mily-database
        +--> crates/mily-system
        +--> crates/mily-logging
        +--> crates/mily-cache
```

La UI no accede directamente a archivos, SQLite ni detalles del sistema. Todo acceso privilegiado se realiza mediante comandos Tauri del backend Rust. Los crates de dominio e infraestructura no dependen de la UI.

## 5. Estructura del repositorio

```text
milyvoicetraductor/
├── apps/
│   └── desktop/
│       ├── src/
│       │   ├── app/
│       │   ├── components/
│       │   ├── features/
│       │   ├── lib/
│       │   ├── routes/
│       │   ├── stores/
│       │   ├── styles/
│       │   └── types/
│       └── src-tauri/
│           ├── capabilities/
│           ├── icons/
│           └── src/
│               ├── commands/
│               ├── bootstrap/
│               └── main.rs
├── crates/
│   ├── mily-core/
│   ├── mily-config/
│   ├── mily-database/
│   ├── mily-system/
│   ├── mily-logging/
│   └── mily-cache/
├── packages/
│   └── brand/
├── docs/
│   ├── architecture/
│   ├── privacy/
│   └── superpowers/
│       ├── specs/
│       └── plans/
├── tests/
├── .github/workflows/
├── .gitignore
├── Cargo.toml
├── package.json
├── pnpm-workspace.yaml
├── README.md
├── CHANGELOG.md
├── SECURITY.md
└── VERSION
```

## 6. Modelo de servicios Rust

Los servicios principales serán objetos con dependencias explícitas e interfaces testeables.

### `AppPaths`

Responsable de resolver y crear directorios de datos, logs, caché y configuración. Nunca imprime rutas completas sensibles en logs.

### `ConfigService`

Responsable de leer, validar, migrar y escribir configuración de usuario. La escritura debe ser atómica para reducir corrupción.

### `DatabaseService`

Responsable de abrir SQLite, aplicar migraciones y exponer repositorios. SQLite se configura para un uso de escritorio simple y confiable.

### `LogService`

Responsable de inicializar logging estructurado. Aplica sanitización antes de persistir mensajes. No registra payloads de audio/transcripción ni secretos.

### `CacheService`

Responsable de almacenar únicamente datos regenerables. Mantiene metadatos de tamaño/fecha, permite `clear`, aplica límite de almacenamiento y elimina entradas expiradas.

### `SystemInfoService`

Responsable de obtener información mínima del equipo sin bloquear. Si una métrica no puede detectarse, devuelve `Unknown` y la UI continúa.

### `EngineManager`

Trait de contrato para el motor IA. Fase 1 implementa `UnavailableEngineManager`, cuyo estado real es `NotInstalled`; no simula traducción.

### `ModelManager`

Trait de contrato para los modelos. Fase 1 informa inventario vacío/no instalado y rutas previstas. No realiza descargas.

## 7. Persistencia

SQLite guardará únicamente metadatos propios de la aplicación en Fase 1.

Tablas iniciales:

- `schema_migrations`
- `settings`
- `app_state`
- `session_index` (estructura preparada, sin contenido de reuniones todavía)

No se almacenará audio ni texto de reuniones en Fase 1.

## 8. Configuración

La configuración incluirá como mínimo:

- versión de esquema;
- idioma de interfaz;
- idioma origen preferido (`auto`, `en`, `zh`);
- idioma destino (`es` en Fase 1);
- tema (`system`, `light`, `dark` preparado, interfaz inicial clara);
- inicio automático del motor cuando exista;
- límite de caché;
- nivel de log permitido;
- consentimiento de funciones futuras que impliquen micrófono.

Valores inválidos deben recuperar defaults seguros, registrar un aviso sanitizado y preservar una copia de recuperación cuando corresponda.

## 9. Logging y privacidad

Los niveles serán `ERROR`, `WARN`, `INFO`, `DEBUG` en desarrollo. En release, el nivel por defecto será `INFO`.

Reglas:

- No registrar contenido de reuniones.
- No registrar audio ni buffers.
- No registrar contraseñas, tokens o claves.
- No registrar variables de entorno completas.
- No registrar rutas de usuario completas; usar alias como `<APP_DATA>` cuando sea necesario.
- No registrar direcciones de correo o identificadores personales.
- Sanitizar errores de librerías antes de persistirlos.
- Rotar archivos de log y limitar retención.
- La función de exportar diagnóstico futura requerirá acción explícita del usuario.

## 10. Caché

La caché contiene solo datos regenerables y nunca constituye fuente de verdad.

- Directorio independiente.
- Límite configurable, default conservador.
- Limpieza LRU/por antigüedad simplificada.
- TTL para entradas temporales.
- Comando `clear_cache` funcional desde Ajustes.
- Ningún dato sensible de reunión en caché durante Fase 1.

## 11. UI y branding

Paleta base:

- Esmeralda: `#00A878`
- Zafiro: `#1769E0`
- Hueso: `#F7F4EA`
- Marino: `#10243E`

La interfaz debe cumplir:

- layout responsive dentro de la ventana;
- controles con estados reales;
- navegación por teclado razonable;
- contraste legible;
- indicadores de estado accesibles que no dependan únicamente del color;
- sin animaciones costosas o permanentes;
- logo y nombre de producto consistentes;
- componentes pequeños y reutilizables.

La pantalla Panel mostrará estado real de aplicación, motor, modelos, almacenamiento y sistema. `Motor IA: No instalado` y `Modelos: 0 instalados` son estados válidos de Fase 1.

## 12. Rendimiento

- No iniciar servicios innecesarios en background.
- No realizar polling continuo en Fase 1.
- Diagnóstico del sistema bajo demanda y caché breve de resultados.
- No cargar librerías de IA.
- No requerir GPU.
- Limitar dependencias frontend.
- Release build optimizado por tamaño cuando sea compatible con Tauri/Rust.

## 13. Manejo de errores

Los errores internos se modelan con tipos propios. Los comandos Tauri convierten errores internos a DTOs seguros:

```text
AppError
  -> log sanitizado
  -> PublicError { code, message }
  -> UI
```

La UI nunca recibe backtrace, SQL, rutas sensibles ni secretos.

## 14. Pruebas

### Rust

- resolución/creación de rutas;
- sanitización de logs;
- configuración default y migración;
- SQLite y migraciones;
- caché: put/get/expiry/clear/limit;
- diagnóstico con campos opcionales;
- estados `EngineManager` y `ModelManager`.

### Frontend

- navegación;
- render de estados;
- ajustes y persistencia mediante API mockeada;
- acciones de limpiar caché;
- errores visibles y seguros.

### Integración

- build frontend;
- `cargo test --workspace`;
- `cargo clippy --workspace --all-targets -- -D warnings`;
- `cargo fmt --check`;
- pruebas frontend;
- build Tauri cuando el runner soporte dependencias requeridas.

## 15. CI y calidad

GitHub Actions ejecutará:

1. formato;
2. lint Rust;
3. tests Rust;
4. lint/typecheck frontend;
5. tests frontend;
6. build frontend;
7. validación de secretos básica por patrones/configuración;
8. artefacto de build solo cuando la rama/release lo requiera.

No se publicarán logs de CI que incluyan secretos o archivos de usuario.

## 16. Versionado

- Producto: `0.1.0`.
- SemVer para código.
- Migraciones SQLite monotónicas.
- Configuración con `schema_version`.
- `CHANGELOG.md` desde el primer release.
- Commits pequeños y enfocados.

## 17. Criterios de aceptación de Fase 1

La fase se considera terminada únicamente cuando:

1. La aplicación compila en modo desarrollo y release.
2. Abre y navega por todas las vistas definidas.
3. Configuración persiste entre reinicios.
4. SQLite crea/aplica migraciones correctamente.
5. Logs se generan, rotan y sanitizan.
6. Caché puede consultarse, limitarse y limpiarse.
7. El panel muestra datos reales del sistema y estados reales de componentes futuros.
8. Funciona sin GPU.
9. Ningún test obligatorio falla.
10. Clippy/format/typecheck pasan sin warnings bloqueantes.
11. No existen secretos ni datos personales en el repositorio.
12. Documentación explica instalación, arquitectura, privacidad y desarrollo.
13. Cada módulo crítico está comentado y segmentado.
14. No quedan marcadores `TODO`, `TBD` o funciones falsas presentadas como completas.

## 18. Decisiones para fases posteriores

- Fase 2 integrará el motor IA como sidecar independiente, sin cambiar las interfaces públicas de la UI.
- Fase 3 incorporará la extensión Chromium mediante protocolo versionado local.
- Fase 4 implementará descargas de modelos con manifiesto, hash y rollback.
- Updater remoto se incorporará después de definir infraestructura de firma y release.
