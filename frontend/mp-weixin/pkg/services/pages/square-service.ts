import squareDiscoveryService, {
  type SquareLoadParams,
  type SquareContactViewModel,
} from '../../../utils/discovery-service';
import { isValidCategoryKey } from '../../../utils/constants/square';
import { classifyError } from '../../../utils/error-classifier';
import { BasePageService } from './base-page-service';
import { createReadyScreenModel, type ScreenModel } from './page-state';

export type SquareLoadMode = 'initial' | 'load_more';

export type SquareEndReason = 'no_more_data' | 'page_limit_reached' | null;

export interface SquareLoadResult {
  screenModel: ScreenModel;
  contacts: SquareContactViewModel[];
  nextCursor: string | null;
  hasMore: boolean;
  currentPageIndex: number;
  maxPagesPerFeed: number;
  endReason: SquareEndReason;
  canRefreshNow: boolean;
  refreshRemainingSeconds: number;
  nextRefreshAvailableAt: number | null;
  refreshIntervalSeconds: number;
  authInvalid: boolean;
  shouldToastBlankFailure: boolean;
  errorMessage: string;
}

export interface SquareLoadContext {
  mode: SquareLoadMode;
  hasCurrentContent: boolean;
  currentContacts: SquareContactViewModel[];
  currentCursor: string | null;
  hasMore: boolean;
  currentNextRefreshAvailableAt: number | null;
  currentRefreshIntervalSeconds: number;
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
    contentVariant: context.hasCurrentContent ? 'data' : 'empty',
    refreshState: 'degraded',
  }),
  contacts: context.hasCurrentContent ? context.currentContacts : [],
  nextCursor: context.currentCursor,
  hasMore: context.hasMore,
  currentPageIndex: 1,
  maxPagesPerFeed: 1,
  endReason: null,
  canRefreshNow: false,
  refreshRemainingSeconds:
    context.currentNextRefreshAvailableAt === null
      ? 0
      : Math.max(0, Math.ceil((context.currentNextRefreshAvailableAt - Date.now()) / 1000)),
  nextRefreshAvailableAt: context.currentNextRefreshAvailableAt,
  refreshIntervalSeconds: context.currentRefreshIntervalSeconds,
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
      endReason: 'page_limit_reached',
    });
  }
  if (context.currentCursor === null) {
    return buildContextResult(context, {
      screenModel: resolveScreenByContacts(context.currentContacts, 'degraded'),
      contacts: context.currentContacts,
      errorMessage: '加载状态无效，请刷新后重试',
    });
  }
  return null;
};

const buildRequestParams = (context: SquareLoadContext): SquareLoadParams => {
  if (context.mode === 'load_more') {
    return {
      cursor: context.currentCursor,
    };
  }
  return {};
};

export class SquarePageService extends BasePageService {
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
        nextCursor: result.nextCursor,
        hasMore: result.hasMore,
        currentPageIndex: result.currentPageIndex,
        maxPagesPerFeed: result.maxPagesPerFeed,
        endReason: result.endReason,
        canRefreshNow: result.canRefreshNow,
        refreshRemainingSeconds: result.refreshRemainingSeconds,
        nextRefreshAvailableAt: result.nextRefreshAvailableAt,
        refreshIntervalSeconds: result.refreshIntervalSeconds,
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
      const isRateLimit = semantics.reason === 'rate-limit';

      return buildContextResult(context, {
        authInvalid: isAuthInvalid,
        shouldToastBlankFailure: false,
        errorMessage: isRateLimit ? '' : error instanceof Error ? error.message : '加载失败',
        canRefreshNow:
          context.currentNextRefreshAvailableAt === null
            ? true
            : Date.now() >= context.currentNextRefreshAvailableAt,
      });
    }
  }
}

export const createSquarePageService = (): SquarePageService => new SquarePageService();
