import { getAvatarUrl } from '../../utils/avatar';
import { fetchContactDetail, refreshStoredContact } from '../../utils/contact-service';
import { classifyError } from '../../utils/error-classifier';
import { isNonEmptyString } from '../../utils/guards';
import {
  getContactByConvId,
  getContacts,
  saveContacts,
  type StoredContact,
} from '../../utils/storage';
import type { ContactProfile } from '../../utils/schemas';
import { del } from '../../utils/api';
import { clearLocalConversationState } from '../../utils/message/conversation-cleanup';
import { BasePageService } from './base-page-service';
import { createReadyScreenModel, type ScreenModel } from './page-state';

export interface ContactView {
  avatar: string;
  name: string;
  genderLabel: string;
  genderType: 'success' | 'danger' | 'default';
  hasGender: boolean;
  displayQiaoId: string;
}

export interface ChatDetailBootstrapResult {
  screenModel: ScreenModel;
  contact: StoredContact | null;
  contactView: ContactView;
}

export interface ChatDetailRefreshResult extends ChatDetailBootstrapResult {
  authInvalid: boolean;
}

const DEFAULT_CONTACT_AVATAR = getAvatarUrl(null);

const createEmptyContactView = (): ContactView => ({
  avatar: DEFAULT_CONTACT_AVATAR,
  name: '',
  genderLabel: '',
  genderType: 'default',
  hasGender: false,
  displayQiaoId: '',
});

const sanitizeNameCandidate = (value: string | null | undefined): string | undefined =>
  isNonEmptyString(value) ? value : undefined;

const getDisplayName = (contact: StoredContact, profile: ContactProfile): string =>
  sanitizeNameCandidate(contact.alias) ??
  sanitizeNameCandidate(profile.nickname) ??
  sanitizeNameCandidate(contact.contact_qiao_id) ??
  '';

const getResolvedAvatar = (contact: StoredContact, profile: ContactProfile): string => {
  const avatarUrl = isNonEmptyString(contact.avatar_url)
    ? contact.avatar_url
    : isNonEmptyString(profile.avatar_url)
      ? profile.avatar_url
      : null;
  const candidate = getAvatarUrl(avatarUrl);
  return isNonEmptyString(candidate) ? candidate : DEFAULT_CONTACT_AVATAR;
};

const getDisplayQiaoId = (contact: StoredContact): string =>
  isNonEmptyString(contact.contact_qiao_id) ? contact.contact_qiao_id : '';

const getGenderLabel = (genderValue: number | null): string =>
  genderValue === 1 ? '男' : genderValue === 2 ? '女' : genderValue === 3 ? '其他' : '';

const buildContactView = (contact: StoredContact, profile?: ContactProfile): ContactView => {
  const resolvedProfile: ContactProfile = profile ?? contact.profile ?? {};
  const genderValue = typeof resolvedProfile.gender === 'number' ? resolvedProfile.gender : null;
  const genderLabel = getGenderLabel(genderValue);

  return {
    avatar: getResolvedAvatar(contact, resolvedProfile),
    name: getDisplayName(contact, resolvedProfile),
    genderLabel,
    genderType: genderValue === 1 ? 'success' : genderValue === 2 ? 'danger' : 'default',
    hasGender: genderLabel !== '',
    displayQiaoId: getDisplayQiaoId(contact),
  };
};

export class ChatDetailPageService extends BasePageService {
  async bootstrap(convId: string): Promise<ChatDetailBootstrapResult | null> {
    if (!isNonEmptyString(convId)) {
      return {
        screenModel: createReadyScreenModel({ contentVariant: 'blank' }),
        contact: null,
        contactView: createEmptyContactView(),
      };
    }
    const seq = this.startRequest();
    const cachedContact = await getContactByConvId(convId);
    if (!this.isRequestActive(seq)) {
      return null;
    }
    if (cachedContact === null) {
      return {
        screenModel: createReadyScreenModel({ contentVariant: 'blank' }),
        contact: null,
        contactView: createEmptyContactView(),
      };
    }
    return {
      screenModel: createReadyScreenModel({ contentVariant: 'data' }),
      contact: cachedContact,
      contactView: buildContactView(cachedContact),
    };
  }

  async refresh(
    convId: string,
    currentContact: StoredContact | null
  ): Promise<ChatDetailRefreshResult | null> {
    if (!isNonEmptyString(convId)) {
      return {
        screenModel: createReadyScreenModel({ contentVariant: 'blank' }),
        contact: null,
        contactView: createEmptyContactView(),
        authInvalid: false,
      };
    }

    const seq = this.startRequest();
    try {
      const detail = await fetchContactDetail(convId);
      const updated = await refreshStoredContact(convId, detail);
      if (!this.isRequestActive(seq)) {
        return null;
      }
      return {
        screenModel: createReadyScreenModel({
          contentVariant: 'data',
          refreshState: 'idle',
        }),
        contact: updated,
        contactView: buildContactView(updated),
        authInvalid: false,
      };
    } catch (error: unknown) {
      const semantics = classifyError(error);
      if (!this.isRequestActive(seq)) {
        return null;
      }
      return {
        screenModel: createReadyScreenModel({
          contentVariant: currentContact === null ? 'blank' : 'data',
          refreshState: 'degraded',
        }),
        contact: currentContact,
        contactView:
          currentContact === null ? createEmptyContactView() : buildContactView(currentContact),
        authInvalid: semantics.reason === 'auth-invalid',
      };
    }
  }

  async clearChatHistory(convId: string): Promise<void> {
    await clearLocalConversationState(convId);
  }

  async deleteContact(convId: string): Promise<void> {
    await del(`/contacts/${convId}`);
    const contacts = await getContacts();
    const updatedContacts = contacts.filter((contact) => contact.conversation_id !== convId);
    await saveContacts(updatedContacts);
    await clearLocalConversationState(convId);
  }
}

export const createChatDetailPageService = (): ChatDetailPageService => new ChatDetailPageService();
