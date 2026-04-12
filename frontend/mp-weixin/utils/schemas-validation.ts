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
  username: z.string().optional().nullable(),
  nickname: z.string().optional().nullable(),
  avatar_url: z.string().optional().nullable(),
  gender: z.number().optional().nullable(),
  bio: z.string().optional().nullable(),
  region: z.string().optional().nullable(),
});
export type ContactProfile = z.infer<typeof ContactProfileSchema>;

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

export const UsernameCheckResponseSchema = z.object({
  available: z.boolean(),
});
export type UsernameCheckResponse = z.infer<typeof UsernameCheckResponseSchema>;

export const AccountInfoSchema = z.object({
  phone: z.string().optional(),
  email: z.string().optional().nullable(),
});
export type AccountInfo = z.infer<typeof AccountInfoSchema>;

export const MinorModeStatusSchema = z.object({
  enabled: z.boolean(),
  has_pin: z.boolean(),
  enabled_at: z.string().nullable(),
  pin_updated_at: z.string().nullable(),
});
export type MinorModeStatus = z.infer<typeof MinorModeStatusSchema>;

export const MinorModePinVerifyResponseSchema = z.object({
  verified: z.boolean(),
});
export type MinorModePinVerifyResponse = z.infer<typeof MinorModePinVerifyResponseSchema>;

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
  contact_type: z.union([z.literal(1), z.literal(2), z.literal(3)]),
  contact_qiao_id: z.string().optional(),
  im_conv_id: z.string().optional(),
  alias: z.string().optional().nullable(),
  remark: z.string().optional().nullable(),
  avatar_url: z.string().optional().nullable(),
  remark_avatar_url: z.string().optional().nullable(),
  original_avatar_url: z.string().optional().nullable(),
  avatar_display_mode: z.union([z.literal(1), z.literal(2)]).optional(),
  tags: z.array(z.string()).optional(),
  last_message_content: z.string().optional().nullable(),
  last_message: z.string().optional().nullable(),
  last_message_time: z.union([z.number(), z.string()]).optional().nullable(),
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

export const MessageSessionBootstrapSchema = z.object({
  config_version: z.string().min(1),
  session: z.object({
    client_id: z.string().min(1),
    app_id: z.string().min(1),
    app_key: z.string().min(1),
    server_url: z.string().min(1),
    im_conv_id: z.string().min(1),
    signature: z.object({
      algorithm: z.string().min(1),
      version: z.string().min(1),
      value: z.string().min(1),
      timestamp: z.number().int(),
      nonce: z.string().min(1),
      expires_in_ms: z.number().int().nonnegative(),
    }),
  }),
  presence: z.object({
    endpoint_id: z.number().int(),
    lease_ttl_days: z.number().int().nonnegative(),
    lease_expires_at_ms: z.number().int().nonnegative(),
  }),
});
export type MessageSessionBootstrap = z.infer<typeof MessageSessionBootstrapSchema>;

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

// Source of truth: backend/app/enums/ -> SquareCategoryTheme
export const SquareThemeKeySchema = z.enum([
  'blue',
  'cyan',
  'teal',
  'green',
  'lime',
  'yellow',
  'orange',
  'purple',
  'pink',
  'magenta',
  'beige',
  'charcoal',
]);
export type SquareThemeKey = z.infer<typeof SquareThemeKeySchema>;

export const SquareCategorySchema = z.object({
  category_key: z.string(),
  title: z.string(),
  description: z.string().optional().nullable(),
  theme_key: SquareThemeKeySchema,
  icon_ref: z.string(),
});
export type SquareCategory = z.infer<typeof SquareCategorySchema>;

export const SquareCategoriesResponseSchema = z.object({
  items: z.array(SquareCategorySchema),
});
export type SquareCategoriesResponse = z.infer<typeof SquareCategoriesResponseSchema>;

export const SquarePaginationSchema = z.object({
  page: z.number().int().positive(),
  page_size: z.number().int().positive(),
  total: z.number().int().nonnegative(),
  has_more: z.boolean(),
});
export type SquarePagination = z.infer<typeof SquarePaginationSchema>;

export const SquareContactSchema = z.object({
  qiao_id: z.string(),
  type_id: z.number().int().positive(),
  category_key: z.string(),
  nickname: z.string().optional().nullable(),
  avatar_url: z.string().optional().nullable(),
  gender: z.number().optional().nullable(),
  tags: z.array(z.string()),
  remark: z.string().nullable(),
  bio: z.string().optional().nullable(),
  region: z.string().optional().nullable(),
});
export type SquareContact = z.infer<typeof SquareContactSchema>;

export const SquareApiResponseSchema = z.object({
  items: z.array(SquareContactSchema),
  pagination: SquarePaginationSchema,
  refresh_available_at: z.string().optional().nullable(),
});
export type SquareApiResponse = z.infer<typeof SquareApiResponseSchema>;

export const StrangerProfileResponseSchema = z.object({
  qiao_id: z.string(),
  username: z.string().optional().nullable(),
  nickname: z.string().optional().nullable(),
  avatar_url: z.string().optional().nullable(),
  gender: z.number().optional().nullable(),
  category_key: z.string().optional().nullable(),
  category_title: z.string().optional().nullable(),
  tags: z.array(z.string()),
  remark: z.string().nullable(),
  bio: z.string().optional().nullable(),
  region: z.string().optional().nullable(),
});
export type StrangerProfileResponse = z.infer<typeof StrangerProfileResponseSchema>;

export const PhoneRefreshResponseSchema = z.object({
  phone: z.string(),
});
export type PhoneRefreshResponse = z.infer<typeof PhoneRefreshResponseSchema>;

export const AppPageSchema = z.object({
  page_key: z.string(),
  page_category: z.number().int(),
  title: z.string(),
  locale: z.string(),
  content_rendered_format: z.literal('html'),
  content_rendered: z.string(),
  updated_at: z.string().datetime(),
});
export type AppPage = z.infer<typeof AppPageSchema>;

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
