/**
 * Page Layout Template Utilities
 * Runtime module that exposes `PageLayoutData` interface
 * and helper to build default states for the shared template.
 */

export interface PageLayoutData {
  /** Whether the page is currently loading */
  isLoading: boolean;
  /** Whether the page is in error state */
  hasError: boolean;
  /** Error message displayed when hasError=true */
  errorMessage: string;
  /** Whether the data set is empty */
  isEmpty: boolean;
  /** Message displayed when isEmpty=true */
  emptyMessage: string;
  /** Whether the footer slot should be visible */
  hasFooter: boolean;
  /** Optional scroll-into-view target ID for content area */
  contentScrollIntoView?: string;
  /** Whether content scroll should animate */
  contentScrollWithAnimation?: boolean;
}

/**
 * Helper to create initial layout data with sensible defaults.
 * Allows overriding partial fields for specific pages.
 */
export function createPageLayoutData(options: Partial<PageLayoutData> = {}): PageLayoutData {
  return {
    isLoading: false,
    hasError: false,
    errorMessage: '',
    isEmpty: false,
    emptyMessage: '暂无数据',
    hasFooter: false,
    contentScrollIntoView: '',
    contentScrollWithAnimation: true,
    ...options,
  };
}
