import { requestValidated } from './api';
import { getAvatarUrl } from './avatar';
import { getLogger } from './logger';
import { SquareApiResponseSchema, type SquareContact } from './schemas';

export const SQUARE_CACHE_TTL_MS = 10 * 60 * 1000;
export const SQUARE_CACHE_STALE_PERIOD_MS = 60 * 60 * 1000;

export interface SquareContactViewModel {
  id: string;
  qiao_id: string;
  nickname?: string;
  gender: number | null;
  avatar_url: string;
  bio?: string;
  region?: string;
  category: number | null;
}

export interface SquareCacheEntry {
  contacts: SquareContactViewModel[];
  nextRefreshAvailableAt: number | null;
  timestamp: number;
}

export interface SquareLoadResult {
  contacts: SquareContactViewModel[];
  nextRefreshAvailableAt: number | null;
  cacheAgeMs: number | null;
  fromCache: boolean;
}

class SquareDiscoveryService {
  private logger = getLogger('SquareDiscoveryService');

  getCacheEntry(category: number | null): SquareCacheEntry | null {
    try {
      const stored = wx.getStorageSync<SquareCacheEntry | null>(
        this.getCacheKey(category)
      );
      if (
        stored &&
        Array.isArray(stored.contacts) &&
        typeof stored.timestamp === 'number'
      ) {
        return stored;
      }
    } catch (error) {
      this.logger.warn('Failed to read square cache', { error });
    }
    return null;
  }

  async load(category: number | null): Promise<SquareLoadResult> {
    const query = this.buildQueryParams(category);
    const response = await requestValidated(SquareApiResponseSchema, {
      url: `/discovery/square${query}`,
      method: 'GET',
    });
    const contacts = response.items.map((item) => this.normalizeContact(item));
    const nextRefreshAvailableAt = this.parseRefreshTimestamp(
      response.refresh_available_at
    );
    const entry: SquareCacheEntry = {
      contacts,
      nextRefreshAvailableAt,
      timestamp: Date.now(),
    };
    this.setCacheEntry(category, entry);
    this.logger.info('Square contacts fetched', {
      category,
      count: contacts.length,
    });
    return {
      contacts,
      nextRefreshAvailableAt,
      cacheAgeMs: null,
      fromCache: false,
    };
  }

  private setCacheEntry(category: number | null, entry: SquareCacheEntry): void {
    try {
      wx.setStorageSync(this.getCacheKey(category), entry);
    } catch (error) {
      this.logger.warn('Failed to write square cache', { error });
    }
  }

  clearCache(category: number | null): void {
    try {
      wx.removeStorageSync(this.getCacheKey(category));
    } catch (error) {
      this.logger.warn('Failed to clear square cache', { error });
    }
  }

  private getCacheKey(category: number | null): string {
    return `square_${category ?? 'all'}`;
  }

  private buildQueryParams(category: number | null): string {
    if (category === null) {
      return '';
    }
    return `?category=${encodeURIComponent(String(category))}`;
  }

  private normalizeContact(contact: SquareContact): SquareContactViewModel {
    return {
      id: contact.qiao_id,
      qiao_id: contact.qiao_id,
      nickname:
        typeof contact.nickname === 'string' && contact.nickname.trim()
          ? contact.nickname
          : undefined,
      gender:
        typeof contact.gender === 'number'
          ? contact.gender
          : contact.gender ?? null,
      avatar_url: getAvatarUrl(contact.avatar_url ?? null),
      bio:
        typeof contact.bio === 'string' && contact.bio.trim()
          ? contact.bio
          : undefined,
      region:
        typeof contact.region === 'string' && contact.region.trim()
          ? contact.region
          : undefined,
      category:
        typeof contact.category === 'number'
          ? contact.category
          : contact.category ?? null,
    };
  }

  private parseRefreshTimestamp(value?: string | null): number | null {
    if (!value) {
      return null;
    }
    const parsed = Date.parse(value);
    return Number.isNaN(parsed) ? null : parsed;
  }
}

const squareDiscoveryService = new SquareDiscoveryService();
export default squareDiscoveryService;
