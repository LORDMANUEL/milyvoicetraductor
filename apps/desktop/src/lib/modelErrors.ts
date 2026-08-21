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
  MODEL_OPERATION_BUSY: 'Ya hay otra operación de modelos en curso. Espera a que termine y vuelve a intentarlo.'
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
