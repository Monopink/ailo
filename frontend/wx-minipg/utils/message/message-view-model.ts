import { StoredMessage, StoredMessages } from '../storage';
import { MESSAGE_TYPE, MessageType } from './constants';

const TIMESTAMP_GAP_MS = 5 * 60 * 1000;

function getMessageTimestamp(message: StoredMessage): number {
  if (typeof message.sent_time === 'number') {
    return message.sent_time;
  }
  if (typeof message.created_at === 'number') {
    return message.created_at;
  }
  if (typeof message.timestamp === 'number') {
    return message.timestamp;
  }
  return Date.now();
}

function shouldSkipMessage(message: StoredMessage): boolean {
  const type = message.message_type as MessageType | undefined;
  return (
    type === MESSAGE_TYPE.TYPING_START ||
    type === MESSAGE_TYPE.TYPING_END ||
    type === MESSAGE_TYPE.NOTIFICATION
  );
}

function formatTimestamp(timestamp: number): string {
  const now = Date.now();
  const diff = now - timestamp;
  const date = new Date(timestamp);

  if (diff < 60_000) {
    return '刚刚';
  }

  if (diff < 3_600_000) {
    const minutes = Math.floor(diff / 60_000);
    return `${minutes}分钟前`;
  }

  const today = new Date();
  if (date.toDateString() === today.toDateString()) {
    const hours = date.getHours();
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${hours}:${minutes}`;
  }

  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) {
    const hours = date.getHours();
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `昨天 ${hours}:${minutes}`;
  }

  const weekDays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
  if (diff < 7 * 24 * 3_600_000) {
    const hours = date.getHours();
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${weekDays[date.getDay()]} ${hours}:${minutes}`;
  }

  if (date.getFullYear() === today.getFullYear()) {
    const month = date.getMonth() + 1;
    const day = date.getDate();
    return `${month}-${day}`;
  }

  const year = date.getFullYear();
  const month = date.getMonth() + 1;
  const day = date.getDate();
  return `${year}-${month}-${day}`;
}

function buildSystemContent(message: StoredMessage): string {
  return message.content || '';
}

function getMessageText(message: StoredMessage): string {
  if (typeof message.content === 'string' && message.content) {
    return message.content;
  }
  if (typeof message.text === 'string') {
    return message.text;
  }
  return '';
}

export interface MessageViewModel extends StoredMessage {
  from_me: boolean;
  showTimestamp: boolean;
  timestampText: string;
  isSystemMessage: boolean;
  systemContent: string;
}

export function buildMessageViewModels(
  messages: StoredMessages,
  currentUserId: string
): MessageViewModel[] {
  const sorted = [...messages].sort(
    (left, right) => getMessageTimestamp(left) - getMessageTimestamp(right)
  );
  const result: MessageViewModel[] = [];
  let previous: MessageViewModel | null = null;

  for (const message of sorted) {
    if (shouldSkipMessage(message)) {
      continue;
    }

    const timestamp = getMessageTimestamp(message);
    const viewModel: MessageViewModel = {
      ...message,
      from_me: currentUserId !== '' && message.from === currentUserId,
      showTimestamp: false,
      timestampText: '',
      isSystemMessage: message.message_type === MESSAGE_TYPE.CHAT_INFO,
      systemContent: '',
    };

    viewModel.content = getMessageText(message);
    viewModel.sent_time = timestamp;
    viewModel.timestampText = formatTimestamp(timestamp);
    viewModel.showTimestamp =
      !previous || timestamp - (previous.sent_time ?? 0) > TIMESTAMP_GAP_MS;
    viewModel.systemContent = viewModel.isSystemMessage
      ? buildSystemContent(message)
      : '';

    result.push(viewModel);
    previous = viewModel;
  }

  return result;
}
