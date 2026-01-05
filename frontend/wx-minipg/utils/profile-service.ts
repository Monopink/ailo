import { getAvatarUrl } from './avatar';
import { getLogger } from './logger';
import { fetchCurrentUserProfile, updateCurrentUserProfile } from './profile';
import type { UserProfile } from './schemas';

export interface ProfileViewModel extends UserProfile {
  displayAvatar: string;
  displayUsername: string;
}

class ProfileService {
  private logger = getLogger('ProfileService');
  private currentProfile: ProfileViewModel | null = null;
  private loadingPromise: Promise<ProfileViewModel> | null = null;

  async loadProfile(forceRefresh = false): Promise<ProfileViewModel> {
    if (!forceRefresh && this.currentProfile) {
      return this.currentProfile;
    }
    if (!forceRefresh && this.loadingPromise) {
      return this.loadingPromise;
    }

    const promise = (async () => {
      this.logger.debug('Fetching profile', { forceRefresh });
      const profile = await fetchCurrentUserProfile();
      const viewModel = this.buildViewModel(profile);
      this.currentProfile = viewModel;
      return viewModel;
    })();

    this.loadingPromise = promise;

    try {
      return await promise;
    } finally {
      if (this.loadingPromise === promise) {
        this.loadingPromise = null;
      }
    }
  }

  async updateProfile(payload: Record<string, unknown>): Promise<ProfileViewModel> {
    this.logger.info('Updating profile', { fields: Object.keys(payload) });
    const profile = await updateCurrentUserProfile(payload);
    const viewModel = this.buildViewModel(profile);
    this.currentProfile = viewModel;
    return viewModel;
  }

  getCachedProfile(): ProfileViewModel | null {
    return this.currentProfile;
  }

  private buildViewModel(profile: UserProfile): ProfileViewModel {
    const displayUsername = profile.username || profile.nickname || '--';
    return {
      ...profile,
      displayAvatar: getAvatarUrl(profile.avatar_url ?? null),
      displayUsername,
    };
  }
}

const profileService = new ProfileService();
export default profileService;
