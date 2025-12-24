/**
 * Message signature utility
 * Provides helpers to fetch LeanCloud IM signatures from backend.
 */
import { post } from './api';
import { getLogger } from './logger';

const logger = getLogger('MessageSignature');

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

export default {
  getMessageClientSignature,
};
