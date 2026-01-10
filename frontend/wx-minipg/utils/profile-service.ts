import { getAvatarUrl } from './avatar';
import { getLogger } from './logger';
import { fetchCurrentUserProfile, updateCurrentUserProfile } from './profile';
import type { UserProfile } from './schemas';
import { isNonEmptyString } from './guards';

export interface ProfileViewModel extends UserProfile {
  displayAvatar: string;
  displayUsername: string;
}

class ProfileService {
  private logger = getLogger('ProfileService');

  async loadProfile(): Promise<ProfileViewModel> {
    this.logger.debug('Fetching profile');
    const profile = await fetchCurrentUserProfile();
    return this.buildViewModel(profile);
  }

  async updateProfile(payload: Record<string, unknown>): Promise<ProfileViewModel> {
    this.logger.info('Updating profile', { fields: Object.keys(payload) });
    const profile = await updateCurrentUserProfile(payload);
    return this.buildViewModel(profile);
  }

  private buildViewModel(profile: UserProfile): ProfileViewModel {
    const displayUsername = isNonEmptyString(profile.username)
      ? profile.username
      : isNonEmptyString(profile.nickname)
      ? profile.nickname
      : '--';
    return {
      ...profile,
      displayAvatar: getAvatarUrl(profile.avatar_url ?? null),
      displayUsername,
    };
  }
}

const profileService = new ProfileService();
export default profileService;
