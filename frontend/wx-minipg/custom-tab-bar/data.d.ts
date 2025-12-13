export interface TabBarItem {
  icon: string;
  selectedIcon: string;
  text: string;
  url: string;
}

declare const TabMenu: ReadonlyArray<TabBarItem>;
export default TabMenu;
