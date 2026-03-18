import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import {
  SQUARE_CATEGORY,
  SQUARE_ENTRY_CARDS,
  type SquareCategory,
  type SquareEntryCard,
} from '../../utils/constants/square';
import { initTabBar } from '../../utils/tab-bar';

const SQUARE_CATEGORY_VALUES = new Set<number>(Object.values(SQUARE_CATEGORY));

const isSquareCategory = (value: number): value is SquareCategory =>
  SQUARE_CATEGORY_VALUES.has(value);

const getDatasetValue = (event: WechatMiniprogram.BaseEvent, key: string): unknown => {
  const dataset = event.currentTarget.dataset as Record<string, unknown> | undefined;
  return dataset?.[key];
};

const toSquareCategory = (value: unknown): SquareCategory | null => {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return isSquareCategory(value) ? value : null;
  }
  if (typeof value === 'string') {
    if (value === 'null' || value === '') {
      return null;
    }
    const parsed = Number.parseInt(value, 10);
    if (Number.isNaN(parsed)) {
      return null;
    }
    return isSquareCategory(parsed) ? parsed : null;
  }
  return null;
};

interface SquareEntryPageData {
  pageLayoutData: PageLayoutData;
  entryCards: readonly SquareEntryCard[];
}

interface SquareEntryPageCustom {
  handleCardTap(event: WechatMiniprogram.TouchEvent): void;
}

Page<SquareEntryPageData, SquareEntryPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
      hasFooter: false,
    }),
    entryCards: SQUARE_ENTRY_CARDS,
  },

  onShow() {
    initTabBar(this);
  },

  handleCardTap(event) {
    const category = toSquareCategory(getDatasetValue(event, 'category')) ?? SQUARE_CATEGORY.FRIEND;
    void wx.navigateTo({
      url: `/pages/square/square?category=${category}`,
    });
  },
});
