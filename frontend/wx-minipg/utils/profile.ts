import { get, patch } from './api';

export interface UserProfileResponse {
  qiao_id: string;
  username?: string | null;
  nickname?: string | null;
  avatar_url?: string | null;
  gender?: number | null;
  bio?: string | null;
  region?: string | null;
}

export interface AccountInfoResponse {
  phone?: string;
  email?: string | null;
}

const PROFILE_ENDPOINT = '/users/me';
const ACCOUNT_ENDPOINT = '/users/account';

export async function fetchCurrentUserProfile(): Promise<UserProfileResponse> {
  return await get<UserProfileResponse>(PROFILE_ENDPOINT);
}

export async function fetchAccountInfo(): Promise<AccountInfoResponse> {
  return await get<AccountInfoResponse>(ACCOUNT_ENDPOINT);
}

export async function updateCurrentUserProfile(
  payload: Record<string, unknown>
): Promise<UserProfileResponse> {
  return await patch<UserProfileResponse, typeof payload>(PROFILE_ENDPOINT, payload);
}
