import { requestValidated } from './api';
import { getAvatarUrl } from './avatar';
import { getLogger } from './logger';
import { SquareApiResponseSchema, type SquareContact } from './schemas';
import { isNonEmptyString } from './guards';
import { normalizeError } from './errors';

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
        stored !== null &&
        Array.isArray(stored.contacts) &&
        typeof stored.timestamp === 'number'
      ) {
        return stored;
      }
    } catch (error: unknown) {
      const err = normalizeError(error);
      this.logger.warn('Failed to read square cache', {
        errorMessage: err.message,
      });
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
    } catch (error: unknown) {
      const err = normalizeError(error);
      this.logger.warn('Failed to write square cache', {
        errorMessage: err.message,
      });
    }
  }

  clearCache(category: number | null): void {
    try {
      wx.removeStorageSync(this.getCacheKey(category));
    } catch (error: unknown) {
      const err = normalizeError(error);
      this.logger.warn('Failed to clear square cache', {
        errorMessage: err.message,
      });
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
      nickname: isNonEmptyString(contact.nickname)
        ? contact.nickname.trim()
        : undefined,
      gender:
        typeof contact.gender === 'number' ? contact.gender : null,
      avatar_url: getAvatarUrl(contact.avatar_url ?? null),
      bio: isNonEmptyString(contact.bio) ? contact.bio.trim() : undefined,
      region: isNonEmptyString(contact.region) ? contact.region.trim() : undefined,
      category:
        typeof contact.category === 'number' ? contact.category : null,
    };
  }

  private parseRefreshTimestamp(value?: string | null): number | null {
    if (!isNonEmptyString(value)) {
      return null;
    }
    const normalized = value.trim();
    const parsed = Date.parse(normalized);
    return Number.isNaN(parsed) ? null : parsed;
  }
}

const squareDiscoveryService = new SquareDiscoveryService();
export default squareDiscoveryService;
