import TabMenu from './data';
import type { TabBarItem } from './data';

Component({
  data: {
    active: 0,
    list: TabMenu,
  },

  methods: {
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
      const page = getCurrentPages().pop();
      if (typeof page === 'undefined' || page.route.length === 0) {
        return;
      }

      const route = page.route;
      const active = this.data.list.findIndex(
        (item: TabBarItem) => item.pagePath === route || `/${item.pagePath}` === route
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
