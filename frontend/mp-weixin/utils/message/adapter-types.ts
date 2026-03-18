import { MESSAGE_STATUS } from '../constants/message';
import type { MessageType } from '../constants/message';

export interface BusinessMessagePayload {
  msg_id: string;
  msg_id_server?: string | null;
  msg_id_client?: string | null;
  from_qiao_id: string;
  to_qiao_id: string;
  conv_id: string;
  content: string;
  message_type: MessageType;
  supports_typing: boolean;
  sent_time: number;
  action?: Record<string, unknown> | string | null;
  notification_type?: number | string | null;
  data?: Record<string, unknown> | null;
}

export type MessageSignature = {
  signature: string;
  timestamp: number;
  nonce: string;
};

export type AdapterMessageStatus = (typeof MESSAGE_STATUS)[keyof typeof MESSAGE_STATUS];

export interface AdapterSendResult extends BusinessMessagePayload {
  lc_msg_id: string;
  lc_timestamp: number;
}

export interface AdapterMessage extends AdapterSendResult {
  status: AdapterMessageStatus;
}

export type AdapterTypingPayload = {
  from_qiao_id: string;
  to_qiao_id: string;
  conv_id: string;
  isTyping: boolean;
  sent_time: number;
};

export type ConnectionState = 'connected' | 'connecting' | 'disconnected' | 'suspending';

export interface MessageAdapter {
  connect(userId: string, signature: MessageSignature): Promise<void>;
  disconnect(): Promise<void>;
  sendMessage(message: BusinessMessagePayload, imConvId: string): Promise<AdapterSendResult>;
  onMessage(handler: (message: AdapterMessage) => void): void;
  onTyping(handler: (payload: AdapterTypingPayload) => void): void;
  onError(handler: (error: Error) => void): void;
  onConnectionChange(handler: (state: ConnectionState) => void): void;
  invalidateConversation?(imConvId?: string | null): void;
  isConnected(): boolean;
}
