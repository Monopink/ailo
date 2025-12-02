/// <reference types="miniprogram-api-typings" />
import type conversationStore from '../utils/message/conversation-store';
import type { MessageService as MessageServiceClass } from '../utils/message/service';

declare global {
  namespace Says {
    type QiaoID = string;

    interface CaptchaConfig {
      provider: string;
      sceneId: string;
      region: string;
      mode: string;
      language: string;
    }

    interface CaptchaHandlers {
      success?(token: string): void;
      fail?(error: unknown): void;
      onReady?(): void;
    }

    interface CaptchaPageData extends Record<string, unknown> {
      captchaProvider?: string;
      captchaSceneId?: string;
      loadCaptcha?: boolean;
      pluginProps?: Record<string, unknown>;
    }

    interface AuthTokens {
      accessToken: string;
      refreshToken: string;
      expiresAt: number;
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
      from: QiaoID;
      to: QiaoID;
      conv_id: string;
      content: string;
      message_type: number;
      supports_typing: boolean;
      sent_time: number;
      status?: number;
      action?: string | null;
      notification_type?: string | null;
      data?: Record<string, unknown> | null;
      lc_msg_id?: string;
      lc_timestamp?: number;
    }

    interface TypingEvent {
      conv_id: string;
      from: QiaoID;
      to: QiaoID;
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
      captchaConfig: CaptchaConfig | null;
      conversationStore: ConversationStoreInstance;
    }

    interface CaptchaPageInstance extends WechatMiniprogram.Page.Instance<
      Record<string, unknown>,
      CaptchaPageData
    > {
      data: CaptchaPageData;
      _captchaActive?: boolean;
      _captchaReady?: boolean;
      _captchaRetryCount?: number;
      onCaptchaSuccess?(token: string): void;
    }
  }

  interface SaysAppInstance extends WechatMiniprogram.App.Instance<WechatMiniprogram.IAnyObject> {
    globalData: Says.GlobalData;
    preloadCaptchaConfig(): Promise<void>;
    initializeAuth(): Promise<void>;
    refreshTokenIfNeeded(): Promise<void>;
    initMessageService(): Promise<void>;
    getMessageService(): Says.MessageService | null;
    getConversationStore(): Says.ConversationStoreInstance;
    getAuthService(): unknown;
    setUserInfo(userInfo: unknown): void;
    getUserInfo(): unknown;
    setToken(token: unknown): void;
    getToken(): unknown;
    clearAuth(): void;
    onMessageReceived?(message: Says.MessagePayload): void;
    onTypingReceived?(payload: Says.TypingEvent): void;
    onMessageError?(error: unknown): void;
  }

  function getApp(): SaysAppInstance;
}

export {};
