export interface SampleContact {
  id: string;
  nickname: string;
  avatar: string;
  bio: string;
}

export interface Feature {
  id: string;
  title: string;
  description: string;
}

export const SAMPLE_CONTACTS: SampleContact[] = [
  {
    id: 'sample-contact-1',
    nickname: '小敲',
    avatar: '/assets/samples/avatar1.webp',
    bio: '温暖的AI伙伴,喜欢倾听你的故事',
  },
  {
    id: 'sample-contact-2',
    nickname: '阿暖',
    avatar: '/assets/samples/avatar2.webp',
    bio: '想和你一起分享生活的点滴',
  },
  {
    id: 'sample-contact-3',
    nickname: '倾听者',
    avatar: '/assets/samples/avatar3.webp',
    bio: '无论什么烦恼,我都愿意倾听',
  },
  {
    id: 'sample-contact-4',
    nickname: '小闺蜜',
    avatar: '/assets/samples/avatar4.webp',
    bio: '一起逛街、聊八卦、分享秘密',
  },
  {
    id: 'sample-contact-5',
    nickname: '游戏达人',
    avatar: '/assets/samples/avatar5.webp',
    bio: '一起开黑吗?我可是王者段位',
  },
];

export const FEATURES: Feature[] = [
  {
    id: 'chat',
    title: '智能对话',
    description: '保持真人聊天的语气与节奏,随时陪伴',
  },
  {
    id: 'emotion',
    title: '情感共鸣',
    description: '更懂情绪的AI 伙伴,持续回应你的感受',
  },
  {
    id: 'roles',
    title: '多元角色',
    description: '学生、同事、恋人…快速切换最契合的角色',
  },
];
