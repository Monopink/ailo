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

    interface MessageSignature {
      signature: string;
      timestamp: number;
      nonce: string;
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
      action?: Record<string, unknown> | string | null;
      notification_type?: number | string | null;
      data?: Record<string, unknown> | null;
      lc_msg_id?: string;
      lc_timestamp?: number;
    }

    interface TypingEvent {
      conv_id: string;
      from_qiao_id: QiaoID;
      to_qiao_id: QiaoID;
      typing: boolean;
      timestamp: number;
    }

    interface ConversationSummary {
      convId: string;
      peerId: QiaoID;
      unreadCount: number;
      lastMessage: MessagePayload | null;
      updatedAt: number;
    }

    interface MessageAdapter {
      connect(userId: QiaoID, signature: MessageSignature): Promise<void>;
      disconnect(): Promise<void>;
      sendMessage(convId: string, message: Partial<MessagePayload>): Promise<MessagePayload>;
      sendTyping(convId: string, typing: boolean): Promise<void>;
      onMessage(handler: (message: MessagePayload) => void): void;
      onTyping(handler: (payload: TypingEvent) => void): void;
      onError(handler: (error: unknown) => void): void;
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
    initializeAuth(): Promise<void>;
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
