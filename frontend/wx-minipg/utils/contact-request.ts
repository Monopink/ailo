import { post } from './api';
import defaultLogger from './logger';
import { isNonEmptyString } from './guards';

const logger = defaultLogger;

const DEFAULT_MESSAGE = '你好，我想添加你为联系人';

interface ContactRequestPromptOptions {
  defaultMessage?: string;
}

interface SendContactRequestOptions {
  qiaoId: string;
  message: string;
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
        const finalMessage =
          trimmedContent.length > 0 ? trimmedContent : defaultMessage;
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
}: SendContactRequestOptions): Promise<void> {
  if (!isNonEmptyString(qiaoId)) {
    throw new Error('Missing qiaoId');
  }

  await post('/contact-requests', {
    to_qiao_id: qiaoId,
    message,
  });
  logger.info('contact_request_sent', { qiao_id: qiaoId });
}
