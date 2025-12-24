import { API_CONFIG } from './config';

const MEDIA_ENDPOINT_PREFIX = `${API_CONFIG.baseUrl}/api/${API_CONFIG.version}/media/`;

const isHttpUrl = (value: string): boolean =>
  value.startsWith('http://') || value.startsWith('https://');

const isDataUrl = (value: string): boolean => value.startsWith('data:');

const buildRelativeUrl = (value: string): string => {
  if (!value.startsWith('/')) {
    return `${API_CONFIG.baseUrl}/${value}`;
  }
  return `${API_CONFIG.baseUrl}${value}`;
};

/**
 * Normalize avatar source returned by the API.
 * Supports CDN URLs, relative paths, and backend file IDs (file_*).
 */
export function getAvatarUrl(source?: string | null): string {
  if (!source) {
    return '';
  }

  const normalized = source.trim();

  if (!normalized) {
    return '';
  }

  if (isHttpUrl(normalized) || isDataUrl(normalized)) {
    return normalized;
  }

  if (normalized.startsWith('file_')) {
    return `${MEDIA_ENDPOINT_PREFIX}${encodeURIComponent(normalized)}`;
  }

  if (normalized.startsWith('/')) {
    return buildRelativeUrl(normalized);
  }

  if (normalized.includes('/')) {
    return buildRelativeUrl(normalized);
  }

  return '';
}
