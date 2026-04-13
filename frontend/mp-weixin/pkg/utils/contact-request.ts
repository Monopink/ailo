import { post } from '../../utils/api';
import { isValidCategoryKey } from '../../utils/constants/square';
import defaultLogger from '../../utils/logger';
import { isNonEmptyString } from '../../utils/guards';

const logger = defaultLogger;

const DEFAULT_MESSAGE = '你好，我想添加你为联系人';

interface ContactRequestPromptOptions {
  defaultMessage?: string;
}

interface SendContactRequestOptions {
  qiaoId: string;
  message: string;
  categoryKey?: string | null;
  alias?: string;
  tags?: string[];
}

export function promptContactRequestMessage(
  options: ContactRequestPromptOptions = {}
): Promise<string | null> {
  const { defaultMessage = DEFAULT_MESSAGE } = options;

  return new Promise((resolve) => {
    wx.showModal({
      title: '添加联系人',
      content: '请输入验证消息',
      editable: true,
      placeholderText: '我是...',
      success: (res: WechatMiniprogram.ShowModalSuccessCallbackResult & { content?: string }) => {
        if (!res.confirm) {
          resolve(null);
          return;
        }
        const content = res.content;
        const trimmedContent = isNonEmptyString(content) ? content.trim() : '';
        const finalMessage = trimmedContent.length > 0 ? trimmedContent : defaultMessage;
        resolve(finalMessage);
      },
      fail: (error) => {
        logger.error('contact_request_prompt_failed', { error });
        resolve(null);
      },
    });
  });
}

export async function sendContactRequest({
  qiaoId,
  message,
  categoryKey,
  alias,
  tags,
}: SendContactRequestOptions): Promise<void> {
  if (!isNonEmptyString(qiaoId)) {
    throw new Error('Missing qiaoId');
  }

  const payload: {
    to_qiao_id: string;
    message: string;
    category_key?: string;
    alias?: string;
    tags?: string[];
  } = {
    to_qiao_id: qiaoId,
    message,
  };
  if (isValidCategoryKey(categoryKey)) {
    payload.category_key = categoryKey;
  }
  if (isNonEmptyString(alias)) {
    payload.alias = alias.trim();
  }
  if (Array.isArray(tags) && tags.length > 0) {
    payload.tags = tags.filter((item) => isNonEmptyString(item)).map((item) => item.trim());
  }

  await post('/contact-requests', payload);
  logger.info('contact_request_sent', { qiao_id: qiaoId });
}
