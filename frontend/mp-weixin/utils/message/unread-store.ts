import { MESSAGE_TYPE } from '../constants/message';
import { isNonEmptyString } from '../guards';
import {
  getConversationUnreadCounts,
  getConversationUnreadMarks,
  getLatestMessageMeta,
  setConversationLastRead,
  setConversationUnreadCounts,
  setConversationUnreadMarks,
} from '../storage';
import type { StoredMessage } from '../storage';

let activeConversationId: string | null = null;

const isCountableMessage = (message: StoredMessage, currentUserId: string | null): boolean => {
  if (!isNonEmptyString(currentUserId)) {
    return false;
  }
  if (!isNonEmptyString(message.conv_id)) {
    return false;
  }
  if (message.to_qiao_id !== currentUserId) {
    return false;
  }

  const messageType =
    typeof message.message_type === 'number' ? message.message_type : MESSAGE_TYPE.TEXT;
  return (
    messageType !== MESSAGE_TYPE.TYPING_START &&
    messageType !== MESSAGE_TYPE.TYPING_END &&
    messageType !== MESSAGE_TYPE.NOTIFICATION &&
    messageType !== MESSAGE_TYPE.CHAT_INFO
  );
};

const clampCount = (value: number): number => (value < 0 ? 0 : value);

const updateUnreadCount = async (convId: string, nextCount: number): Promise<void> => {
  const counts = await getConversationUnreadCounts();
  counts[convId] = clampCount(nextCount);
  await setConversationUnreadCounts(counts);
};

const updateLastRead = async (
  convId: string,
  payload?: { sentTime?: number; msgId?: string }
): Promise<void> => {
  const sentTime = payload?.sentTime ?? Date.now();
  await setConversationLastRead(convId, {
    last_read_sent_time: sentTime,
    last_read_msg_id: payload?.msgId,
  });
};

const unreadStore = {
  async setActiveConversation(convId: string): Promise<void> {
    if (!isNonEmptyString(convId)) {
      return;
    }
    activeConversationId = convId;
    await updateUnreadCount(convId, 0);
    const marks = await getConversationUnreadMarks();
    delete marks[convId];
    await setConversationUnreadMarks(marks);
    const latest = await getLatestMessageMeta(convId);
    await updateLastRead(convId, {
      sentTime: latest?.sent_time,
      msgId: latest?.msg_id,
    });
  },

  clearActiveConversation(convId?: string): void {
    if (convId !== undefined && convId !== activeConversationId) {
      return;
    }
    activeConversationId = null;
  },

  async handleIncomingMessage(message: StoredMessage, currentUserId: string | null): Promise<void> {
    if (!isCountableMessage(message, currentUserId)) {
      return;
    }
    if (message.conv_id === activeConversationId) {
      await updateUnreadCount(message.conv_id, 0);
      const marks = await getConversationUnreadMarks();
      delete marks[message.conv_id];
      await setConversationUnreadMarks(marks);
      await updateLastRead(message.conv_id, {
        sentTime: message.sent_time,
        msgId: message.msg_id,
      });
      return;
    }
    const counts = await getConversationUnreadCounts();
    const current = counts[message.conv_id] ?? 0;
    counts[message.conv_id] = current + 1;
    await setConversationUnreadCounts(counts);
    const marks = await getConversationUnreadMarks();
    delete marks[message.conv_id];
    await setConversationUnreadMarks(marks);
  },

  async markConversationAsUnread(convId: string): Promise<void> {
    if (!isNonEmptyString(convId)) {
      return;
    }
    const counts = await getConversationUnreadCounts();
    const current = counts[convId] ?? 0;
    if (current > 0) {
      counts[convId] = current;
      await setConversationUnreadCounts(counts);
      return;
    }
    const marks = await getConversationUnreadMarks();
    marks[convId] = true;
    await setConversationUnreadMarks(marks);
  },

  async markConversationAsRead(convId: string): Promise<void> {
    if (!isNonEmptyString(convId)) {
      return;
    }
    await updateUnreadCount(convId, 0);
    const marks = await getConversationUnreadMarks();
    delete marks[convId];
    await setConversationUnreadMarks(marks);
    await updateLastRead(convId);
  },

  getActiveConversationId(): string | null {
    return activeConversationId;
  },
};

export default unreadStore;
