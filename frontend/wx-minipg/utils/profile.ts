import { requestValidated } from './api';
import { AccountInfo, AccountInfoSchema, UserProfile, UserProfileSchema } from './schemas';

export type UserProfileResponse = UserProfile;
export type AccountInfoResponse = AccountInfo;

const PROFILE_ENDPOINT = '/user/profile';
const ACCOUNT_ENDPOINT = '/user/account';

export async function fetchCurrentUserProfile(): Promise<UserProfileResponse> {
  return await requestValidated(UserProfileSchema, {
    url: PROFILE_ENDPOINT,
    method: 'GET',
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

export async function updateUserAvatar(fileId: string): Promise<UserProfileResponse> {
  return await updateCurrentUserProfile({ avatar_file_id: fileId });
}
