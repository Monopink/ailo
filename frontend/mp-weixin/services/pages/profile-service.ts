import { classifyError } from '../../utils/error-classifier';
import { type ProfileViewModel } from '../../utils/profile-service';
import profileService from '../../utils/profile-service';
import { BasePageService } from './base-page-service';
import { createReadyScreenModel, type ScreenModel } from './page-state';

export interface ProfileBootstrapResult {
  screenModel: ScreenModel;
  profile: ProfileViewModel | null;
}

export interface ProfileLoadResult extends ProfileBootstrapResult {
  authInvalid: boolean;
}

export class ProfilePageService extends BasePageService {
  bootstrap(): ProfileBootstrapResult {
    const profile = profileService.getProfile();
    return {
      screenModel: createReadyScreenModel({
        contentVariant: 'data',
        refreshState: 'idle',
      }),
      profile,
    };
  }

  async load(currentProfile: ProfileViewModel | null): Promise<ProfileLoadResult | null> {
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
        authInvalid: false,
      };
    } catch (error: unknown) {
      const semantics = classifyError(error);
      if (!this.isRequestActive(seq)) {
        return null;
      }
      return {
        screenModel: createReadyScreenModel({
          contentVariant: 'data',
          refreshState: 'degraded',
        }),
        profile: currentProfile,
        authInvalid: semantics.reason === 'auth-invalid',
      };
    }
  }
}

export const createProfilePageService = (): ProfilePageService => new ProfilePageService();
