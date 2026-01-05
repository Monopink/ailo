import { requestValidated } from './api';
import { getContacts, saveContacts } from './storage';
import { ContactProfile, ConversationResponseSchema, StoredContact } from './schemas';

const buildConversationEndpoint = (convId: string): string => `/contacts/${convId}/conversation`;

export async function fetchConversationProfile(convId: string): Promise<ContactProfile | null> {
  const result = await requestValidated(ConversationResponseSchema, {
    url: buildConversationEndpoint(convId),
    method: 'GET',
  });
  return result.profile ?? null;
}

export async function refreshStoredContact(
  convId: string,
  profile: ContactProfile | null
): Promise<StoredContact | null> {
  const contacts = await getContacts();
  const index = contacts.findIndex((contact) => contact.conv_id === convId);
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
