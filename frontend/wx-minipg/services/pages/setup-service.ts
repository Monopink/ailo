import { getAvatarUrl } from '../../utils/avatar';
import { GENDER_OPTIONS, type GenderValue } from '../../utils/constants/user';
import { fetchCurrentUserProfile, updateCurrentUserProfile } from '../../utils/profile';
import { BasePageService } from './base-page-service';

export interface SetupProfileSnapshot {
  nickname: string;
  avatarUrl: string;
  gender: GenderValue | null;
  genderIndex: number;
  bio: string;
  regionDisplay: string;
}

export interface SetupSubmitPayload {
  nickname: string;
  gender: GenderValue | null;
  bio: string;
  regionDisplay: string;
  avatarFileId: string;
}

const resolveGenderIndex = (value: GenderValue | null): number => {
  if (value === null) {
    return -1;
  }
  return GENDER_OPTIONS.findIndex((option) => option.value === value);
};

const buildProfilePayload = (payload: SetupSubmitPayload): Record<string, unknown> => {
  const submitPayload: Record<string, unknown> = {
    nickname: payload.nickname,
  };

  if (payload.gender !== null) {
    submitPayload.gender = payload.gender;
  }

  const trimmedBio = payload.bio.trim();
  if (trimmedBio !== '') {
    submitPayload.bio = trimmedBio;
  }

  if (payload.regionDisplay !== '') {
    submitPayload.region = payload.regionDisplay;
  }

  if (payload.avatarFileId !== '') {
    submitPayload.avatar_file_id = payload.avatarFileId;
  }

  return submitPayload;
};

export class SetupPageService extends BasePageService {
  async loadProfile(): Promise<SetupProfileSnapshot | null> {
    const seq = this.startRequest();
    const profile = await fetchCurrentUserProfile();
    if (!this.isRequestActive(seq)) {
      return null;
    }
    const gender = typeof profile.gender === 'number' ? (profile.gender as GenderValue) : null;
    return {
      nickname: profile.nickname ?? '',
      avatarUrl: getAvatarUrl(profile.avatar_url ?? ''),
      gender,
      genderIndex: resolveGenderIndex(gender),
      bio: profile.bio ?? '',
      regionDisplay: profile.region ?? '',
    };
  }

  async submitProfile(payload: SetupSubmitPayload): Promise<{ qiao_id: string } | null> {
    const seq = this.startRequest();
    const updatedProfile = await updateCurrentUserProfile(buildProfilePayload(payload));
    if (!this.isRequestActive(seq)) {
      return null;
    }
    return {
      qiao_id: updatedProfile.qiao_id,
    };
  }
}

export const createSetupPageService = (): SetupPageService => new SetupPageService();
