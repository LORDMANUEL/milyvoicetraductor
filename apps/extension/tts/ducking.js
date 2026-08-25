export function clampDuckingLevel(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 0.25;
  return Math.min(1, Math.max(0.05, numeric));
}

export function setDuckingGain(gainParam, enabled, value) {
  if (!gainParam) return null;
  const target = enabled ? clampDuckingLevel(value) : 1;
  gainParam.value = target;
  return target;
}

export function restoreGain(gainParam) {
  if (!gainParam) return null;
  gainParam.value = 1;
  return 1;
}
