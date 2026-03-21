import type { SquareCategory, SquareThemeKey } from '../schemas';

export interface SquareCategoryCard {
  categoryKey: string;
  label: string;
  description?: string;
  themeKey: SquareThemeKey;
  iconName: string;
  iconRef: string;
}

const CATEGORY_KEY_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const ICON_REF_PATTERN = /^tdesign:[a-z0-9-]+$/;
const TDESIGN_PREFIX = 'tdesign:';

export const DEFAULT_SQUARE_ICON = 'chat';

const FALLBACK_CATEGORY_CARDS: readonly SquareCategoryCard[] = [
  {
    categoryKey: 'friend',
    label: '交友',
    description: '结识同频的人，聊聊日常和心情',
    themeKey: 'blue',
    iconName: 'user-filled',
    iconRef: 'tdesign:user-filled',
  },
  {
    categoryKey: 'love',
    label: '恋爱',
    description: '遇见心动对象，把故事慢慢说给TA',
    themeKey: 'pink',
    iconName: 'chat-filled',
    iconRef: 'tdesign:chat-filled',
  },
  {
    categoryKey: 'talk',
    label: '倾诉',
    description: '想说的话有人听，情绪不必独自消化',
    themeKey: 'amber',
    iconName: 'chat',
    iconRef: 'tdesign:chat',
  },
  {
    categoryKey: 'bestie',
    label: '闺蜜',
    description: '找个懂你的闺蜜，分享秘密与小确幸',
    themeKey: 'purple',
    iconName: 'user',
    iconRef: 'tdesign:user',
  },
  {
    categoryKey: 'hobby',
    label: '同好',
    description: '一起聊兴趣爱好，把话题聊到尽兴',
    themeKey: 'green',
    iconName: 'earth',
    iconRef: 'tdesign:earth',
  },
];

const isNonEmptyString = (value: unknown): value is string =>
  typeof value === 'string' && value.trim().length > 0;

export const resolveSquareIconName = (iconRef: string | null | undefined): string => {
  if (!isNonEmptyString(iconRef)) {
    return DEFAULT_SQUARE_ICON;
  }
  const normalized = iconRef.trim();
  if (!ICON_REF_PATTERN.test(normalized)) {
    return DEFAULT_SQUARE_ICON;
  }
  return normalized.slice(TDESIGN_PREFIX.length);
};

export const isValidCategoryKey = (value: unknown): value is string =>
  isNonEmptyString(value) && CATEGORY_KEY_PATTERN.test(value.trim());

export const toSquareCategoryCard = (category: SquareCategory): SquareCategoryCard => ({
  categoryKey: category.category_key,
  label: category.title,
  description: isNonEmptyString(category.description) ? category.description.trim() : undefined,
  themeKey: category.theme_key,
  iconName: resolveSquareIconName(category.icon_ref),
  iconRef: isNonEmptyString(category.icon_ref)
    ? category.icon_ref
    : `tdesign:${DEFAULT_SQUARE_ICON}`,
});

export const buildSquareCategoryCards = (
  categories: readonly SquareCategory[]
): SquareCategoryCard[] => {
  const items: SquareCategoryCard[] = [];
  const seen = new Set<string>();
  categories.forEach((item) => {
    const key = item.category_key.trim();
    if (!isValidCategoryKey(key) || seen.has(key)) {
      return;
    }
    seen.add(key);
    items.push(toSquareCategoryCard(item));
  });

  if (items.length > 0) {
    return items;
  }
  return [];
};

export const getFallbackSquareCategoryCards = (): SquareCategoryCard[] => [
  ...FALLBACK_CATEGORY_CARDS,
];
