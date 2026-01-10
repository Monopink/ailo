import TabMenu from './data';
import type { TabBarItem } from './data';
import { isDefined } from '../utils/guards';

Component({
  data: {
    active: 0,
    list: TabMenu,
  },

  methods: {
    onTabChange(event: WechatMiniprogram.BaseEvent): void {
      const index = event.currentTarget.dataset.index as number;
      this.setData({ active: index });
      const rawUrl = this.data.list[index]?.url ?? '';
      const normalizedUrl = rawUrl.startsWith('/') ? rawUrl : `/${rawUrl}`;
      void wx.switchTab({ url: normalizedUrl });
    },

    init(): void {
      const page = getCurrentPages().pop();
      const route = isDefined(page) ? page.route : '';
      const active = this.data.list.findIndex(
        (item: TabBarItem) => item.url === route || `/${item.url}` === route
      );
      this.setData({ active: active === -1 ? 0 : active });
    },
  },
});
