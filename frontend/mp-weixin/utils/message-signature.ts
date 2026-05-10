/**
 * Message session bootstrap utility.
 *
 * WebSocket runtime bootstrap is issued by backend.
 */

import { requestValidated } from './api';
import { getLogger } from './logger';
import { MessageSessionBootstrapSchema, type MessageSessionBootstrap } from './schemas';
import { getDeviceId } from './storage';

const logger = getLogger('MessageSignature');

export async function bootstrapMessageSession(): Promise<MessageSessionBootstrap> {
  const deviceId = await getDeviceId();
  const payload = await requestValidated(MessageSessionBootstrapSchema, {
    url: '/messages/ws-session',
    method: 'POST',
    data: {
      device_id: deviceId,
    },
  });

  logger.info('Message session bootstrap obtained', {
    config_version: payload.config_version,
    client_id: payload.session.client_id,
    ws_base_url: payload.session.server_url,
  });

  return payload;
}

export default {
  bootstrapMessageSession,
};
