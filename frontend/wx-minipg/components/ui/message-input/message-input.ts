type MessageInputEventDetail = {
  value: string;
  cursor?: number;
  keyCode?: number;
};

type KeyboardHeightChangeDetail = {
  height: number;
  duration: number;
};

type MessageInputConfirmDetail = {
  value: string;
  cursor?: number;
  keyCode?: number;
};

// Emoji list for message input (80 emojis)
const EMOJI_LIST = [
  '😀',
  '😃',
  '😄',
  '😁',
  '😆',
  '😅',
  '🤣',
  '😂',
  '🙂',
  '😊',
  '😇',
  '😍',
  '🥰',
  '😘',
  '😗',
  '😙',
  '😋',
  '😛',
  '😜',
  '🤪',
  '😝',
  '🤑',
  '🤗',
  '🤭',
  '🤔',
  '🤐',
  '🤨',
  '😐',
  '😑',
  '😶',
  '😏',
  '😒',
  '🙄',
  '😬',
  '🤥',
  '😌',
  '😔',
  '😪',
  '🤤',
  '😴',
  '😷',
  '🤒',
  '🤕',
  '🤢',
  '🤮',
  '🤧',
  '🥵',
  '🥶',
  '😎',
  '🤓',
  '🧐',
  '😕',
  '😟',
  '🙁',
  '☹️',
  '😮',
  '😯',
  '😲',
  '😳',
  '🥺',
  '😦',
  '😧',
  '😨',
  '😰',
  '😥',
  '😢',
  '😭',
  '😱',
  '😖',
  '😣',
  '😞',
  '😓',
  '👍',
  '👎',
  '👌',
  '✌️',
  '🤞',
  '🤝',
  '🙏',
  '❤️',
];

Component({
  options: {
    addGlobalClass: true,
    styleIsolation: 'apply-shared',
  },

  properties: {
    value: {
      type: String,
      value: '',
    },
    placeholder: {
      type: String,
      value: '请输入消息',
    },
    maxLength: {
      type: Number,
      value: 200,
    },
    disabled: {
      type: Boolean,
      value: false,
    },
    showEmoji: {
      type: Boolean,
      value: true,
    },
    showSend: {
      type: Boolean,
      value: true,
    },
    sendText: {
      type: String,
      value: '发送',
    },
    showCharCount: {
      type: Boolean,
      value: false,
    },
    cursor: {
      type: Number,
      value: 0,
    },
    autoHeight: {
      type: Boolean,
      value: true,
    },
  },

  data: {
    internalValue: '',
    showEmojiPanel: false,
    EMOJI_LIST,
  },

  observers: {
    value(value: string) {
      this.setData({ internalValue: value });
    },
  },

  methods: {
    handleInput(event: WechatMiniprogram.CustomEvent<MessageInputEventDetail>) {
      const value = event.detail.value;
      this.setData({ internalValue: value });
      this.triggerEvent('input', event.detail);
    },

    handleEmojiTap() {
      if (this.data.disabled) {
        return;
      }
      // Toggle emoji panel visibility
      this.setData({ showEmojiPanel: !this.data.showEmojiPanel });
    },

    handleEmojiSelect(event: WechatMiniprogram.TouchEvent) {
      const emoji = event.currentTarget.dataset.emoji as string;
      const newValue = this.data.internalValue + emoji;
      this.setData({ internalValue: newValue });
      // Emit input event to sync value with parent
      this.triggerEvent('input', { value: newValue });
    },

    handleSend() {
      if (this.data.disabled) {
        return;
      }
      this.triggerEvent('send', { value: this.data.internalValue });
    },

    handleKeyboardHeightChange(event: WechatMiniprogram.CustomEvent<KeyboardHeightChangeDetail>) {
      // Hide emoji panel when keyboard shows
      if (event.detail.height > 0) {
        this.setData({ showEmojiPanel: false });
      }
      this.triggerEvent('keyboardheightchange', event.detail);
    },

    handleConfirm(event: WechatMiniprogram.CustomEvent<MessageInputConfirmDetail>) {
      this.triggerEvent('confirm', event.detail);
    },
  },
});
