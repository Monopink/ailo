import { requireAuth } from '../../utils/auth-guard';
import { APP_CONFIG } from '../../utils/config';
import { getLogger } from '../../utils/logger';
import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { MESSAGE_TYPE } from '../../utils/constants/message';
import { isNonEmptyString } from '../../utils/guards';
import { normalizeError } from '../../utils/errors';
import messageEventBus from '../../utils/message/event-bus';
import unreadStore from '../../utils/message/unread-store';
import type { ConnectionState } from '../../utils/message/adapter-types';
import { type ScreenModel } from '../../services/pages/page-state';
import {
  createIndexPageService,
  type ContactListItem,
  type ContactSwipeAction,
} from '../../services/pages/index-service';
import { showAuthExpiredModalAndRelogin } from '../../utils/auth-expired-modal';
import { mapTagToneClasses } from '../../utils/tag-tone';
import { initTabBar } from '../../utils/tab-bar';

const logger = getLogger('ContactList');
const CONNECTION_ISSUE_DELAY = 8000;
const AUTO_RETRY_DELAYS_MS = [1200, 2600, 5200] as const;

type SwipeActionEvent = WechatMiniprogram.CustomEvent<ContactSwipeAction>;
type ThemeChangeResult = WechatMiniprogram.OnThemeChangeListenerResult;
type SupportedTheme = 'light' | 'dark';

type AuthGuardPage = WechatMiniprogram.Page.Instance<
  Record<string, unknown>,
  Record<string, unknown>
>;

interface LoadOptions {
  forceReload?: boolean;
}

interface ContactListRenderItem extends ContactListItem {
  hasTags: boolean;
  visibleTags: string[];
  visibleTagToneClasses: string[];
  hiddenTagCount: number;
  showTwoMessagePreview: boolean;
}

const TAG_GAP_RPX = 6;
const TAG_FALLBACK_VISIBLE_COUNT = 1;
const LIGHT_WORDMARK_SRC = '/assets/wordmark.svg';
const DARK_WORDMARK_SRC = '/assets/wordmark-dark.svg';

interface TagMeasureItem {
  key: string;
  text: string;
  kind: 'tag' | 'overflow';
  hiddenCount?: number;
}

interface MessageMeasureItem {
  key: string;
  text: string;
}

const normalizeTheme = (theme?: string): SupportedTheme => (theme === 'dark' ? 'dark' : 'light');

const getCurrentTheme = (): SupportedTheme => {
  const appBaseInfo = wx.getAppBaseInfo() as { theme?: string };
  return normalizeTheme(appBaseInfo.theme);
};

const getWordmarkSrcByTheme = (theme: SupportedTheme): string =>
  theme === 'dark' ? DARK_WORDMARK_SRC : LIGHT_WORDMARK_SRC;

const getWindowWidthPx = (): number => {
  if (typeof wx.getWindowInfo === 'function') {
    return wx.getWindowInfo().windowWidth;
  }
  return wx.getSystemInfoSync().windowWidth;
};

const getTagMeasureKey = (tag: string): string => `tag:${tag}`;

const getOverflowMeasureKey = (hiddenCount: number): string => `overflow:${hiddenCount}`;

const getMessageMeasureKey = (text: string): string => `message:${text}`;

const getValidTags = (tags: unknown): string[] => {
  if (!Array.isArray(tags)) {
    return [];
  }
  return tags.filter((tag): tag is string => typeof tag === 'string' && tag.trim().length > 0);
};

const buildFallbackTagLayout = (
  tags: string[]
): Pick<ContactListRenderItem, 'visibleTags' | 'hiddenTagCount'> => {
  const fallbackVisible = tags.slice(0, TAG_FALLBACK_VISIBLE_COUNT);
  return {
    visibleTags: fallbackVisible,
    hiddenTagCount: Math.max(0, tags.length - fallbackVisible.length),
  };
};

const buildTagMeasureItems = (contacts: ContactListRenderItem[]): TagMeasureItem[] => {
  const tagSet = new Set<string>();
  let maxTagCount = 0;

  contacts.forEach((contact) => {
    const tags = getValidTags(contact.tags);
    if (tags.length === 0) {
      return;
    }
    maxTagCount = Math.max(maxTagCount, tags.length);
    tags.forEach((tag) => tagSet.add(tag));
  });

  const tagItems = Array.from(tagSet).map<TagMeasureItem>((tag) => ({
    key: getTagMeasureKey(tag),
    text: tag,
    kind: 'tag',
  }));

  const overflowItems: TagMeasureItem[] = [];
  for (let hiddenCount = 1; hiddenCount <= maxTagCount; hiddenCount += 1) {
    overflowItems.push({
      key: getOverflowMeasureKey(hiddenCount),
      text: `+${hiddenCount}`,
      kind: 'overflow',
      hiddenCount,
    });
  }

  return [...tagItems, ...overflowItems];
};

const buildMessageMeasureItems = (contacts: ContactListRenderItem[]): MessageMeasureItem[] => {
  const latestMessageSet = new Set<string>();
  contacts.forEach((contact) => {
    if (
      contact.hasTags ||
      !contact.canShowTwoMessagePreview ||
      !isNonEmptyString(contact.lastMessage)
    ) {
      return;
    }
    latestMessageSet.add(contact.lastMessage);
  });
  return Array.from(latestMessageSet).map<MessageMeasureItem>((text) => ({
    key: getMessageMeasureKey(text),
    text,
  }));
};

const isPositiveWidth = (value: number | undefined): value is number =>
  typeof value === 'number' && Number.isFinite(value) && value > 0;

const resolveInitialVisibleTagLayout = (
  tags: string[],
  maxWidthPx: number,
  gapPx: number,
  resolveTagWidth: (tag: string) => number | undefined
): { visibleCount: number; usedWidthPx: number } => {
  let visibleCount = 0;
  let usedWidthPx = 0;
  for (let index = 0; index < tags.length; index += 1) {
    const tagWidthPx = resolveTagWidth(tags[index]);
    if (!isPositiveWidth(tagWidthPx)) {
      break;
    }
    const nextWidthPx = tagWidthPx + (visibleCount > 0 ? gapPx : 0);
    if (usedWidthPx + nextWidthPx > maxWidthPx) {
      break;
    }
    usedWidthPx += nextWidthPx;
    visibleCount += 1;
  }
  return { visibleCount, usedWidthPx };
};

interface OverflowLayoutParams {
  tags: string[];
  maxWidthPx: number;
  gapPx: number;
  initialVisibleCount: number;
  initialUsedWidthPx: number;
  resolveTagWidth: (tag: string) => number | undefined;
  resolveOverflowWidth: (hiddenCount: number) => number | undefined;
}

const resolveLayoutWithOverflow = ({
  tags,
  maxWidthPx,
  gapPx,
  initialVisibleCount,
  initialUsedWidthPx,
  resolveTagWidth,
  resolveOverflowWidth,
}: OverflowLayoutParams): Pick<ContactListRenderItem, 'visibleTags' | 'hiddenTagCount'> | null => {
  let visibleCount = initialVisibleCount;
  let usedWidthPx = initialUsedWidthPx;
  let hiddenTagCount = tags.length - visibleCount;

  while (hiddenTagCount > 0) {
    const overflowWidthPx = resolveOverflowWidth(hiddenTagCount);
    if (!isPositiveWidth(overflowWidthPx)) {
      return null;
    }
    const totalWidthWithOverflow = usedWidthPx + (visibleCount > 0 ? gapPx : 0) + overflowWidthPx;
    if (totalWidthWithOverflow <= maxWidthPx) {
      return {
        visibleTags: tags.slice(0, visibleCount),
        hiddenTagCount,
      };
    }
    if (visibleCount === 0) {
      return {
        visibleTags: [],
        hiddenTagCount,
      };
    }

    visibleCount -= 1;
    hiddenTagCount = tags.length - visibleCount;
    const removedTagWidthPx = resolveTagWidth(tags[visibleCount]);
    const shrinkWidthPx =
      (isPositiveWidth(removedTagWidthPx) ? removedTagWidthPx : 0) + (visibleCount > 0 ? gapPx : 0);
    usedWidthPx = Math.max(0, usedWidthPx - shrinkWidthPx);
  }

  return {
    visibleTags: tags.slice(0, visibleCount),
    hiddenTagCount: 0,
  };
};

const computeVisibleTagsByMeasuredWidths = (
  tags: string[],
  maxWidthPx: number,
  gapPx: number,
  resolveTagWidth: (tag: string) => number | undefined,
  resolveOverflowWidth: (hiddenCount: number) => number | undefined
): Pick<ContactListRenderItem, 'visibleTags' | 'hiddenTagCount'> => {
  if (tags.length === 0) {
    return { visibleTags: [], hiddenTagCount: 0 };
  }

  if (maxWidthPx <= 0) {
    return buildFallbackTagLayout(tags);
  }

  const initialLayout = resolveInitialVisibleTagLayout(tags, maxWidthPx, gapPx, resolveTagWidth);
  if (initialLayout.visibleCount >= tags.length) {
    return { visibleTags: tags, hiddenTagCount: 0 };
  }

  const layoutWithOverflow = resolveLayoutWithOverflow({
    tags,
    maxWidthPx,
    gapPx,
    initialVisibleCount: initialLayout.visibleCount,
    initialUsedWidthPx: initialLayout.usedWidthPx,
    resolveTagWidth,
    resolveOverflowWidth,
  });
  return layoutWithOverflow ?? buildFallbackTagLayout(tags);
};

const areSameStringArrays = (left: string[], right: string[]): boolean => {
  if (left.length !== right.length) {
    return false;
  }
  return left.every((value, index) => value === right[index]);
};

const getRectWidth = (value: unknown): number | undefined => {
  if (typeof value !== 'object' || value === null || !('width' in value)) {
    return undefined;
  }
  const width = (value as { width?: unknown }).width;
  if (typeof width !== 'number' || !Number.isFinite(width) || width <= 0) {
    return undefined;
  }
  return width;
};

const getVisibleTagToneClasses = (tags: string[], visibleCount: number): string[] =>
  mapTagToneClasses(tags).slice(0, visibleCount);

const decorateContactList = (contacts: ContactListItem[]): ContactListRenderItem[] =>
  contacts.map((contact) => {
    const tags = getValidTags(contact.tags);
    const tagLayout = buildFallbackTagLayout(tags);
    return {
      ...contact,
      hasTags: tags.length > 0,
      visibleTags: tagLayout.visibleTags,
      visibleTagToneClasses: getVisibleTagToneClasses(tags, tagLayout.visibleTags.length),
      hiddenTagCount: tagLayout.hiddenTagCount,
      showTwoMessagePreview: false,
    };
  });

const buildTwoMessagePreviewResetPayload = (
  contactList: ContactListRenderItem[],
  messageMeasureItems: MessageMeasureItem[]
): { nextContactList: ContactListRenderItem[]; shouldUpdate: boolean } => {
  const nextContactList = contactList.map((contact) =>
    contact.showTwoMessagePreview ? { ...contact, showTwoMessagePreview: false } : contact
  );
  const hasContactListChanged = nextContactList.some(
    (contact, index) => contact !== contactList[index]
  );
  return {
    nextContactList,
    shouldUpdate: hasContactListChanged || messageMeasureItems.length > 0,
  };
};

interface TwoMessagePreviewLayoutParams {
  contactList: ContactListRenderItem[];
  candidateContactIndexes: number[];
  noTagContactIndexes: number[];
  messageMeasureItems: MessageMeasureItem[];
  measureRectValues: unknown[];
  rowRectValues: unknown[];
  messageWidthCache: Record<string, number>;
}

const resolveTwoMessagePreviewContactList = ({
  contactList,
  candidateContactIndexes,
  noTagContactIndexes,
  messageMeasureItems,
  measureRectValues,
  rowRectValues,
  messageWidthCache,
}: TwoMessagePreviewLayoutParams): ContactListRenderItem[] => {
  const measuredMessageWidths = new Map<string, number>();
  messageMeasureItems.forEach((item, index) => {
    const width = getRectWidth(measureRectValues[index]);
    if (!isPositiveWidth(width)) {
      return;
    }
    measuredMessageWidths.set(item.text, width);
    messageWidthCache[item.text] = width;
  });

  const rowWidthByContactIndex = new Map<number, number>();
  noTagContactIndexes.forEach((contactIndex, rowIndex) => {
    const width = getRectWidth(rowRectValues[rowIndex]);
    if (!isPositiveWidth(width)) {
      return;
    }
    rowWidthByContactIndex.set(contactIndex, width);
  });

  const nextContactList = [...contactList];
  candidateContactIndexes.forEach((contactIndex) => {
    const contact = nextContactList[contactIndex];
    if (typeof contact === 'undefined') {
      return;
    }
    const latestMessageWidth =
      measuredMessageWidths.get(contact.lastMessage) ?? messageWidthCache[contact.lastMessage];
    const availableWidth = rowWidthByContactIndex.get(contactIndex);
    const shouldShowTwoMessagePreview =
      isPositiveWidth(latestMessageWidth) &&
      isPositiveWidth(availableWidth) &&
      latestMessageWidth <= availableWidth &&
      isNonEmptyString(contact.secondLastMessage);
    if (contact.showTwoMessagePreview === shouldShowTwoMessagePreview) {
      return;
    }
    nextContactList[contactIndex] = {
      ...contact,
      showTwoMessagePreview: shouldShowTwoMessagePreview,
    };
  });

  return nextContactList;
};

interface ContactListPageData {
  pageLayoutData: PageLayoutData;
  contactList: ContactListRenderItem[];
  tagMeasureItems: TagMeasureItem[];
  messageMeasureItems: MessageMeasureItem[];
  unreadTotal: number;
  showConnectionIssue: boolean;
  navbarTitle: string;
  wordmarkSrc: string;
}

interface ContactListPageCustom {
  indexPageService: ReturnType<typeof createIndexPageService>;
  _loadPromise: Promise<void> | null;
  _connectionIssueTimer: ReturnType<typeof setTimeout> | null;
  _connectionSubscription: (() => void) | null;
  _autoRetryTimer: ReturnType<typeof setTimeout> | null;
  _autoRetryAttempt: number;
  _tagLayoutTimer: ReturnType<typeof setTimeout> | null;
  _tagLayoutVersion: number;
  _tagWidthCache: Record<string, number>;
  _overflowWidthCache: Record<number, number>;
  _messagePreviewTimer: ReturnType<typeof setTimeout> | null;
  _messagePreviewVersion: number;
  _messageWidthCache: Record<string, number>;
  _themeChangeHandler: ((event: ThemeChangeResult) => void) | null;
  applyScreenModel(screenModel: ScreenModel): void;
  updateNavigationTitle(): void;
  bindThemeChange(): void;
  unbindThemeChange(): void;
  syncWordmarkByTheme(theme?: string): void;
  bindConnectionStatus(): void;
  handleConnectionStateChange(state: ConnectionState): void;
  clearConnectionIssueTimer(): void;
  clearAutoRetryTimer(): void;
  clearTagLayoutTimer(): void;
  clearMessagePreviewTimer(): void;
  scheduleTagLayoutRefresh(): void;
  scheduleMessagePreviewRefresh(): void;
  refreshTagLayout(): void;
  refreshMessagePreviewLayout(): void;
  scheduleAutoRetryLoad(): void;
  applyLoadedList(
    screenModel: ScreenModel,
    contactList: ContactListItem[],
    unreadTotal: number
  ): void;
  loadContactList(options?: LoadOptions): Promise<void>;
  loadContactsFromCache(): Promise<boolean>;
  refreshContactListFromAPI(): Promise<void>;
  updateContactPreview(convId: string): Promise<void>;
  onPullDownRefresh(): void;
  goToChat(event: WechatMiniprogram.BaseEvent): void;
  goToSquareEntry(): void;
  onSwipeActionClick(event: SwipeActionEvent): void;
  navigateToContactInfo(convId?: string): void;
  markContactAsUnreadByIndex(index: number): void;
  markContactAsReadByIndex(index: number): void;
  onMessageReceived(message: Ailo.MessagePayload): void;
}

const showToast = (
  title: string,
  icon: WechatMiniprogram.ShowToastOption['icon'] = 'none'
): void => {
  void wx.showToast({ title, icon });
};

const getDataset = (event: WechatMiniprogram.BaseEvent): Record<string, unknown> => {
  const dataset = event.currentTarget.dataset as Record<string, unknown> | undefined;
  return dataset ?? {};
};

const getDatasetString = (event: WechatMiniprogram.BaseEvent, key: string): string | undefined => {
  const value = getDataset(event)[key];
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number') {
    return String(value);
  }
  return undefined;
};

const getDatasetNumber = (event: WechatMiniprogram.BaseEvent, key: string): number | undefined => {
  const value = getDataset(event)[key];
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim().length > 0) {
    const parsed = Number(value);
    return Number.isNaN(parsed) ? undefined : parsed;
  }
  return undefined;
};

const buildPageLayoutScreenModelPayload = (screenModel: ScreenModel): Record<string, unknown> => ({
  'pageLayoutData.screenModel': screenModel,
});

Page<ContactListPageData, ContactListPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
      emptyMessage: '暂无联系人',
      hasFooter: false,
    }),
    contactList: [],
    tagMeasureItems: [],
    messageMeasureItems: [],
    unreadTotal: 0,
    showConnectionIssue: false,
    navbarTitle: APP_CONFIG.brandName,
    wordmarkSrc: getWordmarkSrcByTheme(getCurrentTheme()),
  },

  indexPageService: null as unknown as ReturnType<typeof createIndexPageService>,
  _loadPromise: null,
  _connectionIssueTimer: null,
  _connectionSubscription: null,
  _autoRetryTimer: null,
  _autoRetryAttempt: 0,
  _tagLayoutTimer: null,
  _tagLayoutVersion: 0,
  _tagWidthCache: {},
  _overflowWidthCache: {},
  _messagePreviewTimer: null,
  _messagePreviewVersion: 0,
  _messageWidthCache: {},
  _themeChangeHandler: null,

  applyScreenModel(screenModel: ScreenModel) {
    this.setData(buildPageLayoutScreenModelPayload(screenModel));
  },

  async onLoad() {
    logger.info('Contact list page loaded');
    this.indexPageService = createIndexPageService();
    this._autoRetryAttempt = 0;
    this.clearAutoRetryTimer();
    this.updateNavigationTitle();
    this.bindThemeChange();
    this.syncWordmarkByTheme();
    this.bindConnectionStatus();
    void this.loadContactsFromCache();

    const isAuth = await requireAuth(this as unknown as AuthGuardPage);
    if (!isAuth) {
      return;
    }

    void this.loadContactList();
  },

  onShow() {
    initTabBar(this);
    this.updateNavigationTitle();
    this.syncWordmarkByTheme();
    void this.loadContactsFromCache();
    if (this.data.pageLayoutData.screenModel.contentVariant === 'blank') {
      void this.loadContactList();
    }
  },

  onHide() {
    this.clearAutoRetryTimer();
    this.clearTagLayoutTimer();
    this.clearMessagePreviewTimer();
  },

  onPullDownRefresh() {
    void this.refreshContactListFromAPI().finally(() => {
      void wx.stopPullDownRefresh();
    });
  },

  onUnload() {
    this.clearConnectionIssueTimer();
    this.clearAutoRetryTimer();
    this.clearTagLayoutTimer();
    this.clearMessagePreviewTimer();
    this.unbindThemeChange();
    this.indexPageService.dispose();
    if (this._connectionSubscription !== null) {
      this._connectionSubscription();
      this._connectionSubscription = null;
    }
  },

  bindThemeChange() {
    if (this._themeChangeHandler !== null) {
      return;
    }

    this._themeChangeHandler = (event: ThemeChangeResult): void => {
      this.syncWordmarkByTheme(event.theme);
    };
    wx.onThemeChange(this._themeChangeHandler);
  },

  unbindThemeChange() {
    if (this._themeChangeHandler === null) {
      return;
    }
    wx.offThemeChange(this._themeChangeHandler);
    this._themeChangeHandler = null;
  },

  syncWordmarkByTheme(theme?: string) {
    const nextWordmarkSrc = getWordmarkSrcByTheme(normalizeTheme(theme ?? getCurrentTheme()));
    if (this.data.wordmarkSrc === nextWordmarkSrc) {
      return;
    }
    this.setData({ wordmarkSrc: nextWordmarkSrc });
  },

  bindConnectionStatus() {
    if (this._connectionSubscription !== null) {
      return;
    }
    const app = getApp<AppInstance>();
    const messageService = app.getMessageService();
    if (messageService !== null) {
      this.handleConnectionStateChange(messageService.getConnectionState());
    }
    this._connectionSubscription = messageEventBus.onConnection((state) => {
      this.handleConnectionStateChange(state);
    });
  },

  handleConnectionStateChange(state: ConnectionState) {
    if (state === 'connected') {
      this.clearConnectionIssueTimer();
      if (this.data.showConnectionIssue) {
        this.setData({ showConnectionIssue: false });
      }
      return;
    }

    if (state === 'suspending') {
      this.clearConnectionIssueTimer();
      if (this.data.showConnectionIssue) {
        this.setData({ showConnectionIssue: false });
      }
      return;
    }

    if (state === 'disconnected') {
      if (this._connectionIssueTimer !== null) {
        return;
      }
      this._connectionIssueTimer = setTimeout(() => {
        this._connectionIssueTimer = null;
        if (!this.data.showConnectionIssue) {
          this.setData({ showConnectionIssue: true });
        }
      }, CONNECTION_ISSUE_DELAY);
    }
  },

  clearConnectionIssueTimer() {
    if (this._connectionIssueTimer !== null) {
      clearTimeout(this._connectionIssueTimer);
      this._connectionIssueTimer = null;
    }
  },

  clearAutoRetryTimer() {
    if (this._autoRetryTimer !== null) {
      clearTimeout(this._autoRetryTimer);
      this._autoRetryTimer = null;
    }
  },

  clearTagLayoutTimer() {
    if (this._tagLayoutTimer !== null) {
      clearTimeout(this._tagLayoutTimer);
      this._tagLayoutTimer = null;
    }
  },

  clearMessagePreviewTimer() {
    if (this._messagePreviewTimer !== null) {
      clearTimeout(this._messagePreviewTimer);
      this._messagePreviewTimer = null;
    }
  },

  scheduleTagLayoutRefresh() {
    if (this._tagLayoutTimer !== null) {
      return;
    }
    this._tagLayoutTimer = setTimeout(() => {
      this._tagLayoutTimer = null;
      this.refreshTagLayout();
    }, 0);
  },

  scheduleMessagePreviewRefresh() {
    if (this._messagePreviewTimer !== null) {
      return;
    }
    this._messagePreviewTimer = setTimeout(() => {
      this._messagePreviewTimer = null;
      this.refreshMessagePreviewLayout();
    }, 0);
  },

  refreshTagLayout() {
    const taggedContactIndexes = this.data.contactList
      .map((contact, index) => (contact.hasTags ? index : -1))
      .filter((index) => index >= 0);
    if (taggedContactIndexes.length === 0) {
      if (this.data.tagMeasureItems.length > 0) {
        this.setData({ tagMeasureItems: [] });
      }
      return;
    }

    const tagMeasureItems = buildTagMeasureItems(this.data.contactList);
    this._tagLayoutVersion += 1;
    const layoutVersion = this._tagLayoutVersion;

    this.setData({ tagMeasureItems }, () => {
      wx.nextTick(() => {
        if (layoutVersion !== this._tagLayoutVersion) {
          return;
        }

        wx.createSelectorQuery()
          .in(this)
          .selectAll('.index-tag-measure__item')
          .boundingClientRect()
          .selectAll('.index-cell__tags-row')
          .boundingClientRect()
          .exec((queryResult) => {
            if (layoutVersion !== this._tagLayoutVersion) {
              return;
            }
            const queryResultValue: unknown = queryResult;
            if (!Array.isArray(queryResultValue) || queryResultValue.length < 2) {
              return;
            }
            const measureRectValues: unknown = queryResultValue[0];
            const rowRectValues: unknown = queryResultValue[1];
            if (!Array.isArray(measureRectValues) || !Array.isArray(rowRectValues)) {
              return;
            }
            if (measureRectValues.length === 0 || rowRectValues.length === 0) {
              return;
            }

            const measuredTagWidths = new Map<string, number>();
            const measuredOverflowWidths = new Map<number, number>();
            tagMeasureItems.forEach((item, index) => {
              const width = getRectWidth(measureRectValues[index]);
              if (typeof width !== 'number') {
                return;
              }
              if (item.kind === 'tag') {
                measuredTagWidths.set(item.text, width);
                this._tagWidthCache[item.text] = width;
                return;
              }
              if (typeof item.hiddenCount === 'number') {
                measuredOverflowWidths.set(item.hiddenCount, width);
                this._overflowWidthCache[item.hiddenCount] = width;
              }
            });

            const gapPx = (getWindowWidthPx() / 750) * TAG_GAP_RPX;
            const nextContactList = [...this.data.contactList];

            taggedContactIndexes.forEach((contactIndex, rowIndex) => {
              const contact = nextContactList[contactIndex];
              const tags = getValidTags(contact.tags);
              const rowWidthPx = getRectWidth(rowRectValues[rowIndex]) ?? 0;
              const nextLayout = computeVisibleTagsByMeasuredWidths(
                tags,
                rowWidthPx,
                gapPx,
                (tag) => measuredTagWidths.get(tag) ?? this._tagWidthCache[tag],
                (hiddenCount) =>
                  measuredOverflowWidths.get(hiddenCount) ?? this._overflowWidthCache[hiddenCount]
              );
              const nextVisibleTagToneClasses = getVisibleTagToneClasses(
                tags,
                nextLayout.visibleTags.length
              );
              if (
                nextLayout.hiddenTagCount === contact.hiddenTagCount &&
                areSameStringArrays(nextLayout.visibleTags, contact.visibleTags) &&
                areSameStringArrays(nextVisibleTagToneClasses, contact.visibleTagToneClasses)
              ) {
                return;
              }
              nextContactList[contactIndex] = {
                ...contact,
                visibleTags: nextLayout.visibleTags,
                visibleTagToneClasses: nextVisibleTagToneClasses,
                hiddenTagCount: nextLayout.hiddenTagCount,
              };
            });

            const hasChanged = nextContactList.some(
              (contact, index) => contact !== this.data.contactList[index]
            );
            if (hasChanged) {
              this.setData({ contactList: nextContactList });
            }
          });
      });
    });
  },

  refreshMessagePreviewLayout() {
    const noTagContactIndexes = this.data.contactList
      .map((contact, index) => (!contact.hasTags ? index : -1))
      .filter((index) => index >= 0);
    const candidateContactIndexes = noTagContactIndexes.filter(
      (contactIndex) => this.data.contactList[contactIndex].canShowTwoMessagePreview
    );
    const resetPayload = buildTwoMessagePreviewResetPayload(
      this.data.contactList,
      this.data.messageMeasureItems
    );

    if (candidateContactIndexes.length === 0) {
      if (resetPayload.shouldUpdate) {
        this.setData({
          contactList: resetPayload.nextContactList,
          messageMeasureItems: [],
        });
      }
      return;
    }

    const messageMeasureItems = buildMessageMeasureItems(this.data.contactList);
    if (messageMeasureItems.length === 0) {
      if (resetPayload.shouldUpdate) {
        this.setData({
          contactList: resetPayload.nextContactList,
          messageMeasureItems: [],
        });
      }
      return;
    }

    this._messagePreviewVersion += 1;
    const layoutVersion = this._messagePreviewVersion;

    this.setData({ messageMeasureItems }, () => {
      wx.nextTick(() => {
        if (layoutVersion !== this._messagePreviewVersion) {
          return;
        }

        wx.createSelectorQuery()
          .in(this)
          .selectAll('.index-message-measure__item')
          .boundingClientRect()
          .selectAll('.index-cell__message-main--double')
          .boundingClientRect()
          .exec((queryResult) => {
            if (layoutVersion !== this._messagePreviewVersion) {
              return;
            }
            const queryResultValue: unknown = queryResult;
            if (!Array.isArray(queryResultValue) || queryResultValue.length < 2) {
              return;
            }
            const measureRectValues: unknown = queryResultValue[0];
            const rowRectValues: unknown = queryResultValue[1];
            if (!Array.isArray(measureRectValues) || !Array.isArray(rowRectValues)) {
              return;
            }
            if (measureRectValues.length === 0 || rowRectValues.length === 0) {
              return;
            }

            const nextContactList = resolveTwoMessagePreviewContactList({
              contactList: this.data.contactList,
              candidateContactIndexes,
              noTagContactIndexes,
              messageMeasureItems,
              measureRectValues,
              rowRectValues,
              messageWidthCache: this._messageWidthCache,
            });

            const hasChanged = nextContactList.some(
              (contact, index) => contact !== this.data.contactList[index]
            );
            if (hasChanged) {
              this.setData({ contactList: nextContactList });
            }
          });
      });
    });
  },

  scheduleAutoRetryLoad() {
    if (this._autoRetryTimer !== null) {
      return;
    }
    if (this._autoRetryAttempt >= AUTO_RETRY_DELAYS_MS.length) {
      return;
    }

    const delay = AUTO_RETRY_DELAYS_MS[this._autoRetryAttempt];
    this._autoRetryTimer = setTimeout(() => {
      this._autoRetryTimer = null;
      this._autoRetryAttempt += 1;
      void this.loadContactList({ forceReload: true });
    }, delay);
  },

  applyLoadedList(screenModel, contactList, unreadTotal) {
    const contactListForRender = decorateContactList(contactList);
    this.setData({
      contactList: contactListForRender,
      unreadTotal,
      ...buildPageLayoutScreenModelPayload(screenModel),
    });
    this.scheduleTagLayoutRefresh();
    this.scheduleMessagePreviewRefresh();
    this.updateNavigationTitle();
  },

  updateNavigationTitle() {
    const brandName = APP_CONFIG.brandName;
    if (isNonEmptyString(brandName)) {
      this.setData({ navbarTitle: brandName });
    }
  },

  async loadContactList(options: LoadOptions = {}) {
    const { forceReload = false } = options;
    if (this._loadPromise !== null && !forceReload) {
      return this._loadPromise;
    }

    const loadTask = (async (): Promise<void> => {
      if (!forceReload || this.data.contactList.length === 0) {
        await this.loadContactsFromCache();
      }

      const currentContentVariant = this.data.pageLayoutData.screenModel.contentVariant;
      const hasCurrentModel = currentContentVariant !== 'blank';
      const refreshingContentVariant = hasCurrentModel
        ? this.data.contactList.length === 0
          ? 'empty'
          : 'data'
        : 'blank';

      this.applyScreenModel({
        ...this.data.pageLayoutData.screenModel,
        screenState: 'ready',
        contentVariant: refreshingContentVariant,
        refreshState: 'refreshing',
      });

      const result = await this.indexPageService.refresh({
        contactList: this.data.contactList,
        unreadTotal: this.data.unreadTotal,
        currentContentVariant,
      });
      if (result === null) {
        return;
      }
      if (result.authInvalid) {
        await showAuthExpiredModalAndRelogin();
        return;
      }

      if (result.screenModel.contentVariant === 'blank') {
        this.applyScreenModel({
          ...result.screenModel,
          contentVariant: 'empty',
        });
        this.scheduleAutoRetryLoad();
        return;
      }

      this._autoRetryAttempt = 0;
      this.clearAutoRetryTimer();
      this.applyLoadedList(result.screenModel, result.contactList, result.unreadTotal);
    })();

    this._loadPromise = loadTask.finally(() => {
      this._loadPromise = null;
    });

    return this._loadPromise;
  },

  async loadContactsFromCache() {
    try {
      const result = await this.indexPageService.bootstrap();
      if (result === null) {
        return false;
      }
      this.applyLoadedList(result.screenModel, result.contactList, result.unreadTotal);
      return true;
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.error('Failed to load contacts from cache', { error: err.message });
      return false;
    }
  },

  async refreshContactListFromAPI() {
    if (this._loadPromise !== null) {
      try {
        await this._loadPromise;
      } catch (error: unknown) {
        const err = normalizeError(error);
        logger.warn('Previous contact refresh failed', { error: err.message });
      }
    }
    return this.loadContactList({ forceReload: true });
  },

  onMessageReceived(message) {
    logger.info('Message received in contact list', {
      msg_id: message.msg_id,
      message_type: message.message_type,
    });

    if (message.message_type === MESSAGE_TYPE.CHAT_INFO) {
      void this.refreshContactListFromAPI();
      return;
    }

    if (isNonEmptyString(message.conv_id)) {
      void this.updateContactPreview(message.conv_id);
    }
  },

  async updateContactPreview(convId: string): Promise<void> {
    if (!isNonEmptyString(convId)) {
      return;
    }
    const result = await this.indexPageService.enrichContactPreview(convId, this.data.contactList);
    const contactList = decorateContactList(result.contactList);
    this.setData({
      contactList,
      unreadTotal: result.unreadTotal,
    });
    this.scheduleTagLayoutRefresh();
    this.scheduleMessagePreviewRefresh();
    this.updateNavigationTitle();
  },

  goToChat(event) {
    const convId = getDatasetString(event, 'id');
    if (!isNonEmptyString(convId)) {
      return;
    }
    void wx.navigateTo({ url: `/pkg/chat/chat?id=${convId}` });
  },

  goToSquareEntry() {
    void wx.switchTab({ url: '/pages/square-entry/square-entry' });
  },

  onSwipeActionClick(event: SwipeActionEvent) {
    const action = event.detail;
    const convId = getDatasetString(event, 'id');
    if (!isNonEmptyString(convId)) {
      return;
    }
    const contactIndex = getDatasetNumber(event, 'index');
    if (typeof contactIndex !== 'number') {
      return;
    }

    if (action.key === 'view-contact-info') {
      this.navigateToContactInfo(convId);
    } else if (action.key === 'mark-as-unread') {
      this.markContactAsUnreadByIndex(contactIndex);
    } else {
      this.markContactAsReadByIndex(contactIndex);
    }
  },

  navigateToContactInfo(convId?: string) {
    if (!isNonEmptyString(convId)) {
      return;
    }
    void wx.navigateTo({
      url: `/pkg/contact-info/contact-info?id=${convId}`,
      events: {
        contactAvatarUpdated: () => {
          void this.loadContactsFromCache();
        },
      },
    });
  },

  markContactAsUnreadByIndex(index: number) {
    if (!Number.isInteger(index) || index < 0) {
      return;
    }

    const contactList = [...this.data.contactList];
    const target = contactList[index];
    if (typeof target === 'undefined') {
      return;
    }

    const convId = target.conversation_id;
    if (!isNonEmptyString(convId)) {
      return;
    }

    void (async () => {
      try {
        await unreadStore.markConversationAsUnread(convId);
        const result = await this.indexPageService.refreshConversationUnreadState(
          this.data.contactList,
          convId
        );

        this.setData({
          contactList: result.contactList,
          unreadTotal: result.unreadTotal,
        });
        this.scheduleMessagePreviewRefresh();
        this.updateNavigationTitle();
        showToast('已标为未读', 'success');
      } catch (error: unknown) {
        const err = normalizeError(error);
        logger.warn('Mark contact as unread failed', { error: err.message });
        showToast('标记失败');
      }
    })();
  },

  markContactAsReadByIndex(index: number) {
    if (!Number.isInteger(index) || index < 0) {
      return;
    }

    const contactList = [...this.data.contactList];
    const target = contactList[index];
    if (typeof target === 'undefined') {
      return;
    }

    const convId = target.conversation_id;
    if (!isNonEmptyString(convId)) {
      return;
    }

    void (async () => {
      try {
        await unreadStore.markConversationAsRead(convId);
        const result = await this.indexPageService.refreshConversationUnreadState(
          this.data.contactList,
          convId
        );

        this.setData({
          contactList: result.contactList,
          unreadTotal: result.unreadTotal,
        });
        this.scheduleMessagePreviewRefresh();
        this.updateNavigationTitle();
        showToast('已标为已读', 'success');
      } catch (error: unknown) {
        const err = normalizeError(error);
        logger.warn('Mark contact as read failed', { error: err.message });
        showToast('标记失败');
      }
    })();
  },
});
