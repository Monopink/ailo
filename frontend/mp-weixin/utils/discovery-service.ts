import { requestValidated } from './api';
import { getAvatarUrl } from './avatar';
import {
  buildSquareCategoryCards,
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

export interface SquareCategoriesCacheEntry {
  items: SquareCategoryCard[];
  timestamp: number;
  isFallback?: boolean;
}

export interface SquareLoadParams {
  cursor?: string | null;
  pageSize?: number;
}

export interface SquareLoadResult {
  contacts: SquareContactViewModel[];
  nextCursor: string | null;
  hasMore: boolean;
  currentPageIndex: number;
  maxPagesPerFeed: number;
  endReason: 'no_more_data' | 'page_limit_reached' | null;
  canRefreshNow: boolean;
  refreshRemainingSeconds: number;
  nextRefreshAvailableAt: number;
  refreshIntervalSeconds: number;
}

export interface SquareCategoriesLoadResult {
  items: SquareCategoryCard[];
  fromCache: boolean;
  cacheAgeMs: number | null;
  isFallback: boolean;
}

class SquareDiscoveryService {
  private logger = getLogger('SquareDiscoveryService');

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
    const nextRefreshAvailableAt = this.parseRequiredRefreshTimestamp(
      response.next_refresh_available_at
    );

    this.logger.info('Square contacts fetched', {
      categoryKey,
      count: contacts.length,
      currentPageIndex: response.current_page_index,
      maxPagesPerFeed: response.max_pages_per_feed,
      hasMore: response.has_more,
      endReason: response.end_reason,
    });

    return {
      contacts,
      nextCursor: isNonEmptyString(response.next_cursor) ? response.next_cursor.trim() : null,
      hasMore: Boolean(response.has_more),
      currentPageIndex: response.current_page_index,
      maxPagesPerFeed: response.max_pages_per_feed,
      endReason: response.end_reason,
      canRefreshNow: response.can_refresh_now,
      refreshRemainingSeconds: response.refresh_remaining_seconds,
      nextRefreshAvailableAt,
      refreshIntervalSeconds: response.refresh_interval_seconds,
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
    const entry: SquareCategoriesCacheEntry = {
      items: cards,
      timestamp: Date.now(),
      isFallback: false,
    };
    this.setCategoriesCacheEntry(entry);
    this.logger.info('Square categories fetched', { count: cards.length, isFallback: false });
    return {
      items: cards,
      fromCache: false,
      cacheAgeMs: null,
      isFallback: false,
    };
  }

  getFallbackCategories(): SquareCategoryCard[] {
    return [];
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

  private buildSquareQuery(categoryKey: string, params: SquareLoadParams): string {
    const queryParts = [`category_key=${encodeURIComponent(categoryKey)}`];

    if (isNonEmptyString(params.cursor)) {
      queryParts.push(`cursor=${encodeURIComponent(params.cursor.trim())}`);
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

  private parseRequiredRefreshTimestamp(value: string): number {
    const parsed = Date.parse(value.trim());
    if (Number.isNaN(parsed)) {
      throw new Error('刷新时间字段无效');
    }
    return parsed;
  }
}

const squareDiscoveryService = new SquareDiscoveryService();
export default squareDiscoveryService;
