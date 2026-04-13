import { classifyError } from '../../../utils/error-classifier';
import profileService, { type ProfileViewModel } from '../../../utils/profile-service';
import { BasePageService } from './base-page-service';
import { createReadyScreenModel, type ScreenModel } from './page-state';

const normalizeGenderText = (gender?: number | null): string => {
  switch (gender) {
    case 1:
      return '男';
    case 2:
      return '女';
    case 3:
      return '其他';
    default:
      return '';
  }
};

export interface ProfileDetailBootstrapResult {
  screenModel: ScreenModel;
  profile: ProfileViewModel | null;
  genderText: string;
}

export interface ProfileDetailLoadResult extends ProfileDetailBootstrapResult {
  authInvalid: boolean;
}

export interface ProfileDetailUpdateResult {
  profile: ProfileViewModel | null;
  genderText: string;
  authInvalid: boolean;
}

export class ProfileDetailPageService extends BasePageService {
  bootstrap(): ProfileDetailBootstrapResult {
    const profile = profileService.getProfile();
    return {
      screenModel: createReadyScreenModel({
        contentVariant: profile === null ? 'blank' : 'data',
        refreshState: 'idle',
      }),
      profile,
      genderText: normalizeGenderText(profile?.gender),
    };
  }

  async load(currentProfile: ProfileViewModel | null): Promise<ProfileDetailLoadResult | null> {
    const seq = this.startRequest();
    try {
      const profile = await profileService.loadProfile();
      if (!this.isRequestActive(seq)) {
        return null;
      }
      return {
        screenModel: createReadyScreenModel({
          contentVariant: 'data',
          refreshState: 'idle',
        }),
        profile,
        genderText: normalizeGenderText(profile.gender),
        authInvalid: false,
      };
    } catch (error: unknown) {
      const semantics = classifyError(error);
      if (!this.isRequestActive(seq)) {
        return null;
      }
      return {
        screenModel: createReadyScreenModel({
          contentVariant: currentProfile === null ? 'blank' : 'data',
          refreshState: 'degraded',
        }),
        profile: currentProfile,
        genderText: normalizeGenderText(currentProfile?.gender),
        authInvalid: semantics.reason === 'auth-invalid',
      };
    }
  }

  async updateProfile(
    updateData: Record<string, unknown>,
    currentProfile: ProfileViewModel | null
  ): Promise<ProfileDetailUpdateResult | null> {
    const seq = this.startRequest();
    try {
      const profile = await profileService.updateProfile(updateData);
      if (!this.isRequestActive(seq)) {
        return null;
      }
      return {
        profile,
        genderText: normalizeGenderText(profile.gender),
        authInvalid: false,
      };
    } catch (error: unknown) {
      const semantics = classifyError(error);
      if (!this.isRequestActive(seq)) {
        return null;
      }
      if (semantics.reason === 'auth-invalid') {
        return {
          profile: currentProfile,
          genderText: normalizeGenderText(currentProfile?.gender),
          authInvalid: true,
        };
      }
      throw error;
    }
  }
}

export const createProfileDetailPageService = (): ProfileDetailPageService =>
  new ProfileDetailPageService();
