import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { previewMockData } from '../preview-common/data';
import {
  getPreviewTabPath,
  listPreviewTabItems,
  type PreviewTabItem,
  type PreviewTabKey,
} from '../preview-common/navigation';
import { isValidCategoryKey, type SquareCategoryCard } from '../../utils/constants/square';
import { getLogger } from '../../utils/logger';
import { ensurePreviewAccess } from '../../utils/runtime-segment';

const logger = getLogger('PreviewSquare');

interface PreviewSquarePageData {
  pageLayoutData: PageLayoutData;
  entryCards: SquareCategoryCard[];
  categoriesReady: boolean;
  tabItems: PreviewTabItem[];
  activeTabKey: PreviewTabKey;
}

interface PreviewSquarePageCustom {
  _navigating: boolean;
  handleCardTap(event: WechatMiniprogram.BaseEvent): void;
  handleTabTap(event: WechatMiniprogram.BaseEvent): void;
}

const getDatasetValue = (event: WechatMiniprogram.BaseEvent, key: string): unknown => {
  const dataset = event.currentTarget.dataset as Record<string, unknown> | undefined;
  return dataset?.[key];
};

const resolveCategoryKey = (value: unknown): string | null =>
  typeof value === 'string' && isValidCategoryKey(value) ? value : null;

const showToast = (title: string): void => {
  void wx.showToast({ title, icon: 'none' });
};

Page<PreviewSquarePageData, PreviewSquarePageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
      hasFooter: true,
      emptyMessage: '暂无内容',
    }),
    entryCards: previewMockData.listCategories(),
    categoriesReady: previewMockData.listCategories().length > 0,
    tabItems: listPreviewTabItems(),
    activeTabKey: 'square',
  },

  _navigating: false,

  onShow() {
    if (!ensurePreviewAccess('/pkg/preview-square/preview-square')) {
      return;
    }
    const entryCards = previewMockData.listCategories();
    this.setData({
      entryCards,
      categoriesReady: entryCards.length > 0,
      tabItems: listPreviewTabItems(),
      activeTabKey: 'square',
    });
  },

  handleCardTap(event: WechatMiniprogram.BaseEvent) {
    if (this._navigating) {
      showToast('页面跳转中');
      return;
    }
    if (!this.data.categoriesReady) {
      showToast('暂无内容');
      return;
    }
    const categoryKey = resolveCategoryKey(getDatasetValue(event, 'categoryKey'));
    if (categoryKey === null) {
      showToast('暂无内容');
      return;
    }
    this._navigating = true;
    void wx.navigateTo({
      url: `/pkg/preview-contact/preview-contact?category_key=${encodeURIComponent(categoryKey)}`,
      fail: (error) => {
        logger.warn('Navigate preview contact failed', { error, categoryKey });
        showToast('暂无内容');
      },
      complete: () => {
        this._navigating = false;
      },
    });
  },

  handleTabTap(event: WechatMiniprogram.BaseEvent) {
    const tabKey = getDatasetValue(event, 'key');
    if (tabKey !== 'index' && tabKey !== 'square' && tabKey !== 'profile') {
      return;
    }
    if (tabKey === this.data.activeTabKey) {
      return;
    }
    void wx.redirectTo({ url: getPreviewTabPath(tabKey) });
  },
});
