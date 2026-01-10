/**
 * User-related constants and enums
 *
 * IMPORTANT: All enum values MUST match backend definitions
 */

/** Gender enum - MUST match backend (1=male, 2=female, 3=other) */
export const GENDER = {
  MALE: 1,
  FEMALE: 2,
  OTHER: 3,
} as const;

export type GenderValue = (typeof GENDER)[keyof typeof GENDER];

/** Gender display options for UI pickers */
export const GENDER_OPTIONS = [
  { value: GENDER.MALE, label: '男' },
  { value: GENDER.FEMALE, label: '女' },
  { value: GENDER.OTHER, label: '其他' },
] as const;

export type GenderOption = (typeof GENDER_OPTIONS)[number];

/** User type enum - MUST match backend */
export const USER_TYPE = {
  NORMAL: 1,
  OFFICIAL: 2,
  VIRTUAL: 3,
} as const;

export type UserType = (typeof USER_TYPE)[keyof typeof USER_TYPE];

/** User status enum - MUST match backend */
export const USER_STATUS = {
  ACTIVE: 1,
  INACTIVE: 2,
  SUSPENDED: 3,
} as const;

export type UserStatus = (typeof USER_STATUS)[keyof typeof USER_STATUS];
