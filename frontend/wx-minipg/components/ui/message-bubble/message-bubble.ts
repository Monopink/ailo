type MessageStatus = 'sending' | 'sent' | 'failed';

const STATUS_LABELS: Record<MessageStatus, string> = {
  sending: '发送中…',
  sent: '已送达',
  failed: '发送失败',
};

const formatTimestamp = (value?: number): string => {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '';
  }
  const date = new Date(value);
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${hours}:${minutes}`;
};

Component({
  options: {
    addGlobalClass: true,
  },
  data: {
    formattedTime: '',
    statusLabel: '',
  },
  properties: {
    messageId: {
      type: String,
      value: '',
    },
    content: {
      type: String,
      value: '',
    },
    timestamp: {
      type: Number,
      value: 0,
    },
    direction: {
      type: String,
      value: 'received',
    },
    status: {
      type: String,
      value: '',
    },
    showTime: {
      type: Boolean,
      value: false,
    },
    showAvatar: {
      type: Boolean,
      value: true,
    },
    avatarUrl: {
      type: String,
      value: '',
    },
  },
  lifetimes: {
    attached() {
      this.updateFormattedTime(this.data.timestamp);
      this.updateStatusLabel(this.data.status);
    },
  },
  observers: {
    timestamp(value: number) {
      this.updateFormattedTime(value);
    },
    status(value: string) {
      this.updateStatusLabel(value);
    },
  },
  methods: {
    updateFormattedTime(value: number | undefined) {
      const normalized = typeof value === 'number' ? value : undefined;
      this.setData({
        formattedTime: formatTimestamp(normalized),
      });
    },
    updateStatusLabel(value: string | undefined) {
      const label = (value && STATUS_LABELS[value as MessageStatus]) || '';
      this.setData({
        statusLabel: label,
      });
    },
  },
});
