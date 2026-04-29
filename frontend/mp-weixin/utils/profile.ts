import { requestValidated } from './api';
import type { AccountInfo, UserProfile, UsernameCheckResponse } from './schemas-core';
import {
  AccountInfoSchema,
  UserProfileSchema,
  UsernameCheckResponseSchema,
} from './schemas-validation';

export type UserProfileResponse = UserProfile;
export type AccountInfoResponse = AccountInfo;
export type UsernameAvailabilityResponse = UsernameCheckResponse;
type ProfileRequestOptions = { timeoutMs?: number };

const PROFILE_ENDPOINT = '/user/profile';
const ACCOUNT_ENDPOINT = '/user/account';
const USERNAME_CHECK_ENDPOINT = '/user/username/check';

export async function fetchCurrentUserProfile(
  options: ProfileRequestOptions = {}
): Promise<UserProfileResponse> {
  return await requestValidated(UserProfileSchema, {
    url: PROFILE_ENDPOINT,
    method: 'GET',
    timeoutMs: options.timeoutMs,
  });
}

export async function fetchAccountInfo(): Promise<AccountInfoResponse> {
  return await requestValidated(AccountInfoSchema, {
    url: ACCOUNT_ENDPOINT,
    method: 'GET',
  });
}

export async function updateCurrentUserProfile(
  payload: Record<string, unknown>
): Promise<UserProfileResponse> {
  return await requestValidated(UserProfileSchema, {
    url: PROFILE_ENDPOINT,
    method: 'PUT',
    data: payload,
  });
}

export async function checkUsernameAvailability(
  username: string
): Promise<UsernameAvailabilityResponse> {
  const query = encodeURIComponent(username);
  return await requestValidated(UsernameCheckResponseSchema, {
    url: `${USERNAME_CHECK_ENDPOINT}?username=${query}`,
    method: 'GET',
  });
}

export async function updateUserAvatar(fileId: string): Promise<UserProfileResponse> {
  return await updateCurrentUserProfile({ avatar_file_id: fileId });
}
