import { STORAGE_KEYS } from './config';
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
  feedVersion: string;
  nextCursor: string | null;
  hasMore: boolean;
  nextRefreshAvailableAt: number | null;
  timestamp: number;
}

interface SquareCachePointer {
  feedVersion: string;
  timestamp: number;
}

export interface SquareCategoriesCacheEntry {
  items: SquareCategoryCard[];
  timestamp: number;
  isFallback?: boolean;
}

export interface SquareLoadParams {
  cursor?: string | null;
  feedVersion?: string | null;
  refresh?: boolean;
  pageSize?: number;
}

export interface SquareLoadResult {
  contacts: SquareContactViewModel[];
  feedVersion: string;
  nextCursor: string | null;
  hasMore: boolean;
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

  getCacheEntry(categoryKey: string, feedVersion?: string | null): SquareCacheEntry | null {
    if (!isValidCategoryKey(categoryKey)) {
      return null;
    }
    const resolvedFeedVersion = isNonEmptyString(feedVersion)
      ? feedVersion.trim()
      : this.getLatestFeedVersion(categoryKey);
    if (!isNonEmptyString(resolvedFeedVersion)) {
      return null;
    }
    try {
      const stored = wx.getStorageSync<SquareCacheEntry | null>(
        this.getContactsCacheKey(categoryKey, resolvedFeedVersion)
      );
      if (
        stored !== null &&
        Array.isArray(stored.contacts) &&
        typeof stored.timestamp === 'number' &&
        isNonEmptyString(stored.feedVersion)
      ) {
        return stored;
      }
    } catch (error: unknown) {
      const err = normalizeError(error);
      this.logger.warn('Failed to read square cache', { errorMessage: err.message });
    }
    return null;
  }

  async load(categoryKey: string, params: SquareLoadParams = {}): Promise<SquareLoadResult> {
    if (!isValidCategoryKey(categoryKey)) {
      throw new Error('无效的分类参数');
    }
    const query = this.buildSquareQuery(categoryKey, params);
    const response = await requestValidated(SquareApiResponseSchema, {
      url: `/discovery/square${query}`,
      method: 'GET',
    });
    const contacts = response.items.map((item) => this.normalizeContact(item));
    const nextRefreshAvailableAt = this.parseRefreshTimestamp(response.refresh_available_at);
    const entry: SquareCacheEntry = {
      contacts,
      feedVersion: response.feed_version,
      nextCursor: isNonEmptyString(response.next_cursor) ? response.next_cursor.trim() : null,
      hasMore: Boolean(response.has_more),
      nextRefreshAvailableAt,
      timestamp: Date.now(),
    };
    this.setCacheEntry(categoryKey, entry);
    this.logger.info('Square contacts fetched', {
      categoryKey,
      count: contacts.length,
      feedVersion: entry.feedVersion,
      hasMore: entry.hasMore,
    });
    return {
      contacts,
      feedVersion: entry.feedVersion,
      nextCursor: entry.nextCursor,
      hasMore: entry.hasMore,
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
      const latestFeedVersion = this.getLatestFeedVersion(categoryKey);
      if (isNonEmptyString(latestFeedVersion)) {
        wx.removeStorageSync(this.getContactsCacheKey(categoryKey, latestFeedVersion));
      }
      wx.removeStorageSync(this.getLatestPointerKey(categoryKey));
    } catch (error: unknown) {
      const err = normalizeError(error);
      this.logger.warn('Failed to clear square cache', {
        errorMessage: err.message,
      });
    }
  }

  private setCacheEntry(categoryKey: string, entry: SquareCacheEntry): void {
    if (!isValidCategoryKey(categoryKey) || !isNonEmptyString(entry.feedVersion)) {
      return;
    }
    try {
      wx.setStorageSync(this.getContactsCacheKey(categoryKey, entry.feedVersion), entry);
      const pointer: SquareCachePointer = {
        feedVersion: entry.feedVersion,
        timestamp: entry.timestamp,
      };
      wx.setStorageSync(this.getLatestPointerKey(categoryKey), pointer);
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

  private getLatestFeedVersion(categoryKey: string): string | null {
    try {
      const pointer = wx.getStorageSync<SquareCachePointer | null>(
        this.getLatestPointerKey(categoryKey)
      );
      if (pointer !== null && isNonEmptyString(pointer.feedVersion)) {
        return pointer.feedVersion.trim();
      }
    } catch (error: unknown) {
      const err = normalizeError(error);
      this.logger.warn('Failed to read square cache pointer', { errorMessage: err.message });
    }
    return null;
  }

  private getContactsCacheKey(categoryKey: string, feedVersion: string): string {
    return `square_${this.getCurrentUserQiaoId()}_${categoryKey}_${feedVersion}`;
  }

  private getLatestPointerKey(categoryKey: string): string {
    return `square_latest_${this.getCurrentUserQiaoId()}_${categoryKey}`;
  }

  private getCurrentUserQiaoId(): string {
    try {
      const userInfo = wx.getStorageSync<Record<string, unknown> | null>(STORAGE_KEYS.USER_INFO);
      const rawQiaoId = userInfo?.qiao_id;
      if (typeof rawQiaoId === 'string' && rawQiaoId.trim().length > 0) {
        return rawQiaoId.trim();
      }
    } catch (error: unknown) {
      const err = normalizeError(error);
      this.logger.warn('Failed to resolve current user qiao_id', { errorMessage: err.message });
    }
    return 'anonymous';
  }

  private buildSquareQuery(categoryKey: string, params: SquareLoadParams): string {
    const queryParts = [`category_key=${encodeURIComponent(categoryKey)}`];

    if (isNonEmptyString(params.cursor)) {
      queryParts.push(`cursor=${encodeURIComponent(params.cursor.trim())}`);
    }
    if (isNonEmptyString(params.feedVersion)) {
      queryParts.push(`feed_version=${encodeURIComponent(params.feedVersion.trim())}`);
    }
    if (params.refresh === true) {
      queryParts.push('refresh=true');
    }
    if (
      typeof params.pageSize === 'number' &&
      Number.isFinite(params.pageSize) &&
      params.pageSize > 0
    ) {
      queryParts.push(`page_size=${Math.floor(params.pageSize)}`);
    }

    return `?${queryParts.join('&')}`;
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
