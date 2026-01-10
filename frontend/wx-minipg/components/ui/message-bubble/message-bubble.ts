type BubbleDirection = 'incoming' | 'outgoing';
type MessageStatus = 'sending' | 'sent' | 'failed';

const DIRECTIONS: BubbleDirection[] = ['incoming', 'outgoing'];
const STATUS_LABELS: Record<MessageStatus, string> = {
  sending: '发送中',
  sent: '已送达',
  failed: '发送失败',
};

Component({
  options: {
    addGlobalClass: true,
    styleIsolation: 'apply-shared',
  },

  properties: {
    direction: {
      type: String,
      value: 'incoming',
    },
    text: {
      type: String,
      value: '',
    },
    time: {
      type: String,
      value: '',
    },
    avatar: {
      type: String,
      value: '',
    },
    status: {
      type: String,
      value: '',
    },
  },

  data: {
    normalizedDirection: 'incoming' as BubbleDirection,
    statusLabel: '',
  },

  observers: {
    direction(value: string) {
      this._normalizeDirection(value);
    },
    status(value: string) {
      this._updateStatusLabel(value as MessageStatus);
    },
  },

  lifetimes: {
    attached() {
      this._normalizeDirection(this.data.direction);
      this._updateStatusLabel(this.data.status as MessageStatus);
    },
  },

  methods: {
    _normalizeDirection(value: string) {
      const direction = (
        DIRECTIONS.includes(value as BubbleDirection) ? value : 'incoming'
      ) as BubbleDirection;
      this.setData({ normalizedDirection: direction });
    },

    _updateStatusLabel(value: MessageStatus) {
      const label = STATUS_LABELS[value];
      this.setData({ statusLabel: label });
    },
  },
});
