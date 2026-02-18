import { requestValidated } from './api';
import { getAvatarUrl } from './avatar';
import { getLogger } from './logger';
import { firstNonEmptyString, isNonEmptyString } from './guards';
import conversationStore from './message/conversation-store';
import { getContacts, saveContacts } from './storage';
import {
  ContactProfile,
  ConversationResponse,
  ConversationResponseSchema,
  StoredContact,
} from './schemas';

const buildConversationEndpoint = (convId: string): string => `/contacts/${convId}/conversation`;
const logger = getLogger('ContactService');

async function resolveAuthoritativeImConvId(compatImConvId: string): Promise<string> {
  let authoritativeImConvId = await conversationStore.getImConvId();
  if (!isNonEmptyString(authoritativeImConvId)) {
    const refreshed = await conversationStore.refresh();
    authoritativeImConvId = refreshed.im_conv_id;
  }

  if (!isNonEmptyString(authoritativeImConvId)) {
    throw new Error('IM_CONVERSATION_ID_MISSING');
  }

  if (isNonEmptyString(compatImConvId) && compatImConvId !== authoritativeImConvId) {
    logger.warn('im_conv_id mismatch between contacts and lc-im config', {
      compatImConvId,
      authoritativeImConvId,
    });
    try {
      const refreshed = await conversationStore.refresh();
      if (isNonEmptyString(refreshed.im_conv_id)) {
        authoritativeImConvId = refreshed.im_conv_id;
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      logger.warn('Failed to refresh authoritative im_conv_id after mismatch', { message });
    }
  }

  return authoritativeImConvId;
}

export interface ChatContactViewModel {
  convId: string;
  contactQiaoId: string;
  imConvId: string;
  displayName: string;
  displayAvatar: string;
  profile: ContactProfile;
}

export async function fetchConversationProfile(convId: string): Promise<ContactProfile | null> {
  const result = await requestValidated(ConversationResponseSchema, {
    url: buildConversationEndpoint(convId),
    method: 'GET',
  });
  return result.profile;
}

export async function refreshStoredContact(
  convId: string,
  profile: ContactProfile | null
): Promise<StoredContact | null> {
  const contacts = await getContacts();
  const index = contacts.findIndex((contact) => contact.conversation_id === convId);
  if (index === -1) {
    return null;
  }

  const existing = contacts[index];
  const updated: StoredContact = {
    ...existing,
    profile: {
      ...(existing.profile ?? {}),
      ...(profile ?? {}),
    },
  };

  contacts[index] = updated;
  await saveContacts(contacts);

  return updated;
}

function mergeContactProfile(
  stored: ContactProfile | null | undefined,
  incoming: ContactProfile
): ContactProfile {
  return {
    nickname: firstNonEmptyString(incoming.nickname ?? '', stored?.nickname ?? '') ?? '',
    avatar_url: firstNonEmptyString(incoming.avatar_url ?? '', stored?.avatar_url ?? '') ?? '',
    gender: incoming.gender ?? stored?.gender ?? null,
    bio: firstNonEmptyString(incoming.bio ?? '', stored?.bio ?? '') ?? null,
    region: firstNonEmptyString(incoming.region ?? '', stored?.region ?? '') ?? null,
  };
}

export async function fetchConversationInfo(convId: string): Promise<ConversationResponse> {
  return await requestValidated(ConversationResponseSchema, {
    url: buildConversationEndpoint(convId),
    method: 'GET',
  });
}

export async function getChatContactViewModel(convId: string): Promise<ChatContactViewModel> {
  const conversation = await fetchConversationInfo(convId);
  const contactInfo = conversation.profile;
  if (conversation.conversation_id !== convId) {
    throw new Error('CONVERSATION_ID_MISMATCH');
  }

  if (!isNonEmptyString(conversation.contact_qiao_id)) {
    throw new Error('CONTACT_QIAO_ID_MISSING');
  }
  const imConvId = await resolveAuthoritativeImConvId(conversation.im_conv_id);

  const contacts = await getContacts();
  const index = contacts.findIndex((contact) => contact.conversation_id === convId);

  const storedContact = index === -1 ? null : contacts[index];
  const mergedProfile = mergeContactProfile(storedContact?.profile ?? null, contactInfo);
  const displayName =
    firstNonEmptyString(storedContact?.alias ?? '', mergedProfile.nickname ?? '') ?? '';
  const displayAvatar = getAvatarUrl(mergedProfile.avatar_url ?? '');

  if (index !== -1) {
    const baseContact = contacts[index];
    const updated: StoredContact = {
      ...baseContact,
      conversation_id: baseContact.conversation_id,
      contact_qiao_id: conversation.contact_qiao_id,
      im_conv_id: imConvId,
      profile: {
        ...(baseContact.profile ?? {}),
        ...mergedProfile,
      },
    };
    contacts[index] = updated;
    await saveContacts(contacts);
    logger.info('Chat contact info updated', { convId });
  }

  return {
    convId,
    contactQiaoId: conversation.contact_qiao_id,
    imConvId,
    displayName,
    displayAvatar,
    profile: mergedProfile,
  };
}
