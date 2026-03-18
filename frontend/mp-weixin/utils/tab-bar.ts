/**
 * TabBar Utilities
 *
 * Provides type-safe utilities for interacting with custom TabBar component.
 */

/**
 * Custom TabBar instance interface
 */
interface TabBarInstance {
  init: () => void;
}

/**
 * Type guard to check if value is a valid TabBar instance with init method
 */
const isTabBarInstance = (value: unknown): value is TabBarInstance =>
  typeof value === 'object' &&
  value !== null &&
  typeof (value as TabBarInstance).init === 'function';

/**
 * Initialize custom TabBar active state
 *
 * This function should be called in the onShow() lifecycle of any page
 * that uses custom TabBar to ensure the correct tab is highlighted.
 *
 * @param pageInstance - The page instance (use `this` from Page context)
 *
 * @example
 * ```typescript
 * Page({
 *   onShow() {
 *     initTabBar(this);
 *   }
 * });
 * ```
 */
export const initTabBar = (
  pageInstance: WechatMiniprogram.Page.Instance<
    WechatMiniprogram.IAnyObject,
    WechatMiniprogram.IAnyObject
  >
): void => {
  // Type guard: check if getTabBar method exists
  if (typeof pageInstance.getTabBar !== 'function') {
    return;
  }

  // Get TabBar instance
  const tabBar = pageInstance.getTabBar();

  // Type guard: check if TabBar instance is valid and has init method
  if (!isTabBarInstance(tabBar)) {
    return;
  }

  // Call init() with correct this binding
  tabBar.init();
};
