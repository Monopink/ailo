/**
 * Navbar Component - iOS 26 Style Floating Navigation Bar
 *
 * A floating navigation bar with blur effect and semi-transparent background.
 * Designed for immersive experience with content extending behind the navbar.
 *
 * Properties:
 * - title: string - Navigation bar title
 * - showBack: boolean - Whether to show back button
 * - clickable: boolean - Whether title is clickable
 */

Component({
  options: {
    styleIsolation: 'apply-shared',
  },

  properties: {
    title: {
      type: String,
      value: '',
    },
    showBack: {
      type: Boolean,
      value: true,
    },
    clickable: {
      type: Boolean,
      value: false,
    },
  },

  data: {
    statusBarHeight: 0,
    navBarHeight: 44,
    totalHeight: 0,
  },

  lifetimes: {
    attached() {
      this.calculateNavBarHeight();
    },
  },

  methods: {
    calculateNavBarHeight() {
      const systemInfo = wx.getSystemInfoSync();
      const statusBarHeight = systemInfo.statusBarHeight || 0;

      // Get menu button position to calculate navbar height
      const menuButton = wx.getMenuButtonBoundingClientRect();
      const navBarHeight = (menuButton.top - statusBarHeight) * 2 + menuButton.height;
      const totalHeight = statusBarHeight + navBarHeight;

      this.setData({
        statusBarHeight,
        navBarHeight,
        totalHeight,
      });

      // Notify parent component of navbar height
      this.triggerEvent('ready', { totalHeight });
    },

    onBackTap() {
      const pages = getCurrentPages();
      if (pages.length > 1) {
        void wx.navigateBack();
      } else {
        void wx.switchTab({ url: '/pages/index/index' });
      }
      this.triggerEvent('back');
    },

    onTitleTap() {
      if (this.data.clickable) {
        this.triggerEvent('titleclick');
      }
    },
  },
});
