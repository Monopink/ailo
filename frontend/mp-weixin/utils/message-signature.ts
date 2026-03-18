/**
 * Message signature utility
 * Provides helpers to fetch LeanCloud IM signatures from backend.
 */
import { post } from './api';
import { getLogger } from './logger';

const logger = getLogger('MessageSignature');

type PresenceResponse = {
  endpoint_id: number;
  client_id: string;
  lease_ttl_days: number;
  lease_expires_at_ms: number;
};

export async function getMessageClientSignature(clientId: string): Promise<Ailo.MessageSignature> {
  try {
    const signature = await post<Ailo.MessageSignature>('/lc-im/signature', {
      client_id: clientId,
    });
    logger.info('Message client signature obtained');
    return signature;
  } catch (error) {
    logger.error('Get message client signature failed', { error });
    throw error;
  }
}

export async function registerMessagePresence(clientId: string): Promise<PresenceResponse> {
  try {
    const response = await post<PresenceResponse>('/lc-im/presence', {
      client_id: clientId,
    });
    logger.info('Message presence registered', {
      endpoint_id: response.endpoint_id,
      lease_expires_at_ms: response.lease_expires_at_ms,
    });
    return response;
  } catch (error) {
    logger.error('Register message presence failed', { error });
    throw error;
  }
}

export default {
  getMessageClientSignature,
  registerMessagePresence,
};
