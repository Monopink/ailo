import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { previewMockData, type PreviewSquareContact } from '../preview-common/data';
import { isValidCategoryKey } from '../../utils/constants/square';
import { ensurePreviewAccess } from '../../utils/runtime-segment';
import { promptContactRequestMessage } from '../utils/contact-request';

interface PreviewContactPageData {
  pageLayoutData: PageLayoutData;
  contacts: PreviewSquareContact[];
  selectedContact: PreviewSquareContact | null;
  activeCategoryKey: string;
}

interface PreviewContactPageCustom {
  getContactsByActiveCategory(): PreviewSquareContact[];
  syncSelectedContact(contacts: PreviewSquareContact[]): PreviewSquareContact | null;
  handleAddTap(event: WechatMiniprogram.BaseEvent): Promise<void>;
  handleBack(): void;
}

const getDatasetValue = (event: WechatMiniprogram.BaseEvent, key: string): unknown => {
  const dataset = event.currentTarget.dataset as Record<string, unknown> | undefined;
  return dataset?.[key];
};

const resolveString = (value: unknown): string | null =>
  typeof value === 'string' && value.trim() !== '' ? value : null;

const showToast = (title: string): void => {
  void wx.showToast({ title, icon: 'none' });
};

Page<PreviewContactPageData, PreviewContactPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
      emptyMessage: '暂无内容',
      hasFooter: false,
    }),
    contacts: previewMockData.listContacts(),
    selectedContact: null,
    activeCategoryKey: '',
  },

  onLoad(options?: Record<string, string | undefined>) {
    if (!ensurePreviewAccess('/pkg/preview-contact/preview-contact')) {
      return;
    }
    const categoryKeyRaw = resolveString(options?.category_key);
    const activeCategoryKey =
      categoryKeyRaw !== null && isValidCategoryKey(categoryKeyRaw) ? categoryKeyRaw : '';
    const contacts =
      activeCategoryKey === ''
        ? previewMockData.listContacts()
        : previewMockData.listSquareContacts(activeCategoryKey);
    const selectedId = resolveString(options?.qiao_id);
    const selectedContact =
      selectedId === null ? null : (contacts.find((item) => item.qiaoId === selectedId) ?? null);
    this.setData({
      contacts,
      selectedContact,
      activeCategoryKey,
    });
  },

  getContactsByActiveCategory() {
    if (this.data.activeCategoryKey === '') {
      return previewMockData.listContacts();
    }
    return previewMockData.listSquareContacts(this.data.activeCategoryKey);
  },

  syncSelectedContact(contacts: PreviewSquareContact[]) {
    const selectedId = this.data.selectedContact?.qiaoId ?? null;
    if (selectedId === null) {
      return null;
    }
    return contacts.find((item) => item.qiaoId === selectedId) ?? null;
  },

  onShow() {
    if (!ensurePreviewAccess('/pkg/preview-contact/preview-contact')) {
      return;
    }
    const contacts = this.getContactsByActiveCategory();
    this.setData({
      contacts,
      selectedContact: this.syncSelectedContact(contacts),
    });
  },

  async handleAddTap(event: WechatMiniprogram.BaseEvent) {
    const qiaoId = resolveString(getDatasetValue(event, 'id'));
    if (qiaoId === null) {
      return;
    }
    const message = await promptContactRequestMessage();
    if (message === null) {
      return;
    }
    const added = previewMockData.addContact(qiaoId);
    if (!added) {
      return;
    }
    const contacts = this.getContactsByActiveCategory();
    this.setData({
      contacts,
      selectedContact: this.syncSelectedContact(contacts),
    });
    showToast(message.trim() === '' ? '已提交' : '已发送');
  },

  handleBack() {
    void wx.navigateBack();
  },
});
