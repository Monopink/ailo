import squareDiscoveryService, {
  SQUARE_CACHE_STALE_PERIOD_MS,
  SQUARE_CACHE_TTL_MS,
  type SquareLoadParams,
  type SquareContactViewModel,
} from '../../../utils/discovery-service';
import { isValidCategoryKey } from '../../../utils/constants/square';
import { classifyError } from '../../../utils/error-classifier';
import { BasePageService } from './base-page-service';
import { createReadyScreenModel, type ScreenModel } from './page-state';

export type SquareLoadMode = 'initial' | 'refresh' | 'load_more';

export interface SquareCacheResult {
  screenModel: ScreenModel;
  contacts: SquareContactViewModel[];
  feedVersion: string;
  nextCursor: string | null;
  hasMore: boolean;
  nextRefreshAvailableAt: number | null;
  shouldRevalidate: boolean;
}

export interface SquareLoadResult {
  screenModel: ScreenModel;
  contacts: SquareContactViewModel[];
  feedVersion: string | null;
  nextCursor: string | null;
  hasMore: boolean;
  nextRefreshAvailableAt: number | null;
  authInvalid: boolean;
  shouldToastBlankFailure: boolean;
  errorMessage: string;
}

export interface SquareLoadContext {
  mode: SquareLoadMode;
  hasCurrentContent: boolean;
  currentContacts: SquareContactViewModel[];
  currentFeedVersion: string | null;
  currentCursor: string | null;
  hasMore: boolean;
}

const resolveScreenByContacts = (
  contacts: SquareContactViewModel[],
  refreshState: 'idle' | 'degraded'
): ScreenModel =>
  createReadyScreenModel({
    contentVariant: contacts.length === 0 ? 'empty' : 'data',
    refreshState,
  });

const mergeUniqueContacts = (
  currentContacts: SquareContactViewModel[],
  incomingContacts: SquareContactViewModel[]
): SquareContactViewModel[] => {
  if (currentContacts.length === 0) {
    return incomingContacts;
  }
  if (incomingContacts.length === 0) {
    return currentContacts;
  }
  const existing = new Set(currentContacts.map((item) => item.qiao_id));
  const merged = [...currentContacts];
  for (const contact of incomingContacts) {
    if (existing.has(contact.qiao_id)) {
      continue;
    }
    existing.add(contact.qiao_id);
    merged.push(contact);
  }
  return merged;
};

const buildContextResult = (
  context: SquareLoadContext,
  overrides: Partial<SquareLoadResult>
): SquareLoadResult => ({
  screenModel: createReadyScreenModel({
    contentVariant: context.hasCurrentContent ? 'data' : 'blank',
    refreshState: 'degraded',
  }),
  contacts: context.hasCurrentContent ? context.currentContacts : [],
  feedVersion: context.currentFeedVersion,
  nextCursor: context.currentCursor,
  hasMore: context.hasMore,
  nextRefreshAvailableAt: null,
  authInvalid: false,
  shouldToastBlankFailure: false,
  errorMessage: '',
  ...overrides,
});

const resolveLoadMorePrecheckResult = (context: SquareLoadContext): SquareLoadResult | null => {
  if (context.mode !== 'load_more') {
    return null;
  }
  if (!context.hasMore) {
    return buildContextResult(context, {
      screenModel: resolveScreenByContacts(context.currentContacts, 'idle'),
      contacts: context.currentContacts,
      hasMore: false,
    });
  }
  if (context.currentFeedVersion === null || context.currentCursor === null) {
    return buildContextResult(context, {
      screenModel: resolveScreenByContacts(context.currentContacts, 'degraded'),
      contacts: context.currentContacts,
      errorMessage: '加载状态无效，请刷新后重试',
    });
  }
  return null;
};

const buildRequestParams = (context: SquareLoadContext): SquareLoadParams => {
  if (context.mode === 'refresh') {
    return { refresh: true };
  }
  if (context.mode === 'load_more') {
    return {
      feedVersion: context.currentFeedVersion,
      cursor: context.currentCursor,
      refresh: false,
    };
  }
  return {
    feedVersion: context.currentFeedVersion,
    refresh: false,
  };
};

export class SquarePageService extends BasePageService {
  resolveCache(categoryKey: string): SquareCacheResult | null {
    if (!isValidCategoryKey(categoryKey)) {
      return null;
    }
    const cache = squareDiscoveryService.getCacheEntry(categoryKey);
    if (
      cache === null ||
      typeof cache.timestamp !== 'number' ||
      typeof cache.feedVersion !== 'string' ||
      cache.feedVersion.length === 0
    ) {
      return null;
    }

    const age = Date.now() - cache.timestamp;
    const isFresh = age < SQUARE_CACHE_TTL_MS;
    const isStale = age < SQUARE_CACHE_TTL_MS + SQUARE_CACHE_STALE_PERIOD_MS;
    if (!isFresh && !isStale) {
      return null;
    }

    return {
      screenModel: resolveScreenByContacts(cache.contacts, 'idle'),
      contacts: cache.contacts,
      feedVersion: cache.feedVersion,
      nextCursor: cache.nextCursor,
      hasMore: cache.hasMore,
      nextRefreshAvailableAt: cache.nextRefreshAvailableAt,
      shouldRevalidate: !isFresh,
    };
  }

  async load(categoryKey: string, context: SquareLoadContext): Promise<SquareLoadResult | null> {
    if (!isValidCategoryKey(categoryKey)) {
      return buildContextResult(context, {
        shouldToastBlankFailure: !context.hasCurrentContent,
        errorMessage: '无效的分类参数',
      });
    }

    const loadMorePrecheckResult = resolveLoadMorePrecheckResult(context);
    if (loadMorePrecheckResult !== null) {
      return loadMorePrecheckResult;
    }

    const seq = this.startRequest();
    try {
      const result = await squareDiscoveryService.load(categoryKey, buildRequestParams(context));
      if (!this.isRequestActive(seq)) {
        return null;
      }

      const contacts =
        context.mode === 'load_more'
          ? mergeUniqueContacts(context.currentContacts, result.contacts)
          : result.contacts;
      return {
        screenModel: resolveScreenByContacts(contacts, 'idle'),
        contacts,
        feedVersion: result.feedVersion,
        nextCursor: result.nextCursor,
        hasMore: result.hasMore,
        nextRefreshAvailableAt: result.nextRefreshAvailableAt,
        authInvalid: false,
        shouldToastBlankFailure: false,
        errorMessage: '',
      };
    } catch (error: unknown) {
      const semantics = classifyError(error);
      if (!this.isRequestActive(seq)) {
        return null;
      }
      const isAuthInvalid = semantics.reason === 'auth-invalid';

      const cache = squareDiscoveryService.getCacheEntry(categoryKey, context.currentFeedVersion);
      if (cache !== null && typeof cache.timestamp === 'number') {
        const age = Date.now() - cache.timestamp;
        if (age < SQUARE_CACHE_TTL_MS + SQUARE_CACHE_STALE_PERIOD_MS) {
          return buildContextResult(context, {
            screenModel: resolveScreenByContacts(cache.contacts, 'degraded'),
            contacts: cache.contacts,
            feedVersion: cache.feedVersion,
            nextCursor: cache.nextCursor,
            hasMore: cache.hasMore,
            nextRefreshAvailableAt: cache.nextRefreshAvailableAt,
            authInvalid: isAuthInvalid,
          });
        }
      }

      return buildContextResult(context, {
        authInvalid: isAuthInvalid,
        shouldToastBlankFailure: !context.hasCurrentContent && !isAuthInvalid,
        errorMessage: error instanceof Error ? error.message : '加载失败',
      });
    }
  }
}

export const createSquarePageService = (): SquarePageService => new SquarePageService();
