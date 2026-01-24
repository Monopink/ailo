/**
 * Offline message API
 * Handles pull + ACK for offline message compensation.
 */

import { requestValidated } from '../api';
import type { OfflineMessagesResponse } from '../schemas';
import { OfflineAckResponseSchema, OfflineMessagesResponseSchema } from '../schemas';
import { getDeviceId } from '../storage';

export async function fetchOfflineMessages(params?: {
  cursor?: string | null;
  limit?: number;
}): Promise<OfflineMessagesResponse> {
  const deviceId = await getDeviceId();
  const payload: { device_id: string; limit?: number; cursor?: string } = {
    device_id: deviceId,
    limit: params?.limit,
  };
  if (params?.cursor !== null && params?.cursor !== undefined) {
    payload.cursor = params.cursor;
  }

  return await requestValidated(OfflineMessagesResponseSchema, {
    url: '/messages/offline',
    method: 'GET',
    data: payload,
  });
}

export async function ackOfflineMessages(payload: {
  last_ack_msg_id: string;
  last_ack_sent_at: number;
}): Promise<void> {
  const deviceId = await getDeviceId();

  await requestValidated(OfflineAckResponseSchema, {
    url: '/messages/ack',
    method: 'POST',
    data: {
      device_id: deviceId,
      last_ack_msg_id: payload.last_ack_msg_id,
      last_ack_sent_at: payload.last_ack_sent_at,
    },
  });
}
