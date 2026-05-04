import { ASSET_CONFIG } from '../../utils/config';
import { type SquareCategoryCard } from '../../utils/constants/square';

export interface PreviewGuestProfile {
  qiaoId: string;
  nickname: string;
  bio: string;
  region: string;
  avatarUrl: string;
}

export interface PreviewSquareContact {
  qiaoId: string;
  nickname: string;
  bio: string;
  categoryKey: string;
  avatarUrl: string;
  added: boolean;
}

export interface PreviewConversation {
  id: string;
  title: string;
  lastMessage: string;
  updatedAtLabel: string;
  unread: number;
}

export interface PreviewMessage {
  id: string;
  conversationId: string;
  sender: 'guest' | 'peer';
  text: string;
  timeLabel: string;
}

const COS_ASSET_BASE_URL = ASSET_CONFIG.cosBaseUrl;

const AVATARS = [
  `${COS_ASSET_BASE_URL}/demo/avatars/1.webp`,
  `${COS_ASSET_BASE_URL}/demo/avatars/2.webp`,
  `${COS_ASSET_BASE_URL}/demo/avatars/3.webp`,
  `${COS_ASSET_BASE_URL}/demo/avatars/4.webp`,
  `${COS_ASSET_BASE_URL}/demo/avatars/5.webp`,
  `${COS_ASSET_BASE_URL}/demo/avatars/6.webp`,
] as const;

const pickAvatar = (index: number): string => AVATARS[Math.abs(index) % AVATARS.length];

const buildSessionGuestQiaoId = (): string => {
  const randomNumber = Math.floor(Math.random() * 90000000) + 10000000;
  return `guest_${randomNumber}`;
};

const PREVIEW_CATEGORIES: readonly SquareCategoryCard[] = [
  {
    categoryKey: 'friend',
    label: '交友',
    description: '认识同频的人，聊聊日常和心情',
    themeKey: 'blue',
    iconName: 'user-filled',
    iconRef: 'tdesign:user-filled',
  },
  {
    categoryKey: 'talk',
    label: '倾诉',
    description: '把想说的话说出来，会有人认真倾听',
    themeKey: 'orange',
    iconName: 'chat',
    iconRef: 'tdesign:chat',
  },
  {
    categoryKey: 'hobby',
    label: '同好',
    description: '交流兴趣爱好，找到有话题的人',
    themeKey: 'green',
    iconName: 'earth',
    iconRef: 'tdesign:earth',
  },
];

const INITIAL_SQUARE_CONTACTS: readonly PreviewSquareContact[] = [
  {
    qiaoId: 'square_10001',
    nickname: '阿周',
    bio: '下班后喜欢聊日常，也愿意听你分享今天发生的事。',
    categoryKey: 'friend',
    avatarUrl: pickAvatar(0),
    added: false,
  },
  {
    qiaoId: 'square_10002',
    nickname: '小范同学',
    bio: '社恐但真诚，熟了以后话会多一点。',
    categoryKey: 'friend',
    avatarUrl: pickAvatar(1),
    added: false,
  },
  {
    qiaoId: 'square_10003',
    nickname: '晚班护士周姐',
    bio: '轮班后常常睡不着，想找人聊聊情绪。',
    categoryKey: 'talk',
    avatarUrl: pickAvatar(2),
    added: false,
  },
  {
    qiaoId: 'square_10004',
    nickname: '米粒',
    bio: '情绪上来的时候，也可以先慢慢说。',
    categoryKey: 'talk',
    avatarUrl: pickAvatar(3),
    added: false,
  },
  {
    qiaoId: 'square_10005',
    nickname: '骑行小杨',
    bio: '周末短途骑行，想找人交流路线和装备。',
    categoryKey: 'hobby',
    avatarUrl: pickAvatar(4),
    added: false,
  },
  {
    qiaoId: 'square_10006',
    nickname: '书店阿梅',
    bio: '常逛独立书店，愿意交换阅读清单。',
    categoryKey: 'hobby',
    avatarUrl: pickAvatar(5),
    added: false,
  },
];

const INITIAL_CONVERSATIONS: readonly PreviewConversation[] = [];

const INITIAL_MESSAGES: readonly PreviewMessage[] = [];

const PREVIEW_GUEST_PROFILE: PreviewGuestProfile = {
  qiaoId: buildSessionGuestQiaoId(),
  nickname: '游客',
  bio: '',
  region: '',
  avatarUrl: pickAvatar(0),
};

const squareContactsState: PreviewSquareContact[] = INITIAL_SQUARE_CONTACTS.map((item) => ({
  ...item,
}));
const conversationsState: PreviewConversation[] = INITIAL_CONVERSATIONS.map((item) => ({
  ...item,
}));
const messagesState: PreviewMessage[] = INITIAL_MESSAGES.map((item) => ({ ...item }));

const nowLabel = (): string => {
  const now = new Date();
  const hh = String(now.getHours()).padStart(2, '0');
  const mm = String(now.getMinutes()).padStart(2, '0');
  return `${hh}:${mm}`;
};

export const previewMockData = {
  getGuestProfile(): PreviewGuestProfile {
    return { ...PREVIEW_GUEST_PROFILE };
  },

  listCategories(): SquareCategoryCard[] {
    return PREVIEW_CATEGORIES.map((item) => ({ ...item }));
  },

  listSquareContacts(categoryKey: string): PreviewSquareContact[] {
    return squareContactsState
      .filter((item) => item.categoryKey === categoryKey)
      .map((item) => ({ ...item }));
  },

  listContacts(): PreviewSquareContact[] {
    return squareContactsState.map((item) => ({ ...item }));
  },

  addContact(qiaoId: string): boolean {
    const target = squareContactsState.find((item) => item.qiaoId === qiaoId);
    if (target === undefined) {
      return false;
    }
    target.added = true;
    return true;
  },

  listConversations(): PreviewConversation[] {
    return conversationsState.map((item) => ({ ...item }));
  },

  listConversationMessages(conversationId: string): PreviewMessage[] {
    return messagesState
      .filter((item) => item.conversationId === conversationId)
      .map((item) => ({ ...item }));
  },

  appendGuestMessage(conversationId: string, text: string): void {
    const messageText = text.trim();
    if (messageText === '') {
      return;
    }
    const messageId = `msg_guest_${Date.now()}`;
    const createdAt = nowLabel();
    messagesState.push({
      id: messageId,
      conversationId,
      sender: 'guest',
      text: messageText,
      timeLabel: createdAt,
    });

    const peerReply = '收到，你的消息已发送。';
    messagesState.push({
      id: `${messageId}_reply`,
      conversationId,
      sender: 'peer',
      text: peerReply,
      timeLabel: createdAt,
    });

    const targetConversation = conversationsState.find((item) => item.id === conversationId);
    if (targetConversation !== undefined) {
      targetConversation.lastMessage = peerReply;
      targetConversation.updatedAtLabel = createdAt;
    }
  },
};
