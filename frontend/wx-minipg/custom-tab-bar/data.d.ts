export interface TabBarItem {
  icon: string;
  activeIcon: string;
  text: string;
  pagePath: string;
}

declare const TabMenu: ReadonlyArray<TabBarItem>;
export default TabMenu;
