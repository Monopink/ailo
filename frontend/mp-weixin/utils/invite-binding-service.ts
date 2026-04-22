import { getLogger } from './logger';
import { fetchInvitationBindingStatus } from './invitation';

export type InviteBindingState = 'bound' | 'unbound' | 'unknown';

const CACHE_TTL_MS = 3 * 60 * 1000;

class InviteBindingService {
  private logger = getLogger('InviteBindingService');
  private state: InviteBindingState = 'unknown';
  private cacheTime: number | null = null;
  private loadPromise: Promise<InviteBindingState> | null = null;
  private dirty = false;

  getState(): InviteBindingState {
    return this.state;
  }

  markDirty(): void {
    this.dirty = true;
  }

  markBound(): void {
    this.state = 'bound';
    this.cacheTime = Date.now();
    this.dirty = false;
  }

  clear(): void {
    this.state = 'unknown';
    this.cacheTime = null;
    this.dirty = false;
    this.loadPromise = null;
  }

  async load(options: { forceRefresh?: boolean } = {}): Promise<InviteBindingState> {
    const { forceRefresh = false } = options;
    const shouldUseCache = !forceRefresh && !this.dirty && this.isCacheValid();
    if (shouldUseCache) {
      return this.state;
    }

    if (this.loadPromise !== null) {
      return await this.loadPromise;
    }

    this.loadPromise = (async () => {
      try {
        const result = await fetchInvitationBindingStatus();
        this.state = result.is_bound ? 'bound' : 'unbound';
        this.cacheTime = Date.now();
        this.dirty = false;
        return this.state;
      } catch (error: unknown) {
        this.logger.warn('Load invite binding status failed', { error });
        if (this.state !== 'bound' && this.state !== 'unbound') {
          this.state = 'unknown';
        }
        return this.state;
      } finally {
        this.loadPromise = null;
      }
    })();

    return await this.loadPromise;
  }

  private isCacheValid(): boolean {
    if (this.cacheTime === null) {
      return false;
    }
    return Date.now() - this.cacheTime < CACHE_TTL_MS;
  }
}

const inviteBindingService = new InviteBindingService();
export default inviteBindingService;
