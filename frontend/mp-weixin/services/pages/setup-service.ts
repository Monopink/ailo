import { getAvatarUrl } from '../../utils/avatar';
import { GENDER_OPTIONS, type GenderValue } from '../../utils/constants/user';
import { requestValidated } from '../../utils/api';
import { fetchCurrentUserProfile, updateCurrentUserProfile } from '../../utils/profile';
import {
  GrowthAttributionTrackResponseSchema,
  InvitationBindResponse,
  InvitationBindResponseSchema,
  InvitationIntakeResponse,
  InvitationIntakeResponseSchema,
} from '../../utils/schemas';
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
  regionCnCityCode: string | null;
  regionProvinceName: string | null;
  regionCityName: string | null;
  regionChanged: boolean;
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

  if (payload.regionChanged) {
    if (
      payload.regionCnCityCode !== null &&
      payload.regionProvinceName !== null &&
      payload.regionCityName !== null
    ) {
      submitPayload.region_country_code = 'CN';
      submitPayload.region_cn_city_code = payload.regionCnCityCode;
      submitPayload.region_province_name = payload.regionProvinceName;
      submitPayload.region_city_name = payload.regionCityName;
    } else {
      submitPayload.region_country_code = null;
      submitPayload.region_cn_city_code = null;
      submitPayload.region_province_name = null;
      submitPayload.region_city_name = null;
    }
  }

  if (payload.avatarFileId !== '') {
    submitPayload.avatar_file_id = payload.avatarFileId;
  }

  return submitPayload;
};

const INVITATIONS_BIND_ENDPOINT = '/invitations/bind';
const INVITATIONS_INTAKE_ENDPOINT = '/invitations/intake';
const GROWTH_ATTRIBUTION_ENDPOINT = '/growth/attributions/track';

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

  async bindInviteCode(
    code: string,
    source: 'setup' | 'link' | 'invite_bind_page' | 'invite_share_page' = 'setup'
  ): Promise<InvitationBindResponse | null> {
    const seq = this.startRequest();
    const response = await requestValidated(InvitationBindResponseSchema, {
      url: INVITATIONS_BIND_ENDPOINT,
      method: 'POST',
      data: { code, source },
    });
    if (!this.isRequestActive(seq)) {
      return null;
    }
    return response;
  }

  async intakeInviteCode(options: {
    source: 'setup' | 'link' | 'invite_bind_page' | 'invite_share_page';
    trigger: 'clipboard' | 'link_param' | 'manual_input';
    rawText?: string;
    inviteCode?: string;
  }): Promise<InvitationIntakeResponse | null> {
    const seq = this.startRequest();
    const response = await requestValidated(InvitationIntakeResponseSchema, {
      url: INVITATIONS_INTAKE_ENDPOINT,
      method: 'POST',
      data: {
        source: options.source,
        trigger: options.trigger,
        raw_text: options.rawText,
        invite_code: options.inviteCode,
      },
    });
    if (!this.isRequestActive(seq)) {
      return null;
    }
    return response;
  }

  async trackGrowthAttribution(options: {
    campaignCode: string;
    source: string;
    payload?: Record<string, unknown>;
  }): Promise<boolean> {
    const seq = this.startRequest();
    const response = await requestValidated(GrowthAttributionTrackResponseSchema, {
      url: GROWTH_ATTRIBUTION_ENDPOINT,
      method: 'POST',
      data: {
        campaign_code: options.campaignCode,
        source: options.source,
        payload: options.payload,
      },
    });
    if (!this.isRequestActive(seq)) {
      return false;
    }
    return response.accepted;
  }
}

export const createSetupPageService = (): SetupPageService => new SetupPageService();
