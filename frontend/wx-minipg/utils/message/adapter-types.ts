import { MESSAGE_STATUS } from './constants';
import type { MessageType } from './constants';

export interface BusinessMessagePayload {
  msg_id: string;
  from: string;
  to: string;
  conv_id: string;
  content: string;
  message_type: MessageType;
  supports_typing: boolean;
  sent_time: number;
  action?: string | null;
  notification_type?: string | null;
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
  from: string;
  conv_id: string;
  isTyping: boolean;
};

export interface MessageAdapter {
  connect(userId: string, signature: MessageSignature): Promise<void>;
  disconnect(): Promise<void>;
  sendMessage(message: BusinessMessagePayload, imConvId: string): Promise<AdapterSendResult>;
  onMessage(handler: (message: AdapterMessage) => void): void;
  onTyping(handler: (payload: AdapterTypingPayload) => void): void;
  onError(handler: (error: Error) => void): void;
  invalidateConversation?(imConvId?: string | null): void;
  isConnected(): boolean;
}
