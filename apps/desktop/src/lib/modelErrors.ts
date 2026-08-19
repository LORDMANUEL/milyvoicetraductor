export interface PublicModelError {
  code?: string;
  message?: string;
}

const FALLBACK_MESSAGES: Record<string, string> = {
  MODEL_NO_NETWORK: 'No hay conexión disponible para continuar la descarga. Comprueba Internet y pulsa Reintentar.',
  MODEL_NO_SPACE: 'No hay suficiente espacio libre para instalar el modelo. Libera espacio y pulsa Reintentar.',
  MODEL_PROVIDER_ERROR: 'El proveedor de modelos no pudo completar la descarga. Puedes reintentar sin perder los archivos válidos.',
  MODEL_DOWNLOAD_INTERRUPTED: 'La descarga se interrumpió. Pulsa Reintentar para continuar desde los archivos ya descargados.',
  MODEL_HASH_MISMATCH: 'La verificación de integridad falló. El pack no será activado hasta descargarse correctamente.',
  MODEL_RUNTIME_ERROR: 'El motor local no está preparado correctamente. Usa Reparar instalación y vuelve a intentarlo.',
  MODEL_PERMISSION_ERROR: 'Windows bloqueó la escritura en la carpeta local de modelos. Revisa permisos y vuelve a intentarlo.',
  MODEL_CONVERSION_ERROR: 'El modelo se descargó, pero la optimización INT8 no pudo terminar. Pulsa Reintentar; si continúa, usa Reparar instalación.',
  MODEL_LICENSE_BLOCKED: 'Este pack no está permitido para el perfil de uso seleccionado.',
  MODEL_EXTERNAL_UNSAFE: 'El pack externo contiene archivos, rutas o tamaños que MilyVoice no permite por seguridad.',
  MODEL_EXTERNAL_MANIFEST: 'El manifiesto externo está incompleto o declara un motor, proveedor, licencia o presupuesto no permitido.',
  MODEL_EXTERNAL_INVALID: 'El archivo externo no es un .mmpack válido o no contiene los componentes declarados.',
  MODEL_EXTERNAL_SOURCE: 'Solo se permiten enlaces HTTPS de GitHub o Hugging Face que apunten a un archivo .mmpack.',
  MODEL_EXTERNAL_TOO_LARGE: 'El repositorio externo supera el límite máximo permitido para una descarga de modelos.',
  PROCESS_MEMORY_LIMIT: 'Este modelo superaría el máximo de 2 GB asignado a todo MilyVoice. Usa un perfil Lite o ejecuta Optimizar automáticamente.',
  VRAM_LIMIT: 'Este modelo necesita más de los 384 MB de VRAM reservados por MilyVoice en una GPU de 512 MB.',
  NO_COMPATIBLE_ENGINE: 'Ningún motor instalado pasó simultáneamente las pruebas de velocidad, estabilidad y memoria.'
};

/**
 * Convierte el rechazo serializado de Tauri en un mensaje recuperable.
 * Los códigos conocidos siempre conservan un texto de producto comprensible.
 * Un mensaje del backend solo sustituye ese fallback cuando parece una frase
 * pública deliberada, no una etiqueta/diagnóstico corto como "offline".
 */
export function modelErrorMessage(error: unknown): string {
  const candidate = error && typeof error === 'object' ? error as PublicModelError : {};
  const code = typeof candidate.code === 'string' ? candidate.code : 'MODEL_PROVIDER_ERROR';
  const safeMessage = typeof candidate.message === 'string' ? candidate.message.trim() : '';
  const safeForUi = safeMessage.length >= 12
    && safeMessage.length <= 300
    && /\s/.test(safeMessage)
    && !/[\\/]Users[\\/]|\/home\/|token=|authorization:/i.test(safeMessage);

  if (safeForUi) return safeMessage;
  return FALLBACK_MESSAGES[code] ?? FALLBACK_MESSAGES.MODEL_PROVIDER_ERROR;
}

export function modelErrorCode(error: unknown): string {
  if (error && typeof error === 'object' && 'code' in error && typeof (error as PublicModelError).code === 'string') {
    return (error as PublicModelError).code as string;
  }
  return 'MODEL_PROVIDER_ERROR';
}
