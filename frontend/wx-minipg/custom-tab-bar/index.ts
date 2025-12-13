import TabMenu from './data';
import type { TabBarItem } from './data';

Component({
  data: {
    active: 0,
    list: TabMenu,
  },

  methods: {
    onTabChange(event: WechatMiniprogram.BaseEvent): void {
      const index = event.currentTarget.dataset.index as number;
      this.setData({ active: index });
      let url = this.data.list[index]?.url;
      // Handle URL path format - ensure it starts with '/'
      if (!url.startsWith('/')) {
        url = '/' + url;
      }
      void wx.switchTab({ url });
    },

    init(): void {
      const page = getCurrentPages().pop();
      const route = page ? page.route : '';
      const active = this.data.list.findIndex(
        (item: TabBarItem) => item.url === route || `/${item.url}` === route
      );
      this.setData({ active: active === -1 ? 0 : active });
    },
  },
});
