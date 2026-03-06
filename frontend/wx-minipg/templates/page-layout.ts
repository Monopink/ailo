/**
 * Page Layout Template Utilities
 * Runtime module that exposes `PageLayoutData` interface
 * and helper to build default states for the shared template.
 */

export interface PageLayoutData {
  /** New state model consumed by page-layout */
  screenModel: {
    screenState: 'booting' | 'ready';
    contentVariant: 'data' | 'empty' | 'blank';
    refreshState: 'idle' | 'refreshing' | 'degraded';
  };
  /** Message displayed when contentVariant=empty */
  emptyMessage: string;
  /** Whether the footer slot should be visible */
  hasFooter: boolean;
  /** Optional scroll-into-view target ID for content area */
  contentScrollIntoView?: string;
  /** Whether content scroll should animate */
  contentScrollWithAnimation?: boolean;
}

type ScreenModel = PageLayoutData['screenModel'];
type PageLayoutInitOptions = Omit<Partial<PageLayoutData>, 'screenModel'> & {
  screenModel: ScreenModel;
};

/**
 * Helper to create initial layout data.
 * `screenModel` must be explicitly provided by the page.
 */
export function createPageLayoutData(options: PageLayoutInitOptions): PageLayoutData {
  const { screenModel, ...restOptions } = options;
  return {
    screenModel,
    emptyMessage: '',
    hasFooter: false,
    contentScrollIntoView: '',
    contentScrollWithAnimation: true,
    ...restOptions,
  };
}
