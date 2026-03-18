/**
 * Square discovery constants and enums
 *
 * IMPORTANT: All enum values MUST match backend definitions
 */

/** Square category enum - MUST match backend SquareCategory */
export const SQUARE_CATEGORY = {
  FRIEND: 1,
  LOVE: 2,
  TALK: 3,
  BESTIE: 4,
  HOBBY: 5,
} as const;

export type SquareCategory = (typeof SQUARE_CATEGORY)[keyof typeof SQUARE_CATEGORY];

/** Square category labels for UI */
export const SQUARE_CATEGORY_LABELS: Record<SquareCategory, string> = {
  [SQUARE_CATEGORY.FRIEND]: '交友',
  [SQUARE_CATEGORY.LOVE]: '恋爱',
  [SQUARE_CATEGORY.TALK]: '倾诉',
  [SQUARE_CATEGORY.BESTIE]: '闺蜜',
  [SQUARE_CATEGORY.HOBBY]: '同好',
};

/** Square category list for tabs */
export const SQUARE_CATEGORY_ITEMS = [
  {
    key: SQUARE_CATEGORY.FRIEND,
    label: SQUARE_CATEGORY_LABELS[SQUARE_CATEGORY.FRIEND],
    theme: 'friend',
  },
  {
    key: SQUARE_CATEGORY.LOVE,
    label: SQUARE_CATEGORY_LABELS[SQUARE_CATEGORY.LOVE],
    theme: 'love',
  },
  {
    key: SQUARE_CATEGORY.TALK,
    label: SQUARE_CATEGORY_LABELS[SQUARE_CATEGORY.TALK],
    theme: 'talk',
  },
  {
    key: SQUARE_CATEGORY.BESTIE,
    label: SQUARE_CATEGORY_LABELS[SQUARE_CATEGORY.BESTIE],
    theme: 'bestie',
  },
  {
    key: SQUARE_CATEGORY.HOBBY,
    label: SQUARE_CATEGORY_LABELS[SQUARE_CATEGORY.HOBBY],
    theme: 'hobby',
  },
] as const;

export type SquareCategoryItem = (typeof SQUARE_CATEGORY_ITEMS)[number];

export type SquareEntryTheme = 'friend' | 'love' | 'talk' | 'bestie' | 'hobby';

/** Square entry cards for the entry page */
export const SQUARE_ENTRY_CARDS = [
  {
    key: 'friend',
    theme: 'friend',
    category: SQUARE_CATEGORY.FRIEND,
    title: '交友',
    description: '结识同频的人，聊聊日常和心情',
    icon: 'user-filled',
  },
  {
    key: 'love',
    theme: 'love',
    category: SQUARE_CATEGORY.LOVE,
    title: '恋爱',
    description: '遇见心动对象，把故事慢慢说给TA',
    icon: 'chat-filled',
  },
  {
    key: 'talk',
    theme: 'talk',
    category: SQUARE_CATEGORY.TALK,
    title: '倾诉',
    description: '想说的话有人听，情绪不必独自消化',
    icon: 'chat',
  },
  {
    key: 'bestie',
    theme: 'bestie',
    category: SQUARE_CATEGORY.BESTIE,
    title: '闺蜜',
    description: '找个懂你的闺蜜，分享秘密与小确幸',
    icon: 'user',
  },
  {
    key: 'hobby',
    theme: 'hobby',
    category: SQUARE_CATEGORY.HOBBY,
    title: '同好',
    description: '一起聊兴趣爱好，把话题聊到尽兴',
    icon: 'earth',
  },
] as const;

export type SquareEntryCard = (typeof SQUARE_ENTRY_CARDS)[number];
