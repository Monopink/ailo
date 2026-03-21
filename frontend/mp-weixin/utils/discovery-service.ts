import { requestValidated } from './api';
import { getAvatarUrl } from './avatar';
import {
  buildSquareCategoryCards,
  getFallbackSquareCategoryCards,
  isValidCategoryKey,
  type SquareCategoryCard,
} from './constants/square';
import { normalizeError } from './errors';
import { isNonEmptyString } from './guards';
import { getLogger } from './logger';
import {
  SquareApiResponseSchema,
  SquareCategoriesResponseSchema,
  type SquareContact,
} from './schemas';

export const SQUARE_CACHE_TTL_MS = 10 * 60 * 1000;
export const SQUARE_CACHE_STALE_PERIOD_MS = 60 * 60 * 1000;
export const SQUARE_CATEGORIES_CACHE_KEY = 'square_categories_v1';
export const SQUARE_CATEGORIES_CACHE_TTL_MS = 10 * 60 * 1000;
export const SQUARE_CATEGORIES_CACHE_STALE_PERIOD_MS = 6 * 60 * 60 * 1000;

export interface SquareContactViewModel {
  id: string;
  qiao_id: string;
  typeId: number;
  nickname?: string;
  gender: number | null;
  avatar_url: string;
  tags: string[];
  remark: string | null;
  bio?: string;
  region?: string;
  categoryKey: string;
}

export interface SquareCacheEntry {
  contacts: SquareContactViewModel[];
  nextRefreshAvailableAt: number | null;
  timestamp: number;
}

export interface SquareCategoriesCacheEntry {
  items: SquareCategoryCard[];
  timestamp: number;
  isFallback?: boolean;
}

export interface SquareLoadResult {
  contacts: SquareContactViewModel[];
  nextRefreshAvailableAt: number | null;
  cacheAgeMs: number | null;
  fromCache: boolean;
}

export interface SquareCategoriesLoadResult {
  items: SquareCategoryCard[];
  fromCache: boolean;
  cacheAgeMs: number | null;
  isFallback: boolean;
}

class SquareDiscoveryService {
  private logger = getLogger('SquareDiscoveryService');

  getCacheEntry(categoryKey: string): SquareCacheEntry | null {
    if (!isValidCategoryKey(categoryKey)) {
      return null;
    }
    try {
      const stored = wx.getStorageSync<SquareCacheEntry | null>(
        this.getContactsCacheKey(categoryKey)
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
      this.logger.warn('Failed to read square cache', { errorMessage: err.message });
    }
    return null;
  }

  async load(categoryKey: string): Promise<SquareLoadResult> {
    if (!isValidCategoryKey(categoryKey)) {
      throw new Error('无效的分类参数');
    }
    const query = this.buildSquareQuery(categoryKey);
    const response = await requestValidated(SquareApiResponseSchema, {
      url: `/discovery/square${query}`,
      method: 'GET',
    });
    const contacts = response.items.map((item) => this.normalizeContact(item));
    const nextRefreshAvailableAt = this.parseRefreshTimestamp(response.refresh_available_at);
    const entry: SquareCacheEntry = {
      contacts,
      nextRefreshAvailableAt,
      timestamp: Date.now(),
    };
    this.setCacheEntry(categoryKey, entry);
    this.logger.info('Square contacts fetched', {
      categoryKey,
      count: contacts.length,
      total: response.pagination.total,
    });
    return {
      contacts,
      nextRefreshAvailableAt,
      cacheAgeMs: null,
      fromCache: false,
    };
  }

  getCategoriesCacheEntry(): SquareCategoriesCacheEntry | null {
    try {
      const stored = wx.getStorageSync<SquareCategoriesCacheEntry | null>(
        SQUARE_CATEGORIES_CACHE_KEY
      );
      if (stored !== null && Array.isArray(stored.items) && typeof stored.timestamp === 'number') {
        return stored;
      }
    } catch (error: unknown) {
      const err = normalizeError(error);
      this.logger.warn('Failed to read square categories cache', {
        errorMessage: err.message,
      });
    }
    return null;
  }

  async loadCategories(): Promise<SquareCategoriesLoadResult> {
    const response = await requestValidated(SquareCategoriesResponseSchema, {
      url: '/discovery/square-categories',
      method: 'GET',
    });
    const cards = buildSquareCategoryCards(response.items);
    const isFallback = cards.length === 0;
    const items = isFallback ? getFallbackSquareCategoryCards() : cards;
    const entry: SquareCategoriesCacheEntry = {
      items,
      timestamp: Date.now(),
      isFallback,
    };
    this.setCategoriesCacheEntry(entry);
    this.logger.info('Square categories fetched', { count: items.length, isFallback });
    return {
      items,
      fromCache: false,
      cacheAgeMs: null,
      isFallback,
    };
  }

  getFallbackCategories(): SquareCategoryCard[] {
    return getFallbackSquareCategoryCards();
  }

  clearCache(categoryKey: string): void {
    if (!isValidCategoryKey(categoryKey)) {
      return;
    }
    try {
      wx.removeStorageSync(this.getContactsCacheKey(categoryKey));
    } catch (error: unknown) {
      const err = normalizeError(error);
      this.logger.warn('Failed to clear square cache', {
        errorMessage: err.message,
      });
    }
  }

  private setCacheEntry(categoryKey: string, entry: SquareCacheEntry): void {
    if (!isValidCategoryKey(categoryKey)) {
      return;
    }
    try {
      wx.setStorageSync(this.getContactsCacheKey(categoryKey), entry);
    } catch (error: unknown) {
      const err = normalizeError(error);
      this.logger.warn('Failed to write square cache', { errorMessage: err.message });
    }
  }

  private setCategoriesCacheEntry(entry: SquareCategoriesCacheEntry): void {
    try {
      wx.setStorageSync(SQUARE_CATEGORIES_CACHE_KEY, entry);
    } catch (error: unknown) {
      const err = normalizeError(error);
      this.logger.warn('Failed to write square categories cache', {
        errorMessage: err.message,
      });
    }
  }

  private getContactsCacheKey(categoryKey: string): string {
    return `square_${categoryKey}`;
  }

  private buildSquareQuery(categoryKey: string): string {
    return `?category_key=${encodeURIComponent(categoryKey)}`;
  }

  private normalizeContact(contact: SquareContact): SquareContactViewModel {
    return {
      id: contact.qiao_id,
      qiao_id: contact.qiao_id,
      typeId: contact.type_id,
      categoryKey: contact.category_key,
      nickname: isNonEmptyString(contact.nickname) ? contact.nickname.trim() : undefined,
      gender: typeof contact.gender === 'number' ? contact.gender : null,
      avatar_url: getAvatarUrl(contact.avatar_url ?? null),
      tags: Array.isArray(contact.tags)
        ? contact.tags
            .filter((tag): tag is string => typeof tag === 'string' && tag.trim().length > 0)
            .map((tag) => tag.trim())
        : [],
      remark: isNonEmptyString(contact.remark) ? contact.remark.trim() : null,
      bio: isNonEmptyString(contact.bio) ? contact.bio.trim() : undefined,
      region: isNonEmptyString(contact.region) ? contact.region.trim() : undefined,
    };
  }

  private parseRefreshTimestamp(value?: string | null): number | null {
    if (!isNonEmptyString(value)) {
      return null;
    }
    const parsed = Date.parse(value.trim());
    return Number.isNaN(parsed) ? null : parsed;
  }
}

const squareDiscoveryService = new SquareDiscoveryService();
export default squareDiscoveryService;
