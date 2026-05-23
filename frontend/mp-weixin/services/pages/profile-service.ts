import { classifyError } from '../../utils/error-classifier';
import inviteBindingService, { type InviteBindingState } from '../../utils/invite-binding-service';
import { type ProfileViewModel } from '../../utils/profile-service';
import profileService from '../../utils/profile-service';
import { BasePageService } from './base-page-service';
import { createReadyScreenModel, type ScreenModel } from './page-state';

export interface ProfileBootstrapResult {
  screenModel: ScreenModel;
  profile: ProfileViewModel | null;
  inviteBindingState: InviteBindingState;
}

export interface ProfileLoadResult extends ProfileBootstrapResult {
  authInvalid: boolean;
}

export class ProfilePageService extends BasePageService {
  bootstrap(): ProfileBootstrapResult {
    const profile = profileService.getProfile({ allowStale: true });
    return {
      screenModel: createReadyScreenModel({
        contentVariant: 'data',
        refreshState: 'idle',
      }),
      profile,
      inviteBindingState: inviteBindingService.getState(),
    };
  }

  async load(
    currentProfile: ProfileViewModel | null,
    currentInviteBindingState: InviteBindingState,
    options: { forceRefreshBinding?: boolean } = {}
  ): Promise<ProfileLoadResult | null> {
    const seq = this.startRequest();
    const { forceRefreshBinding = false } = options;
    try {
      const [profile, inviteBindingState] = await Promise.all([
        profileService.loadProfile(),
        inviteBindingService.load({ forceRefresh: forceRefreshBinding }),
      ]);
      if (!this.isRequestActive(seq)) {
        return null;
      }
      return {
        screenModel: createReadyScreenModel({
          contentVariant: 'data',
          refreshState: 'idle',
        }),
        profile,
        inviteBindingState,
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
        inviteBindingState: currentInviteBindingState,
        authInvalid: semantics.reason === 'auth-invalid',
      };
    }
  }
}

export const createProfilePageService = (): ProfilePageService => new ProfilePageService();
