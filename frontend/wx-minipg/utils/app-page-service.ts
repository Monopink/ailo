import { requestValidated } from './api';
import { getLogger } from './logger';
import { AppPageSchema, type AppPage } from './schemas';

const logger = getLogger('AppPageService');
const PAGE_KEY_PATTERN = /^[a-z][a-z0-9_]{0,63}$/;

export interface AppPageViewModel {
  pageKey: string;
  title: string;
  contentRendered: string;
}

const toViewModel = (page: AppPage): AppPageViewModel => ({
  pageKey: page.page_key,
  title: page.title,
  contentRendered: page.content_rendered,
});

const normalizePageKey = (pageKey: string): string => {
  const normalized = pageKey.trim().toLowerCase();
  if (!PAGE_KEY_PATTERN.test(normalized)) {
    throw new Error('invalid page key');
  }
  return normalized;
};

export async function fetchAppPage(pageKey: string): Promise<AppPageViewModel> {
  const normalizedPageKey = normalizePageKey(pageKey);
  logger.info('Loading app page', { pageKey: normalizedPageKey });
  const page = await requestValidated(AppPageSchema, {
    url: `/pages/${normalizedPageKey}`,
    method: 'GET',
    auth: false,
    retryAuth: false,
  });
  return toViewModel(page);
}
