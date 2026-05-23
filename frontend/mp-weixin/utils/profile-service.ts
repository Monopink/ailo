import { getAvatarUrl } from './avatar';
import { getLogger } from './logger';
import {
  checkUsernameAvailability as checkUsernameAvailabilityRequest,
  fetchCurrentUserProfile,
  updateCurrentUserProfile,
} from './profile';
import type { UserProfile } from './schemas-core';

export interface ProfileViewModel extends UserProfile {
  displayAvatar: string;
  displayUsername: string;
}

const CACHE_TTL_MS = 3 * 60 * 1000;

class ProfileService {
  private logger = getLogger('ProfileService');

  private cache: ProfileViewModel | null = null;
  private cacheTime: number | null = null;
  private loadPromise: Promise<ProfileViewModel> | null = null;
  private cacheVersion = 0;

  getProfile(options: { allowStale?: boolean } = {}): ProfileViewModel | null {
    if (this.cache === null) {
      return null;
    }
    if (options.allowStale === true || this.isCacheValid()) {
      return this.cache;
    }
    return null;
  }

  async loadProfile(forceRefresh = false): Promise<ProfileViewModel> {
    const cacheValid = this.isCacheValid();
    if (!forceRefresh && cacheValid && this.cache !== null) {
      this.logger.debug('Profile cache hit');
      return this.cache;
    }

    if (!forceRefresh && !cacheValid) {
      this.logger.debug('Profile cache miss');
    }

    if (this.loadPromise !== null) {
      this.logger.debug('Profile load in-flight');
      return this.loadPromise;
    }

    const loadVersion = this.cacheVersion;
    this.logger.debug(forceRefresh ? 'Force refresh profile' : 'Fetching profile');

    this.loadPromise = (async () => {
      try {
        const profile = await fetchCurrentUserProfile();
        if (loadVersion !== this.cacheVersion) {
          throw new Error('PROFILE_LOAD_STALE');
        }

        const viewModel = this.buildViewModel(profile);
        this.cache = viewModel;
        this.cacheTime = Date.now();
        return viewModel;
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        if (errorMessage === 'PROFILE_LOAD_STALE') {
          this.logger.info('Profile load ignored due to cache reset');
          throw error;
        }
        this.logger.error('Profile load failed', { error: errorMessage });
        throw error;
      } finally {
        this.loadPromise = null;
      }
    })();

    return this.loadPromise;
  }

  async updateProfile(payload: Record<string, unknown>): Promise<ProfileViewModel> {
    this.logger.info('Updating profile', { fields: Object.keys(payload) });
    const profile = await updateCurrentUserProfile(payload);
    const viewModel = this.buildViewModel(profile);
    this.cache = viewModel;
    this.cacheTime = Date.now();
    return viewModel;
  }

  async checkUsernameAvailability(username: string): Promise<void> {
    this.logger.info('Checking username availability');
    await checkUsernameAvailabilityRequest(username);
  }

  clearProfile(): void {
    this.cache = null;
    this.cacheTime = null;
    this.cacheVersion += 1;
  }

  private buildViewModel(profile: UserProfile): ProfileViewModel {
    const displayUsername = profile.username ?? '';
    return {
      ...profile,
      displayAvatar: getAvatarUrl(profile.avatar_url ?? null),
      displayUsername,
    };
  }

  private isCacheValid(): boolean {
    if (this.cache === null || this.cacheTime === null) {
      return false;
    }
    return Date.now() - this.cacheTime < CACHE_TTL_MS;
  }
}

const profileService = new ProfileService();
export default profileService;
