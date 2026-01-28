import { getAvatarUrl } from './avatar';
import { isNonEmptyString } from './guards';
import { getLogger } from './logger';
import { fetchCurrentUserProfile, updateCurrentUserProfile } from './profile';
import type { UserProfile } from './schemas';

export interface ProfileViewModel extends UserProfile {
  displayAvatar: string;
  displayUsername: string;
}

const CACHE_TTL_MS = 3 * 60 * 1000;
const RETRY_DELAYS_MS = [0, 2000, 5000];

class ProfileService {
  private logger = getLogger('ProfileService');

  private cache: ProfileViewModel | null = null;
  private cacheTime: number | null = null;
  private loadPromise: Promise<ProfileViewModel> | null = null;
  private cacheVersion = 0;
  private retryTimers: number[] = [];
  private retryScheduled = false;

  getProfile(): ProfileViewModel | null {
    if (this.isCacheValid()) {
      return this.cache;
    }
    return null;
  }

  async loadProfile(forceRefresh = false): Promise<ProfileViewModel> {
    const cacheValid = this.isCacheValid();
    if (!forceRefresh && cacheValid && this.cache !== null) {
      this.logger.debug('Profile cache hit');
      if (!isNonEmptyString(this.cache.displayAvatar)) {
        this.scheduleRetry();
      }
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

        if (isNonEmptyString(viewModel.displayAvatar)) {
          this.clearRetryTimers();
        } else {
          this.scheduleRetry();
        }

        return viewModel;
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        if (errorMessage === 'PROFILE_LOAD_STALE') {
          this.logger.info('Profile load ignored due to cache reset');
          throw error;
        }
        this.logger.error('Profile load failed', { error: errorMessage });
        this.scheduleRetry();
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
    this.clearRetryTimers();
    return viewModel;
  }

  clearProfile(): void {
    this.cache = null;
    this.cacheTime = null;
    this.cacheVersion += 1;
    this.clearRetryTimers();
  }

  cancelRetries(): void {
    this.clearRetryTimers();
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

  private scheduleRetry(): void {
    if (this.retryScheduled) {
      return;
    }

    this.retryScheduled = true;
    RETRY_DELAYS_MS.forEach((delay) => {
      const timerId = setTimeout(() => {
        this.retryTimers = this.retryTimers.filter((id) => id !== timerId);
        void this.loadProfile(true).catch(() => {
          // Keep silent, retry policy handles user experience.
        });
        if (this.retryTimers.length === 0) {
          this.retryScheduled = false;
        }
      }, delay) as unknown as number;
      this.retryTimers.push(timerId);
    });
  }

  private clearRetryTimers(): void {
    this.retryTimers.forEach((timerId) => {
      clearTimeout(timerId);
    });
    this.retryTimers = [];
    this.retryScheduled = false;
  }
}

const profileService = new ProfileService();
export default profileService;
