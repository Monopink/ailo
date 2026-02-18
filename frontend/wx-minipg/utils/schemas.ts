/**
 * Runtime validation schemas using Zod
 *
 * These schemas provide both TypeScript types and runtime validation.
 * Use them to validate API responses and external data.
 */

import { z } from 'zod';
import { MESSAGE_STATUS, MESSAGE_TYPE } from './constants/message';

// ============================================================================
// User Schemas
// ============================================================================

export const UserInfoSchema = z.object({
  id: z.number(),
  nickname: z.string(),
  avatar: z.string().url().nullable(),
  gender: z.enum(['male', 'female', 'other']),
  bio: z.string().nullable(),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
});

export type UserInfo = z.infer<typeof UserInfoSchema>;

export const MessageStatusSchema = z.nativeEnum(MESSAGE_STATUS);
export type MessageStatus = z.infer<typeof MessageStatusSchema>;

export const MessageTypeSchema = z.nativeEnum(MESSAGE_TYPE);
export type MessageType = z.infer<typeof MessageTypeSchema>;

export const ContactProfileSchema = z.object({
  nickname: z.string().optional().nullable(),
  avatar_url: z.string().optional().nullable(),
  gender: z.number().optional().nullable(),
  bio: z.string().optional().nullable(),
  region: z.string().optional().nullable(),
});
export type ContactProfile = z.infer<typeof ContactProfileSchema>;

export const ConversationResponseSchema = z.object({
  conversation_id: z.string(),
  im_conv_id: z.string(),
  contact_qiao_id: z.string(),
  profile: ContactProfileSchema,
});
export type ConversationResponse = z.infer<typeof ConversationResponseSchema>;

export const UserProfileSchema = z.object({
  qiao_id: z.string(),
  username: z.string().nullable(),
  nickname: z.string().nullable(),
  avatar_url: z.string().nullable(),
  gender: z.number().nullable(),
  bio: z.string().nullable(),
  region: z.string().nullable(),
});
export type UserProfile = z.infer<typeof UserProfileSchema>;

export const AccountInfoSchema = z.object({
  phone: z.string().optional(),
  email: z.string().optional().nullable(),
});
export type AccountInfo = z.infer<typeof AccountInfoSchema>;

// ============================================================================
// Auth Schemas
// ============================================================================

export const AuthUserPayloadSchema = z.object({
  qiao_id: z.string(),
  nickname: z.string().optional().nullable(),
  avatar_url: z.string().optional().nullable(),
});
export type AuthUserPayload = z.infer<typeof AuthUserPayloadSchema>;

export const WechatLoginCheckSchema = z.object({
  status: z.enum(['bound', 'need_phone']),
  access_token: z.string().nullable().optional(),
  refresh_token: z.string().nullable().optional(),
  expires_in: z.number().nullable().optional(),
  needs_profile_setup: z.boolean().nullable().optional(),
  user: AuthUserPayloadSchema.nullable().optional(),
  message: z.string().nullable().optional(),
});
export type WechatLoginCheckResponse = z.infer<typeof WechatLoginCheckSchema>;

export const WechatBindPhoneResponseSchema = z.object({
  status: z.literal('success'),
  access_token: z.string(),
  refresh_token: z.string(),
  expires_in: z.number(),
  needs_profile_setup: z.boolean(),
  user: AuthUserPayloadSchema,
  message: z.string().optional().nullable(),
  binding_reused: z.boolean().optional(),
  replaced_old_wechat: z.boolean().optional(),
});
export type WechatBindPhoneResponse = z.infer<typeof WechatBindPhoneResponseSchema>;

export const StoredContactSchema = z.object({
  conversation_id: z.string(),
  contact_qiao_id: z.string().optional(),
  im_conv_id: z.string().optional(),
  alias: z.string().optional().nullable(),
  tags: z.array(z.string()).optional(),
  is_pinned: z.boolean().optional(),
  is_muted: z.boolean().optional(),
  is_blocked: z.boolean().optional(),
  profile: ContactProfileSchema.optional(),
});
export type StoredContact = z.infer<typeof StoredContactSchema>;

export const StoredContactsSchema = z.array(StoredContactSchema);
export type StoredContacts = z.infer<typeof StoredContactsSchema>;

export const StoredMessageSchema = z.object({
  msg_id: z.string(),
  msg_id_server: z.string().optional().nullable(),
  msg_id_client: z.string().optional().nullable(),
  conv_id: z.string(),
  from_qiao_id: z.string().optional(),
  to_qiao_id: z.string().optional(),
  content: z.string().optional().nullable(),
  message_type: MessageTypeSchema.optional(),
  supports_typing: z.boolean().optional(),
  sent_time: z.number().optional(),
  status: MessageStatusSchema.optional(),
  action: z
    .union([z.string(), z.record(z.string(), z.unknown())])
    .optional()
    .nullable(),
  notification_type: z.union([z.string(), z.number()]).optional().nullable(),
  data: z.record(z.string(), z.unknown()).optional().nullable(),
  id: z.string().optional(),
  text: z.string().optional(),
  created_at: z.number().optional(),
  timestamp: z.number().optional(),
});
export type StoredMessage = z.infer<typeof StoredMessageSchema>;

export const StoredMessagesSchema = z.array(StoredMessageSchema);
export type StoredMessages = z.infer<typeof StoredMessagesSchema>;

export const ConversationUnreadCountsSchema = z.record(z.number().int().nonnegative());
export type ConversationUnreadCounts = z.infer<typeof ConversationUnreadCountsSchema>;

export const ConversationUnreadMarksSchema = z.record(z.boolean());
export type ConversationUnreadMarks = z.infer<typeof ConversationUnreadMarksSchema>;

export const ConversationReadStateItemSchema = z.object({
  last_read_sent_time: z.number(),
  last_read_msg_id: z.string().optional(),
  updated_at: z.number(),
});
export type ConversationReadStateItem = z.infer<typeof ConversationReadStateItemSchema>;

export const ConversationReadStateSchema = z.record(ConversationReadStateItemSchema);
export type ConversationReadState = z.infer<typeof ConversationReadStateSchema>;

export const ConversationViewStateItemSchema = z.object({
  last_viewed_msg_id: z.string().optional(),
  is_at_bottom: z.boolean(),
  updated_at: z.number(),
});
export type ConversationViewStateItem = z.infer<typeof ConversationViewStateItemSchema>;

export const ConversationViewStateSchema = z.record(ConversationViewStateItemSchema);
export type ConversationViewState = z.infer<typeof ConversationViewStateSchema>;

export const OfflineMessageSchema = z.object({
  msg_id_server: z.string(),
  msg_id_client: z.string().optional().nullable(),
  conversation_id: z.string(),
  from_qiao_id: z.string(),
  to_qiao_id: z.string(),
  content: z.string().optional().nullable(),
  message_type: MessageTypeSchema,
  client_sent_time_ms: z.number().optional().nullable(),
  sent_time_ms: z.number(),
  metadata: z
    .object({
      action: z.record(z.string(), z.unknown()).optional().nullable(),
      notification_type: z.number().optional().nullable(),
    })
    .optional(),
});
export type OfflineMessage = z.infer<typeof OfflineMessageSchema>;

export const OfflineMessagesResponseSchema = z.object({
  server_time_ms: z.number(),
  limit: z.number(),
  has_more: z.boolean(),
  next_cursor: z.string().optional().nullable(),
  messages: z.array(OfflineMessageSchema),
});
export type OfflineMessagesResponse = z.infer<typeof OfflineMessagesResponseSchema>;

export const OfflineAckResponseSchema = z.object({
  success: z.boolean(),
  server_time_ms: z.number(),
});
export type OfflineAckResponse = z.infer<typeof OfflineAckResponseSchema>;

export const ConversationConfigSchema = z.object({
  im_conv_id: z.string(),
  signature_algorithm: z.string(),
  signature_version: z.string(),
  signature_ttl_ms: z.number().int().nonnegative(),
});
export type ConversationConfig = z.infer<typeof ConversationConfigSchema>;

// ============================================================================
// API Response Schemas
// ============================================================================

export const ApiResponseSchema = <T extends z.ZodTypeAny>(
  dataSchema: T
): z.ZodObject<{
  code: z.ZodNumber;
  message: z.ZodString;
  data: T;
}> =>
  z.object({
    code: z.number(),
    message: z.string(),
    data: dataSchema,
  });

export type ApiResponse<T> = {
  code: number;
  message: string;
  data: T;
};

// ============================================================================
// Pagination Schema
// ============================================================================

export const PaginationSchema = z.object({
  page: z.number().int().positive(),
  page_size: z.number().int().positive(),
  total: z.number().int().nonnegative(),
  total_pages: z.number().int().nonnegative(),
});

export type Pagination = z.infer<typeof PaginationSchema>;

export const SquareContactSchema = z.object({
  qiao_id: z.string(),
  nickname: z.string().optional().nullable(),
  avatar_url: z.string().optional().nullable(),
  gender: z.number().optional().nullable(),
  bio: z.string().optional().nullable(),
  region: z.string().optional().nullable(),
  category: z.number().optional().nullable(),
});
export type SquareContact = z.infer<typeof SquareContactSchema>;

export const SquareApiResponseSchema = z.object({
  items: z.array(SquareContactSchema),
  refresh_available_at: z.string().optional().nullable(),
});
export type SquareApiResponse = z.infer<typeof SquareApiResponseSchema>;

export const PhoneRefreshResponseSchema = z.object({
  phone: z.string(),
});
export type PhoneRefreshResponse = z.infer<typeof PhoneRefreshResponseSchema>;

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Safely parse data with a schema
 * Returns parsed data or null if validation fails
 */
export function safeParse<T>(schema: z.ZodSchema<T>, data: unknown): T | null {
  const result = schema.safeParse(data);
  if (result.success) {
    return result.data;
  }
  console.error('Schema validation failed:', result.error);
  return null;
}

/**
 * Parse data with a schema, throw error if validation fails
 */
export function parse<T>(schema: z.ZodSchema<T>, data: unknown): T {
  return schema.parse(data);
}
