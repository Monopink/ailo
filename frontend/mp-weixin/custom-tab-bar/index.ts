import { getTabMenuByTheme } from './data';
import type { ResolvedTabBarItem, TabBarTheme } from './data';

type ThemeChangeResult = WechatMiniprogram.OnThemeChangeListenerResult;
type ThemeAwareTabBar = WechatMiniprogram.Component.TrivialInstance & {
  themeChangeHandler?: (event: ThemeChangeResult) => void;
  syncTheme: (theme?: string) => void;
};

const normalizeTheme = (theme?: string): TabBarTheme => (theme === 'dark' ? 'dark' : 'light');

const getCurrentTheme = (): TabBarTheme => {
  const appBaseInfo = wx.getAppBaseInfo() as { theme?: string };
  return normalizeTheme(appBaseInfo.theme);
};

const initialTheme = getCurrentTheme();

Component({
  data: {
    active: 0,
    currentTheme: initialTheme,
    list: getTabMenuByTheme(initialTheme),
  },

  lifetimes: {
    attached(): void {
      const component = this as ThemeAwareTabBar;
      const themeChangeHandler = (event: ThemeChangeResult): void => {
        component.syncTheme(event.theme);
      };

      component.themeChangeHandler = themeChangeHandler;
      wx.onThemeChange(themeChangeHandler);
      component.syncTheme();
    },

    detached(): void {
      const component = this as ThemeAwareTabBar;
      if (typeof component.themeChangeHandler === 'function') {
        wx.offThemeChange(component.themeChangeHandler);
      }
    },
  },

  methods: {
    syncTheme(theme?: string): void {
      const currentTheme = normalizeTheme(theme ?? getCurrentTheme());
      if (this.data.currentTheme === currentTheme) {
        return;
      }

      this.setData({
        currentTheme,
        list: getTabMenuByTheme(currentTheme),
      });
    },

    onTabChange(event: WechatMiniprogram.BaseEvent): void {
      const dataset = event.currentTarget.dataset as { index?: unknown } | undefined;
      const indexRaw = dataset?.index;
      const index = typeof indexRaw === 'number' ? indexRaw : Number(indexRaw);
      if (!Number.isInteger(index)) {
        return;
      }

      const item = this.data.list[index];
      if (typeof item === 'undefined' || item.pagePath.length === 0) {
        return;
      }

      this.setData({
        active: index,
      });
      const normalizedUrl = item.pagePath.startsWith('/') ? item.pagePath : `/${item.pagePath}`;
      void wx.switchTab({ url: normalizedUrl });
    },

    init(): void {
      this.syncTheme();

      const page = getCurrentPages().pop();
      if (typeof page === 'undefined' || page.route.length === 0) {
        return;
      }

      const route = page.route;
      const active = this.data.list.findIndex(
        (item: ResolvedTabBarItem) => item.pagePath === route || `/${item.pagePath}` === route
      );
      if (active < 0) {
        return;
      }

      this.setData({
        active,
      });
    },
  },
});
