import { requestValidated } from '../../utils/api';
import { getAvatarUrl } from '../../utils/avatar';
import { firstNonEmptyString, isNonEmptyString } from '../../utils/guards';
import { getLogger } from '../../utils/logger';
import conversationStore from '../../utils/message/conversation-store';
import { getContacts, saveContacts } from '../../utils/storage';
import { ContactProfile, StoredContact, StoredContactSchema } from '../../utils/schemas';

const buildContactEndpoint = (convId: string): string => `/contacts/${convId}`;
const logger = getLogger('ContactService');

export interface ContactUpdatePayload {
  alias?: string | null;
  remark?: string | null;
  tags?: string[];
  avatar_file_id?: string | null;
  avatar_display_mode?: 1 | 2;
}

const mergeOptionalText = (
  incoming: string | null | undefined,
  stored: string | null | undefined,
  emptyValue: string | null
): string | null => firstNonEmptyString(incoming ?? '', stored ?? '') ?? emptyValue;

const hasOwnContactField = <K extends keyof StoredContact>(
  contact: StoredContact,
  field: K
): boolean => Object.prototype.hasOwnProperty.call(contact, field);

const mergeNullableContactField = (
  existing: StoredContact | null,
  incoming: StoredContact,
  field: 'alias' | 'remark' | 'avatar_url' | 'remark_avatar_url' | 'original_avatar_url'
): string | null => {
  if (hasOwnContactField(incoming, field)) {
    return incoming[field] ?? null;
  }
  return existing?.[field] ?? null;
};

const mergeContactTags = (existing: StoredContact | null, incoming: StoredContact): string[] => {
  if (hasOwnContactField(incoming, 'tags')) {
    return incoming.tags ?? [];
  }
  return existing?.tags ?? [];
};

const mergeAvatarDisplayMode = (
  existing: StoredContact | null,
  incoming: StoredContact
): 1 | 2 | undefined => {
  if (hasOwnContactField(incoming, 'avatar_display_mode')) {
    return incoming.avatar_display_mode ?? existing?.avatar_display_mode;
  }
  return existing?.avatar_display_mode;
};

async function resolveAuthoritativeImConvId(): Promise<string> {
  let authoritativeImConvId = await conversationStore.getImConvId();
  if (!isNonEmptyString(authoritativeImConvId)) {
    const refreshed = await conversationStore.refresh();
    authoritativeImConvId = refreshed.session.im_conv_id;
  }
  if (!isNonEmptyString(authoritativeImConvId)) {
    throw new Error('IM_CONVERSATION_ID_MISSING');
  }
  return authoritativeImConvId;
}

const mergeContactProfile = (
  stored: ContactProfile | null | undefined,
  incoming: ContactProfile | null | undefined
): ContactProfile => ({
  nickname: mergeOptionalText(incoming?.nickname, stored?.nickname, ''),
  avatar_url: mergeOptionalText(incoming?.avatar_url, stored?.avatar_url, ''),
  gender: incoming?.gender ?? stored?.gender ?? null,
  bio: mergeOptionalText(incoming?.bio, stored?.bio, null),
  region: mergeOptionalText(incoming?.region, stored?.region, null),
  username: mergeOptionalText(incoming?.username, stored?.username, null),
});

const mergeStoredContact = (
  existing: StoredContact | null,
  incoming: StoredContact
): StoredContact => ({
  ...(existing ?? {}),
  ...incoming,
  conversation_id: incoming.conversation_id,
  contact_qiao_id: incoming.contact_qiao_id ?? existing?.contact_qiao_id,
  im_conv_id: incoming.im_conv_id ?? existing?.im_conv_id,
  // Respect explicit null/empty values from API responses.
  alias: mergeNullableContactField(existing, incoming, 'alias'),
  remark: mergeNullableContactField(existing, incoming, 'remark'),
  tags: mergeContactTags(existing, incoming),
  avatar_url: mergeNullableContactField(existing, incoming, 'avatar_url'),
  remark_avatar_url: mergeNullableContactField(existing, incoming, 'remark_avatar_url'),
  original_avatar_url: mergeNullableContactField(existing, incoming, 'original_avatar_url'),
  avatar_display_mode: mergeAvatarDisplayMode(existing, incoming),
  profile: mergeContactProfile(existing?.profile ?? null, incoming.profile ?? null),
});

export interface ChatContactViewModel {
  convId: string;
  contactQiaoId: string;
  contactType: 1 | 2 | 3 | null;
  imConvId: string;
  displayName: string;
  displayAvatar: string;
  profile: ContactProfile;
}

export async function fetchContactDetail(convId: string): Promise<StoredContact> {
  const result = await requestValidated(StoredContactSchema, {
    url: buildContactEndpoint(convId),
    method: 'GET',
  });
  if (result.conversation_id !== convId) {
    throw new Error('CONVERSATION_ID_MISMATCH');
  }
  return result;
}

export async function updateContactDetail(
  convId: string,
  payload: ContactUpdatePayload
): Promise<StoredContact> {
  const result = await requestValidated(StoredContactSchema, {
    url: buildContactEndpoint(convId),
    method: 'PUT',
    data: payload,
  });
  if (result.conversation_id !== convId) {
    throw new Error('CONVERSATION_ID_MISMATCH');
  }
  return result;
}

export async function refreshStoredContact(
  convId: string,
  detail: StoredContact
): Promise<StoredContact> {
  const contacts = await getContacts();
  const index = contacts.findIndex((contact) => contact.conversation_id === convId);
  const existing = index === -1 ? null : contacts[index];
  const updated = mergeStoredContact(existing, detail);

  if (index === -1) {
    contacts.push(updated);
  } else {
    contacts[index] = updated;
  }
  await saveContacts(contacts);
  return updated;
}

export async function getChatContactViewModel(convId: string): Promise<ChatContactViewModel> {
  const detail = await fetchContactDetail(convId);
  const source = await refreshStoredContact(convId, detail);
  const profile = source.profile ?? {};

  if (!isNonEmptyString(source.contact_qiao_id)) {
    throw new Error('CONTACT_QIAO_ID_MISSING');
  }

  const imConvId = await resolveAuthoritativeImConvId();
  const displayName = firstNonEmptyString(source.alias ?? '', profile.nickname ?? '') ?? '';
  const displayAvatar = getAvatarUrl(
    firstNonEmptyString(source.avatar_url ?? '', profile.avatar_url ?? '') ?? ''
  );

  logger.info('Chat contact info updated', { convId });

  return {
    convId,
    contactQiaoId: source.contact_qiao_id,
    contactType: typeof source.contact_type === 'number' ? source.contact_type : null,
    imConvId,
    displayName,
    displayAvatar,
    profile,
  };
}
