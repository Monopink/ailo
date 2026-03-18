import squareDiscoveryService, {
  SQUARE_CACHE_STALE_PERIOD_MS,
  SQUARE_CACHE_TTL_MS,
  type SquareContactViewModel,
} from '../../utils/discovery-service';
import { type SquareCategory } from '../../utils/constants/square';
import { classifyError } from '../../utils/error-classifier';
import { BasePageService } from './base-page-service';
import { createReadyScreenModel, type ScreenModel } from './page-state';

export interface SquareCacheResult {
  screenModel: ScreenModel;
  contacts: SquareContactViewModel[];
  nextRefreshAvailableAt: number | null;
  shouldRevalidate: boolean;
}

export interface SquareLoadResult {
  screenModel: ScreenModel;
  contacts: SquareContactViewModel[];
  nextRefreshAvailableAt: number | null;
  authInvalid: boolean;
  shouldToastBlankFailure: boolean;
  errorMessage: string;
}

export interface SquareLoadContext {
  hasCurrentContent: boolean;
  currentContacts: SquareContactViewModel[];
}

const resolveScreenByContacts = (
  contacts: SquareContactViewModel[],
  refreshState: 'idle' | 'degraded'
): ScreenModel =>
  createReadyScreenModel({
    contentVariant: contacts.length === 0 ? 'empty' : 'data',
    refreshState,
  });

export class SquarePageService extends BasePageService {
  resolveCache(category: SquareCategory): SquareCacheResult | null {
    const cache = squareDiscoveryService.getCacheEntry(category);
    if (cache === null || typeof cache.timestamp !== 'number') {
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
      nextRefreshAvailableAt: cache.nextRefreshAvailableAt,
      shouldRevalidate: !isFresh,
    };
  }

  async load(
    category: SquareCategory,
    context: SquareLoadContext
  ): Promise<SquareLoadResult | null> {
    const seq = this.startRequest();
    try {
      const result = await squareDiscoveryService.load(category);
      if (!this.isRequestActive(seq)) {
        return null;
      }
      return {
        screenModel: resolveScreenByContacts(result.contacts, 'idle'),
        contacts: result.contacts,
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

      const cache = squareDiscoveryService.getCacheEntry(category);
      if (cache !== null && typeof cache.timestamp === 'number') {
        const age = Date.now() - cache.timestamp;
        if (age < SQUARE_CACHE_TTL_MS + SQUARE_CACHE_STALE_PERIOD_MS) {
          return {
            screenModel: resolveScreenByContacts(cache.contacts, 'degraded'),
            contacts: cache.contacts,
            nextRefreshAvailableAt: cache.nextRefreshAvailableAt,
            authInvalid: isAuthInvalid,
            shouldToastBlankFailure: false,
            errorMessage: '',
          };
        }
      }

      return {
        screenModel: createReadyScreenModel({
          contentVariant: context.hasCurrentContent ? 'data' : 'blank',
          refreshState: 'degraded',
        }),
        contacts: context.hasCurrentContent ? context.currentContacts : [],
        nextRefreshAvailableAt: null,
        authInvalid: isAuthInvalid,
        shouldToastBlankFailure: !context.hasCurrentContent && !isAuthInvalid,
        errorMessage: error instanceof Error ? error.message : '加载失败',
      };
    }
  }
}

export const createSquarePageService = (): SquarePageService => new SquarePageService();
