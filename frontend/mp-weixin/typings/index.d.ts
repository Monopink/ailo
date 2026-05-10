/// <reference types="miniprogram-api-typings" />
import type conversationStore from '../utils/message/conversation-store';
import type { MessageService as MessageServiceClass } from '../utils/message/service';

declare global {
  namespace Ailo {
    type QiaoID = string;

    interface AuthTokens {
      accessToken: string;
      refreshToken: string;
      expiresIn: number;
    }

    interface AuthUser {
      qiao_id: QiaoID;
      nickname: string;
      avatar: string;
      bio?: string;
      gender?: string;
      phone?: string;
      tags?: string[];
    }

    interface MessageAuthPayload {
      wsTicket: string;
      issuedAtMs: number;
      deviceId: string;
    }

    interface MessagePayload {
      msg_id: string;
      msg_id_server?: string | null;
      msg_id_client?: string | null;
      from_qiao_id: QiaoID;
      to_qiao_id: QiaoID;
      conv_id: string;
      content: string;
      message_type: number;
      supports_typing: boolean;
      sent_time: number;
      status?: number;
      failure_category?: string | null;
      failure_reason?: string | null;
      retryable?: boolean | null;
      action?: Record<string, unknown> | string | null;
      notification_type?: number | string | null;
      data?: Record<string, unknown> | null;
      provider_msg_id?: string;
      provider_timestamp_ms?: number;
    }

    interface TypingEvent {
      conv_id: string;
      from_qiao_id: QiaoID;
      to_qiao_id: QiaoID;
      isTyping: boolean;
      sent_time: number;
    }

    type MessageConnectionState = 'connected' | 'connecting' | 'disconnected' | 'suspending';

    interface ConversationSummary {
      convId: string;
      peerId: QiaoID;
      unreadCount: number;
      lastMessage: MessagePayload | null;
      updatedAt: number;
    }

    interface MessageAdapter {
      connect(
        userId: QiaoID,
        auth: MessageAuthPayload,
        config: {
          provider: string;
          server_url: string;
          config_version: string;
          session_hint: string;
        }
      ): Promise<void>;
      disconnect(): Promise<void>;
      sendMessage(message: MessagePayload, sessionHint: string): Promise<MessagePayload>;
      onMessage(handler: (message: MessagePayload) => void): void;
      onTyping(handler: (payload: TypingEvent) => void): void;
      onError(handler: (error: unknown) => void): void;
      onConnectionChange(handler: (state: MessageConnectionState) => void): void;
      invalidateConversation?(sessionHint?: string | null): void;
      isConnected(): boolean;
    }

    interface MessageQueueJob {
      convId: string;
      message: MessagePayload;
      retries: number;
    }

    type MessageService = MessageServiceClass;

    type ConversationStoreInstance = typeof conversationStore;

    interface GlobalData {
      messageService: MessageService | null;
      systemInfo: WechatMiniprogram.SystemInfo | null;
      conversationStore: ConversationStoreInstance;
    }
  }

  interface AppInstance extends WechatMiniprogram.App.Instance<WechatMiniprogram.IAnyObject> {
    globalData: Ailo.GlobalData;
    initMessageService(): Promise<void>;
    getMessageService(): Ailo.MessageService | null;
    getConversationStore(): Ailo.ConversationStoreInstance;
    getAuthService(): unknown;
    setUserInfo(userInfo: unknown): void;
    getUserInfo(): unknown;
    setToken(token: unknown): void;
    getToken(): unknown;
    clearAuth(): void;
    onMessageReceived?(message: Ailo.MessagePayload): void;
    onMessageError?(error: unknown): void;
  }

  function getApp(): AppInstance;
}

export {};
