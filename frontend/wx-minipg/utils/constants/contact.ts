/**
 * Contact-related constants and enums.
 *
 * IMPORTANT: All enum values MUST match backend definitions.
 */

/** Contact avatar display mode - MUST match backend (1=original, 2=custom remark avatar). */
export const CONTACT_AVATAR_DISPLAY_MODE = {
  ORIGINAL: 1,
  CUSTOM: 2,
} as const;

export type ContactAvatarDisplayMode =
  (typeof CONTACT_AVATAR_DISPLAY_MODE)[keyof typeof CONTACT_AVATAR_DISPLAY_MODE];
