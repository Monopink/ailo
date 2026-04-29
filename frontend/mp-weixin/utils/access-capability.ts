import { ACCOUNT_SEGMENT, type AccountSegment } from './constants/user';
import type { StoredAuthUser } from './storage';

const normalizeAccountSegment = (value: unknown): AccountSegment => {
  if (value === ACCOUNT_SEGMENT.MEMBER_FULL || value === ACCOUNT_SEGMENT.MEMBER_LIMITED) {
    return value;
  }
  return ACCOUNT_SEGMENT.MEMBER_FULL;
};

export const resolveAccountSegment = (user: StoredAuthUser | null | undefined): AccountSegment => {
  return normalizeAccountSegment(user?.account_segment);
};

export const canUseInviteCapability = (user: StoredAuthUser | null | undefined): boolean => {
  return resolveAccountSegment(user) === ACCOUNT_SEGMENT.MEMBER_FULL;
};
