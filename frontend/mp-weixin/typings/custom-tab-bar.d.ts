/**
 * Custom TabBar Component Type Definition
 *
 * Defines the interface for the custom-tab-bar component instance
 * to ensure type safety when calling getTabBar() from pages.
 */

/**
 * Custom TabBar component instance interface
 */
interface CustomTabBarInstance {
  /**
   * Initialize TabBar active state based on current page route
   * Must be called in page's onShow() lifecycle to update active tab indicator
   */
  init(): void;

  /**
   * Tab change event handler
   */
  onTabChange(event: WechatMiniprogram.BaseEvent): void;

  /**
   * Component data
   */
  data: {
    active: number;
    list: Array<{
      icon: string;
      selectedIcon: string;
      text: string;
      url: string;
    }>;
  };

  /**
   * Set component data
   */
  setData(data: Partial<CustomTabBarInstance['data']>): void;
}

/**
 * Extend Page instance type to include getTabBar method
 */
declare namespace WechatMiniprogram {
  interface Page {
    Instance: {
      /**
       * Get custom TabBar instance
       * Returns the custom tab bar component instance if it exists
       */
      getTabBar?(): CustomTabBarInstance | null;
    };
  }
}
