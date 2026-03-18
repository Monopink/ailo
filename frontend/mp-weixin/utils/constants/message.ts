/**
 * Message-related constants and enums
 *
 * These constants define business layer message types and status
 * Independent of any third-party messaging service (Leancloud)
 *
 * IMPORTANT: All enum values MUST match backend definitions
 */

/**
 * Message status enum - MUST match backend
 * @readonly
 * @enum {number}
 */
export const MESSAGE_STATUS = {
  SENDING: 1,
  SENT: 2,
  FAILED: 3,
  RECEIVED: 4,
} as const;

export type MessageStatus = (typeof MESSAGE_STATUS)[keyof typeof MESSAGE_STATUS];

/**
 * Message type enum - MUST match backend
 * @readonly
 * @enum {number}
 */
export const MESSAGE_TYPE = {
  TEXT: 1,
  TYPING_START: 2,
  TYPING_END: 3,
  CHAT_INFO: 4,
  NOTIFICATION: 9,
} as const;

export type MessageType = (typeof MESSAGE_TYPE)[keyof typeof MESSAGE_TYPE];
