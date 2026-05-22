const TOAST_CONTAINER_ID = 'incomplete-request-toast-container';

export function safeText(value, fallback = '-') {
  if (value === null || value === undefined || value === '') return fallback;
  return String(value);
}

export function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

export function formatTags(tagsValue) {
  if (Array.isArray(tagsValue)) return tagsValue.join(', ');
  if (tagsValue && typeof tagsValue === 'object' && Array.isArray(tagsValue.tags)) {
    return tagsValue.tags.join(', ');
  }
  return '-';
}

export function formatDateTime(isoText) {
  if (!isoText) return '-';
  const date = new Date(isoText);
  if (Number.isNaN(date.getTime())) return safeText(isoText);
  return date.toLocaleString();
}

export function withUtcTitle(isoText) {
  return `<span title="UTC: ${escapeHtml(safeText(isoText))}">${escapeHtml(formatDateTime(isoText))}</span>`;
}

export function formatElapsedSince(isoText) {
  if (!isoText) return '-';
  const createdAt = new Date(isoText);
  if (Number.isNaN(createdAt.getTime())) return '-';
  const elapsedMs = Date.now() - createdAt.getTime();
  if (elapsedMs <= 0) return '刚刚';

  const totalMinutes = Math.floor(elapsedMs / 60000);
  const totalHours = Math.floor(totalMinutes / 60);
  const days = Math.floor(totalHours / 24);
  const hours = totalHours % 24;
  const minutes = totalMinutes % 60;

  if (days > 0) {
    return hours > 0 ? `${days}天${hours}小时` : `${days}天`;
  }
  if (hours > 0) {
    return minutes > 0 ? `${hours}小时${minutes}分钟` : `${hours}小时`;
  }
  if (minutes > 0) {
    return `${minutes}分钟`;
  }
  return '刚刚';
}

export function formatRelativeToNow(isoText) {
  if (!isoText) return '-';
  const target = new Date(isoText);
  if (Number.isNaN(target.getTime())) return '-';
  const diffMs = Date.now() - target.getTime();
  if (Math.abs(diffMs) < 60000) return '刚刚';

  const suffix = diffMs >= 0 ? '前' : '后';
  const totalMinutes = Math.floor(Math.abs(diffMs) / 60000);
  const totalHours = Math.floor(totalMinutes / 60);
  const days = Math.floor(totalHours / 24);
  const hours = totalHours % 24;
  const minutes = totalMinutes % 60;

  if (days > 0) {
    if (hours > 0) return `${days}天${hours}小时${suffix}`;
    return `${days}天${suffix}`;
  }
  if (hours > 0) {
    if (minutes > 0) return `${hours}小时${minutes}分钟${suffix}`;
    return `${hours}小时${suffix}`;
  }
  if (minutes > 0) {
    return `${minutes}分钟${suffix}`;
  }
  return '刚刚';
}

export function formatDetailJson(payload) {
  try {
    return JSON.stringify(payload ?? {}, null, 2);
  } catch {
    return '{}';
  }
}

export function buildRetryIdempotencyKey(requestId, mode) {
  return `admin_retry:${mode}:${requestId}:${Date.now()}:${Math.random().toString(36).slice(2, 10)}`;
}

export function showToast(message, isError = false) {
  let container = document.getElementById(TOAST_CONTAINER_ID);
  if (!container) {
    container = document.createElement('div');
    container.id = TOAST_CONTAINER_ID;
    container.style.position = 'fixed';
    container.style.top = '20px';
    container.style.right = '20px';
    container.style.zIndex = '1060';
    document.body.appendChild(container);
  }
  const alert = document.createElement('div');
  alert.className = `alert ${isError ? 'alert-danger' : 'alert-success'}`;
  alert.textContent = message;
  container.appendChild(alert);
  window.setTimeout(() => alert.remove(), 3000);
}
