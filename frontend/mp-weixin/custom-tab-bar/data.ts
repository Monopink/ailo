export type TabBarTheme = 'light' | 'dark';

export interface ThemeTabBarItem {
  lightIcon: string;
  lightActiveIcon: string;
  darkIcon: string;
  darkActiveIcon: string;
  iconSize: string;
  text: string;
  pagePath: string;
}

export interface ResolvedTabBarItem {
  icon: string;
  activeIcon: string;
  iconSize: string;
  text: string;
  pagePath: string;
}

const TAB_MENU: ThemeTabBarItem[] = [
  {
    lightIcon: '/assets/icons/chat.svg',
    lightActiveIcon: '/assets/icons/chat-fill.svg',
    darkIcon: '/assets/icons/chat-dark.svg',
    darkActiveIcon: '/assets/icons/chat-fill-dark.svg',
    iconSize: '62rpx',
    text: '聊天',
    pagePath: 'pages/index/index',
  },
  {
    lightIcon: '/assets/icons/discovery.svg',
    lightActiveIcon: '/assets/icons/discovery-fill.svg',
    darkIcon: '/assets/icons/discovery-dark.svg',
    darkActiveIcon: '/assets/icons/discovery-fill-dark.svg',
    iconSize: '62rpx',
    text: '发现',
    pagePath: 'pages/square-entry/square-entry',
  },
  {
    lightIcon: '/assets/icons/profile.svg',
    lightActiveIcon: '/assets/icons/profile-fill.svg',
    darkIcon: '/assets/icons/profile-dark.svg',
    darkActiveIcon: '/assets/icons/profile-fill-dark.svg',
    iconSize: '62rpx',
    text: '我的',
    pagePath: 'pages/profile/profile',
  },
];

const normalizeTheme = (theme?: string): TabBarTheme => (theme === 'dark' ? 'dark' : 'light');

export const getTabMenuByTheme = (theme?: string): ResolvedTabBarItem[] => {
  const currentTheme = normalizeTheme(theme);

  return TAB_MENU.map(({ lightIcon, lightActiveIcon, darkIcon, darkActiveIcon, ...rest }) => ({
    ...rest,
    icon: currentTheme === 'dark' ? darkIcon : lightIcon,
    activeIcon: currentTheme === 'dark' ? darkActiveIcon : lightActiveIcon,
  }));
};

export default TAB_MENU;
