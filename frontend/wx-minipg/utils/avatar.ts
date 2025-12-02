/**
 * Avatar utility functions
 * Handles avatar URL conversion and format detection
 */

/**
 * Get avatar URL from various formats
 * Supports:
 * - assets:// protocol (preset avatars)
 * - https:// protocol (remote avatars)
 * - null/undefined (default avatar)
 *
 * @param {string} avatarUrl - Avatar URL from API
 * @returns {string} - Local or remote avatar URL
 */
export function getAvatarUrl(avatarUrl?: string | null): string {
  // No avatar: use default
  if (!avatarUrl) {
    return '/assets/avatars/default.png';
  }

  // Preset avatar: assets://xxxx
  if (avatarUrl.startsWith('assets://')) {
    const assetId = avatarUrl.replace('assets://', '');

    // Try to detect file format
    // Since we don't know the exact format, we'll try common formats
    // WeChat miniprogram will handle the file loading
    // Priority: jpg > png > webp
    // For now, we'll use a simple approach: try jpg first
    // If the file doesn't exist, WeChat will show broken image
    // In production, we should have a consistent format or store format info

    // For MVP: assume jpg format for preset avatars (1574, 2454, 3758)
    // and png for default avatar
    return `/assets/avatars/${assetId}.jpg`;
  }

  // Remote avatar: https://... or http://...
  if (avatarUrl.startsWith('https://') || avatarUrl.startsWith('http://')) {
    return avatarUrl;
  }

  // Unknown format: use default
  return '/assets/avatars/default.png';
}
