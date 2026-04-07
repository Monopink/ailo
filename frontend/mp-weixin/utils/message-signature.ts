/**
 * Message session bootstrap utility.
 */
import { requestValidated } from './api';
import { getLogger } from './logger';
import { MessageSessionBootstrapSchema, type MessageSessionBootstrap } from './schemas';

const logger = getLogger('MessageSignature');

export async function bootstrapMessageSession(): Promise<MessageSessionBootstrap> {
  try {
    const response = await requestValidated(MessageSessionBootstrapSchema, {
      url: '/lc-im/bootstrap',
      method: 'POST',
      data: {
        client_kind: 2,
      },
    });
    logger.info('Message session bootstrap obtained', {
      config_version: response.config_version,
      im_conv_id: response.session.im_conv_id,
    });
    return response;
  } catch (error) {
    logger.error('Message session bootstrap failed', { error });
    throw error;
  }
}

export default {
  bootstrapMessageSession,
};
