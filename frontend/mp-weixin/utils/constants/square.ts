import type { SquareCategory, SquareThemeKey } from '../schemas';

export type SquareThemeClass = 'friend' | 'love' | 'talk' | 'bestie' | 'hobby';

export interface SquareCategoryCard {
  categoryKey: string;
  label: string;
  description?: string;
  themeClass: SquareThemeClass;
  themeKey: SquareThemeKey;
  iconName: string;
  iconRef: string;
}

const CATEGORY_KEY_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const ICON_REF_PATTERN = /^tdesign:[a-z0-9-]+$/;
const TDESIGN_PREFIX = 'tdesign:';

export const DEFAULT_SQUARE_ICON = 'chat';

// Source of truth: backend/app/enums/common.py -> SquareCategoryTheme
export const SQUARE_THEME_KEYS: readonly SquareThemeKey[] = [
  'ocean',
  'sky',
  'mint',
  'forest',
  'lime',
  'amber',
  'sunset',
  'rose',
  'grape',
  'slate',
];

const THEME_CLASS_BY_THEME_KEY: Record<SquareThemeKey, SquareThemeClass> = {
  ocean: 'friend',
  sky: 'hobby',
  mint: 'talk',
  forest: 'hobby',
  lime: 'friend',
  amber: 'love',
  sunset: 'love',
  rose: 'bestie',
  grape: 'bestie',
  slate: 'talk',
};

const FALLBACK_CATEGORY_CARDS: readonly SquareCategoryCard[] = [
  {
    categoryKey: 'friend',
    label: '交友',
    description: '结识同频的人，聊聊日常和心情',
    themeClass: 'friend',
    themeKey: 'ocean',
    iconName: 'user-filled',
    iconRef: 'tdesign:user-filled',
  },
  {
    categoryKey: 'love',
    label: '恋爱',
    description: '遇见心动对象，把故事慢慢说给TA',
    themeClass: 'love',
    themeKey: 'amber',
    iconName: 'chat-filled',
    iconRef: 'tdesign:chat-filled',
  },
  {
    categoryKey: 'talk',
    label: '倾诉',
    description: '想说的话有人听，情绪不必独自消化',
    themeClass: 'talk',
    themeKey: 'grape',
    iconName: 'chat',
    iconRef: 'tdesign:chat',
  },
  {
    categoryKey: 'bestie',
    label: '闺蜜',
    description: '找个懂你的闺蜜，分享秘密与小确幸',
    themeClass: 'bestie',
    themeKey: 'rose',
    iconName: 'user',
    iconRef: 'tdesign:user',
  },
  {
    categoryKey: 'hobby',
    label: '同好',
    description: '一起聊兴趣爱好，把话题聊到尽兴',
    themeClass: 'hobby',
    themeKey: 'sky',
    iconName: 'earth',
    iconRef: 'tdesign:earth',
  },
];

const isNonEmptyString = (value: unknown): value is string =>
  typeof value === 'string' && value.trim().length > 0;

const SQUARE_THEME_KEY_SET = new Set<SquareThemeKey>(SQUARE_THEME_KEYS);

const isSquareThemeKey = (value: unknown): value is SquareThemeKey =>
  typeof value === 'string' && SQUARE_THEME_KEY_SET.has(value as SquareThemeKey);

const normalizeThemeClass = (themeKey: string): SquareThemeClass =>
  isSquareThemeKey(themeKey) ? THEME_CLASS_BY_THEME_KEY[themeKey] : 'friend';

const normalizeThemeKey = (themeKey: string): SquareThemeKey =>
  isSquareThemeKey(themeKey) ? themeKey : 'ocean';

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
  themeClass: normalizeThemeClass(category.theme_key),
  themeKey: normalizeThemeKey(category.theme_key),
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
