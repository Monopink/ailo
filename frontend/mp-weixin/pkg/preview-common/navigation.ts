import { getTabMenuByTheme } from '../../custom-tab-bar/data';

export type PreviewTabKey = 'index' | 'square' | 'profile';

export interface PreviewTabItem {
  key: PreviewTabKey;
  label: string;
  icon: string;
  activeIcon: string;
  iconSize: string;
  path: string;
}

const PREVIEW_TAB_PATH_BY_PAGE_PATH: Record<string, { key: PreviewTabKey; path: string }> = {
  'pages/index/index': {
    key: 'index',
    path: '/pkg/preview-index/preview-index',
  },
  'pages/square-entry/square-entry': {
    key: 'square',
    path: '/pkg/preview-square/preview-square',
  },
  'pages/profile/profile': {
    key: 'profile',
    path: '/pkg/preview-profile/preview-profile',
  },
};

const resolveCurrentTheme = (): string | undefined => {
  const appBaseInfo = wx.getAppBaseInfo() as { theme?: string };
  return appBaseInfo.theme;
};

export const listPreviewTabItems = (): PreviewTabItem[] => {
  return getTabMenuByTheme(resolveCurrentTheme())
    .map((item) => {
      const mapping = PREVIEW_TAB_PATH_BY_PAGE_PATH[item.pagePath];
      if (typeof mapping === 'undefined') {
        return null;
      }
      return {
        key: mapping.key,
        label: item.text,
        icon: item.icon,
        activeIcon: item.activeIcon,
        iconSize: item.iconSize,
        path: mapping.path,
      };
    })
    .filter((item): item is PreviewTabItem => item !== null);
};

export const getPreviewTabPath = (key: PreviewTabKey): string =>
  listPreviewTabItems().find((item) => item.key === key)?.path ??
  '/pkg/preview-index/preview-index';
