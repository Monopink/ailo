import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { getLogger } from '../../utils/logger';
import {
  isValidCategoryKey,
  type SquareCategoryCard,
} from '../../utils/constants/square';
import { isNonEmptyString } from '../../utils/guards';

const logger = getLogger('SquareDemo');

interface SquareDemoContactViewModel {
  qiao_id: string;
  nickname: string;
  avatar_url: string;
  bio: string;
  categoryKey: string;
}

const COS_ASSET_BASE_URL = 'https://cortex.qiaoqiaoai.cn';
const AVATAR_PLACEHOLDER_URL = `${COS_ASSET_BASE_URL}/assets/avatar-placeholder.webp`;
const MORE_CATEGORY_KEY = 'more';
const PREVIEW_COUNT = 5;
const DEMO_CATEGORIES: readonly SquareCategoryCard[] = [
  {
    categoryKey: 'friend',
    label: '交友',
    themeKey: 'blue',
    iconName: 'user-filled',
    iconRef: 'tdesign:user-filled',
  },
  {
    categoryKey: 'talk',
    label: '倾诉',
    themeKey: 'orange',
    iconName: 'chat',
    iconRef: 'tdesign:chat',
  },
  {
    categoryKey: 'hobby',
    label: '同好',
    themeKey: 'green',
    iconName: 'earth',
    iconRef: 'tdesign:earth',
  },
  {
    categoryKey: MORE_CATEGORY_KEY,
    label: '登录发现更多分类',
    themeKey: 'charcoal',
    iconName: 'lock-on',
    iconRef: 'tdesign:lock-on',
  },
];

const DEMO_AVATARS: readonly string[] = [
  `${COS_ASSET_BASE_URL}/demo/avatars/1.webp`,
  `${COS_ASSET_BASE_URL}/demo/avatars/2.webp`,
  `${COS_ASSET_BASE_URL}/demo/avatars/3.webp`,
  `${COS_ASSET_BASE_URL}/demo/avatars/4.webp`,
  `${COS_ASSET_BASE_URL}/demo/avatars/5.webp`,
  `${COS_ASSET_BASE_URL}/demo/avatars/6.webp`,
];

const pickDemoAvatar = (index: number): string => {
  const normalized = Math.abs(index);
  return DEMO_AVATARS[normalized % DEMO_AVATARS.length];
};

const DEMO_CONTACTS: readonly SquareDemoContactViewModel[] = [
  {
    qiao_id: 'demo_10001',
    nickname: '阿周',
    avatar_url: pickDemoAvatar(0),
    bio: '下班后喜欢聊日常，也愿意听你分享今天发生的事。',
    categoryKey: 'friend',
  },
  {
    qiao_id: 'demo_10002',
    nickname: '李会计',
    avatar_url: pickDemoAvatar(1),
    bio: '最近压力有点大，想找人互相倾诉、互相打气。',
    categoryKey: 'talk',
  },
  {
    qiao_id: 'demo_10003',
    nickname: '陈老师',
    avatar_url: pickDemoAvatar(2),
    bio: '你慢慢说，我会认真听，不急着下结论。',
    categoryKey: 'talk',
  },
  {
    qiao_id: 'demo_10004',
    nickname: '林老师',
    avatar_url: pickDemoAvatar(3),
    bio: '喜欢把复杂事情说简单，聊学习和生活都可以。',
    categoryKey: 'friend',
  },
  {
    qiao_id: 'demo_10005',
    nickname: '阿梁电影',
    avatar_url: pickDemoAvatar(4),
    bio: '每周看两部片，喜欢聊剧情和角色。',
    categoryKey: 'hobby',
  },
  {
    qiao_id: 'demo_10006',
    nickname: '手冲咖啡吴叔',
    avatar_url: pickDemoAvatar(5),
    bio: '在家折腾咖啡器具，欢迎交流冲煮参数。',
    categoryKey: 'hobby',
  },
  {
    qiao_id: 'demo_10007',
    nickname: '晨跑老赵',
    avatar_url: pickDemoAvatar(6),
    bio: '早起跑步多年，想找人互相打卡、互相督促。',
    categoryKey: 'friend',
  },
  {
    qiao_id: 'demo_10008',
    nickname: '小范同学',
    avatar_url: pickDemoAvatar(7),
    bio: '正在准备考试，偶尔想找人互相鼓励。',
    categoryKey: 'friend',
  },
  {
    qiao_id: 'demo_10009',
    nickname: '阿婷',
    avatar_url: pickDemoAvatar(8),
    bio: '爱记手账，喜欢分享小确幸。',
    categoryKey: 'friend',
  },
  {
    qiao_id: 'demo_10010',
    nickname: '老胡',
    avatar_url: pickDemoAvatar(9),
    bio: '做事慢一点更稳，愿意聊规划和执行。',
    categoryKey: 'friend',
  },
  {
    qiao_id: 'demo_10011',
    nickname: '小陈',
    avatar_url: pickDemoAvatar(10),
    bio: '社恐但真诚，熟了以后话会多一点。',
    categoryKey: 'friend',
  },
  {
    qiao_id: 'demo_10012',
    nickname: '晓雯',
    avatar_url: pickDemoAvatar(11),
    bio: '喜欢有来有回的聊天，不爱尬聊。',
    categoryKey: 'friend',
  },
  {
    qiao_id: 'demo_10013',
    nickname: '晚班护士周姐',
    avatar_url: pickDemoAvatar(12),
    bio: '轮班之后常常睡不着，想找人聊聊情绪。',
    categoryKey: 'talk',
  },
  {
    qiao_id: 'demo_10014',
    nickname: '阿楠',
    avatar_url: pickDemoAvatar(13),
    bio: '有时想把心事说出来，听听不同角度。',
    categoryKey: 'talk',
  },
  {
    qiao_id: 'demo_10015',
    nickname: '周末树洞',
    avatar_url: pickDemoAvatar(14),
    bio: '工作日忙，周末在线，适合慢慢聊。',
    categoryKey: 'talk',
  },
  {
    qiao_id: 'demo_10016',
    nickname: '沈姐',
    avatar_url: pickDemoAvatar(15),
    bio: '经历过低谷，更懂得先接住情绪再讲道理。',
    categoryKey: 'talk',
  },
  {
    qiao_id: 'demo_10017',
    nickname: '听你说的老郑',
    avatar_url: pickDemoAvatar(16),
    bio: '你先说，我不打断，聊完再一起想办法。',
    categoryKey: 'talk',
  },
  {
    qiao_id: 'demo_10018',
    nickname: '米粒',
    avatar_url: pickDemoAvatar(17),
    bio: '情绪上头时也别怕，先把想法讲出来。',
    categoryKey: 'talk',
  },
  {
    qiao_id: 'demo_10019',
    nickname: '骑行小杨',
    avatar_url: pickDemoAvatar(18),
    bio: '周末短途骑行，想找同城车友交流路线。',
    categoryKey: 'hobby',
  },
  {
    qiao_id: 'demo_10020',
    nickname: '木工老岳',
    avatar_url: pickDemoAvatar(19),
    bio: '喜欢做小木作，最近在做书架和收纳盒。',
    categoryKey: 'hobby',
  },
  {
    qiao_id: 'demo_10021',
    nickname: '书店阿梅',
    avatar_url: pickDemoAvatar(20),
    bio: '常逛独立书店，愿意交换阅读清单。',
    categoryKey: 'hobby',
  },
  {
    qiao_id: 'demo_10022',
    nickname: '烘焙韩姐',
    avatar_url: pickDemoAvatar(21),
    bio: '面包和饼干都在学，欢迎互相分享配方。',
    categoryKey: 'hobby',
  },
  {
    qiao_id: 'demo_10023',
    nickname: '钓鱼老罗',
    avatar_url: pickDemoAvatar(22),
    bio: '爱研究线组和饵料，聊装备不聊玄学。',
    categoryKey: 'hobby',
  },
  {
    qiao_id: 'demo_10024',
    nickname: '园艺阿沈',
    avatar_url: pickDemoAvatar(23),
    bio: '阳台种花种菜，失败经验比成功经验更多。',
    categoryKey: 'hobby',
  },
];

interface SquareDemoPageData {
  pageLayoutData: PageLayoutData;
  categories: SquareCategoryCard[];
  currentCategoryKey: string;
  contacts: SquareDemoContactViewModel[];
  contactsPreview: SquareDemoContactViewModel[];
  hasMore: boolean;
  avatarPlaceholderUrl: string;
}

interface SquareDemoPageCustom {
  applyCategories(categories: SquareCategoryCard[], preferredKey?: string | null): boolean;
  selectCategory(event: WechatMiniprogram.TouchEvent): void;
  handleContactTap(event: WechatMiniprogram.BaseEvent): void;
  handleCategoryMoreTap(): void;
  handleViewMoreTap(): void;
  applyFilteredContacts(categoryKey: string): void;
}

const buildPageLayoutScreenModelPayload = (
  screenState: 'ready',
  contentVariant: 'data' | 'empty',
  refreshState: 'idle'
): Record<string, unknown> => ({
  'pageLayoutData.screenModel': {
    screenState,
    contentVariant,
    refreshState,
  },
});

const getDatasetValue = (event: WechatMiniprogram.BaseEvent, key: string): unknown => {
  const dataset = event.currentTarget.dataset as Record<string, unknown> | undefined;
  return dataset?.[key];
};

const toCategoryKey = (value: unknown): string | null => {
  if (typeof value === 'string' && isValidCategoryKey(value)) {
    return value;
  }
  return null;
};

const toStringValue = (value: unknown): string | undefined => {
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number') {
    return String(value);
  }
  return undefined;
};

const resolveInitialCategoryKey = (categories: readonly SquareCategoryCard[]): string => {
  const first = categories.find((item) => item.categoryKey !== MORE_CATEGORY_KEY);
  return first?.categoryKey ?? 'friend';
};

Page<SquareDemoPageData, SquareDemoPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
      emptyMessage: '暂无内容',
    }),
    categories: [...DEMO_CATEGORIES],
    currentCategoryKey: resolveInitialCategoryKey(DEMO_CATEGORIES),
    contacts: [],
    contactsPreview: [],
    hasMore: false,
    avatarPlaceholderUrl: AVATAR_PLACEHOLDER_URL,
  },

  applyCategories(categories, preferredKey = null) {
    const normalized = categories.filter((item) => isValidCategoryKey(item.categoryKey));
    if (normalized.length === 0) {
      return false;
    }

    const availableKeys = new Set(normalized.map((item) => item.categoryKey));
    const currentKey = this.data.currentCategoryKey;
    let nextKey = currentKey;
    const preferred =
      typeof preferredKey === 'string' && preferredKey.length > 0 ? preferredKey : null;

    if (preferred !== null && preferred !== MORE_CATEGORY_KEY && availableKeys.has(preferred)) {
      nextKey = preferred;
    } else if (!availableKeys.has(currentKey) || currentKey === MORE_CATEGORY_KEY) {
      nextKey = resolveInitialCategoryKey(normalized);
    }

    this.setData({
      categories: normalized,
      currentCategoryKey: nextKey,
    });
    return true;
  },

  onLoad(options?: Record<string, string | undefined>) {
    const requestedCategory = options?.category_key;
    const preferredKey =
      isNonEmptyString(requestedCategory) && isValidCategoryKey(requestedCategory)
        ? requestedCategory
        : null;

    if (preferredKey === MORE_CATEGORY_KEY) {
      this.handleCategoryMoreTap();
    }

    this.applyCategories([...DEMO_CATEGORIES], preferredKey === MORE_CATEGORY_KEY ? null : preferredKey);
    this.applyFilteredContacts(this.data.currentCategoryKey);
  },

  applyFilteredContacts(categoryKey) {
    const contacts = DEMO_CONTACTS.filter((item) => item.categoryKey === categoryKey);
    const contactsPreview = contacts.slice(0, PREVIEW_COUNT);
    this.setData({
      contacts,
      contactsPreview,
      hasMore: contacts.length > PREVIEW_COUNT,
      ...buildPageLayoutScreenModelPayload('ready', contacts.length === 0 ? 'empty' : 'data', 'idle'),
    });
  },

  selectCategory(event) {
    const categoryKey = toCategoryKey(getDatasetValue(event, 'categoryKey'));
    if (categoryKey === null || categoryKey === this.data.currentCategoryKey) {
      return;
    }

    if (categoryKey === MORE_CATEGORY_KEY) {
      this.handleCategoryMoreTap();
      return;
    }

    const exists = this.data.categories.some((item) => item.categoryKey === categoryKey);
    if (!exists) {
      return;
    }

    this.setData({
      currentCategoryKey: categoryKey,
    });
    this.applyFilteredContacts(categoryKey);
  },

  handleCategoryMoreTap() {
    logger.info('Demo category more tapped');
    void wx.navigateTo({ url: '/pages/login/login?source=demo' });
  },

  handleViewMoreTap() {
    const categoryKey = this.data.currentCategoryKey;
    logger.info('Demo view more tapped', { categoryKey });
    void wx.navigateTo({
      url: `/pages/login/login?source=demo_more&category_key=${encodeURIComponent(categoryKey)}`,
    });
  },

  handleContactTap(event) {
    const qiaoId = toStringValue(getDatasetValue(event, 'id'));
    if (!isNonEmptyString(qiaoId)) {
      return;
    }
    logger.info('Demo contact tapped', { qiaoId });
    void wx.navigateTo({ url: '/pages/login/login?source=demo' });
  },
});
