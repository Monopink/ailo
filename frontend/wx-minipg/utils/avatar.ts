const DEFAULT_AVATAR = '/assets/avatars/default.png';

/**
 * Normalize avatar URL returned by the API.
 * Only supports CDN URLs or packaged static assets.
 */
export function getAvatarUrl(avatarUrl?: string | null): string {
  if (!avatarUrl) {
    return DEFAULT_AVATAR;
  }

  const normalized = avatarUrl.trim();
  if (!normalized) {
    return DEFAULT_AVATAR;
  }

  if (normalized.startsWith('http://') || normalized.startsWith('https://')) {
    return normalized;
  }

  if (normalized.startsWith('/assets/avatars/')) {
    return normalized;
  }

  return DEFAULT_AVATAR;
}
