import { getAvatarUrl } from '../../../utils/avatar';
import {
  fetchContactDetail,
  refreshStoredContact,
  updateContactDetail,
  type ContactUpdatePayload,
} from '../../utils/contact-service';
import { classifyError } from '../../../utils/error-classifier';
import { firstNonEmptyString, isNonEmptyString } from '../../../utils/guards';
import {
  getContactByConvId,
  getContacts,
  saveContacts,
  type StoredContact,
} from '../../../utils/storage';
import type { ContactProfile } from '../../../utils/schemas-core';
import { del } from '../../../utils/api';
import { clearLocalConversationState } from '../../utils/message/conversation-cleanup';
import { BasePageService } from './base-page-service';
import { createReadyScreenModel, type ScreenModel } from './page-state';

export type ContactRecord = StoredContact & {
  avatar_url?: string | null;
  username?: string | null;
  bio?: string | null;
  region?: string | null;
  displayAvatar: string;
};

export interface ContactInfoBootstrapResult {
  screenModel: ScreenModel;
  contact: ContactRecord | null;
}

export interface ContactInfoRefreshResult extends ContactInfoBootstrapResult {
  authInvalid: boolean;
}

const normalizeOptionalText = (value: string | null | undefined): string | undefined =>
  typeof value === 'string' && value.trim().length > 0 ? value : undefined;

const resolveOriginalAvatarSource = (
  contactRecord: ContactRecord,
  profile: ContactProfile
): string | undefined =>
  firstNonEmptyString(
    contactRecord.original_avatar_url ?? '',
    profile.avatar_url ?? '',
    contactRecord.avatar_url ?? ''
  );

const normalizeContact = (contact: StoredContact): ContactRecord => {
  const contactRecord = contact as ContactRecord;
  const profile: ContactProfile = contactRecord.profile ?? {};
  const normalizedOriginalAvatar = getAvatarUrl(
    resolveOriginalAvatarSource(contactRecord, profile) ?? null
  );
  const remarkAvatarSource = firstNonEmptyString(contactRecord.remark_avatar_url ?? '');
  const normalizedRemarkAvatar = isNonEmptyString(remarkAvatarSource)
    ? getAvatarUrl(remarkAvatarSource)
    : null;
  const avatarDisplayMode: 1 | 2 =
    contactRecord.avatar_display_mode === 2 && normalizedRemarkAvatar !== null ? 2 : 1;
  const normalizedAvatar =
    avatarDisplayMode === 2 && normalizedRemarkAvatar !== null
      ? normalizedRemarkAvatar
      : normalizedOriginalAvatar;

  return {
    ...contactRecord,
    avatar_display_mode: avatarDisplayMode,
    username: normalizeOptionalText(profile.username) ?? null,
    avatar_url: normalizedAvatar,
    remark_avatar_url: normalizedRemarkAvatar,
    original_avatar_url: normalizedOriginalAvatar,
    bio: normalizeOptionalText(profile.bio) ?? contactRecord.bio ?? null,
    region: normalizeOptionalText(profile.region) ?? contactRecord.region ?? null,
    displayAvatar: normalizedAvatar,
  };
};

export class ContactInfoPageService extends BasePageService {
  private async updateContactAndNormalize(
    convId: string,
    payload: ContactUpdatePayload
  ): Promise<ContactRecord> {
    const detail = await updateContactDetail(convId, payload);
    const updated = await refreshStoredContact(convId, detail);
    return normalizeContact(updated);
  }

  async bootstrap(convId: string): Promise<ContactInfoBootstrapResult | null> {
    if (!isNonEmptyString(convId)) {
      return {
        screenModel: createReadyScreenModel({ contentVariant: 'blank' }),
        contact: null,
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
      };
    }
    return {
      screenModel: createReadyScreenModel({ contentVariant: 'data' }),
      contact: normalizeContact(cachedContact),
    };
  }

  async refresh(
    convId: string,
    currentContact: ContactRecord | null
  ): Promise<ContactInfoRefreshResult | null> {
    if (!isNonEmptyString(convId)) {
      return {
        screenModel: createReadyScreenModel({ contentVariant: 'blank' }),
        contact: null,
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
        contact: normalizeContact(updated),
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

  async setAvatarDisplayMode(convId: string, mode: 1 | 2): Promise<ContactRecord> {
    return await this.updateContactAndNormalize(convId, { avatar_display_mode: mode });
  }

  async setRemarkAvatar(convId: string, avatarFileId: string): Promise<ContactRecord> {
    return await this.updateContactAndNormalize(convId, { avatar_file_id: avatarFileId });
  }

  async clearRemarkAvatar(convId: string): Promise<ContactRecord> {
    return await this.updateContactAndNormalize(convId, { avatar_file_id: null });
  }
}

export const createContactInfoPageService = (): ContactInfoPageService =>
  new ContactInfoPageService();
