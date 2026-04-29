import { isNonEmptyString } from './guards';

const LOGIN_PAGE_PATH = '/pages/login/login';
const LOGIN_PROMPT_TITLE = '提示';
const LOGIN_PROMPT_CONTENT = '请先登录后继续';
const LOGIN_PROMPT_CONFIRM_TEXT = '去登录';

export interface PromptLoginRedirectOptions {
  source?: string;
}

const buildLoginUrl = (source?: string): string => {
  if (!isNonEmptyString(source)) {
    return LOGIN_PAGE_PATH;
  }
  return `${LOGIN_PAGE_PATH}?source=${encodeURIComponent(source.trim())}`;
};

const showLoginPrompt = async (): Promise<void> =>
  await new Promise((resolve) => {
    void wx.showModal({
      title: LOGIN_PROMPT_TITLE,
      content: LOGIN_PROMPT_CONTENT,
      showCancel: false,
      confirmText: LOGIN_PROMPT_CONFIRM_TEXT,
      complete: () => resolve(),
    });
  });

export const promptLoginAndRedirect = async (
  options: PromptLoginRedirectOptions = {}
): Promise<void> => {
  await showLoginPrompt();
  void wx.reLaunch({ url: buildLoginUrl(options.source) });
};
