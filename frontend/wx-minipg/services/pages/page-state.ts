export type ScreenState = 'booting' | 'ready';
export type ContentVariant = 'data' | 'empty' | 'blank';
export type RefreshState = 'idle' | 'refreshing' | 'degraded';

export interface ScreenModel {
  screenState: ScreenState;
  contentVariant: ContentVariant;
  refreshState: RefreshState;
}

export const createBootingScreenModel = (): ScreenModel => ({
  screenState: 'booting',
  contentVariant: 'blank',
  refreshState: 'idle',
});

export const createReadyScreenModel = (options: {
  contentVariant: ContentVariant;
  refreshState?: RefreshState;
}): ScreenModel => ({
  screenState: 'ready',
  contentVariant: options.contentVariant,
  refreshState: options.refreshState ?? 'idle',
});
