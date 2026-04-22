import { get, requestValidated } from './api';
import { getLogger } from './logger';
import { isNonEmptyString } from './guards';
import { type ContactLimitResponse } from './schemas-core';
import { ContactLimitResponseSchema } from './schemas-validation';
import type { StoredContacts } from './storage';

const logger = getLogger('ContactSync');

const CONTACTS_PAGE_LIMIT = 50;
const MAX_CONTACT_PAGES = 20;

interface ContactsPagination {
  cursor?: string;
  has_more?: boolean;
}

export interface ContactsPageResponse {
  items?: StoredContacts;
  pagination?: ContactsPagination;
}

const CONTACT_LIMIT_ENDPOINT = '/contacts/limit';

export async function fetchContactLimitFromApi(): Promise<ContactLimitResponse> {
  return await requestValidated(ContactLimitResponseSchema, {
    url: CONTACT_LIMIT_ENDPOINT,
    method: 'GET',
  });
}

export async function fetchAllContactsFromApi(
  limit = CONTACTS_PAGE_LIMIT
): Promise<StoredContacts> {
  const aggregated: StoredContacts = [];
  let cursor: string | undefined;
  let hasMore = true;
  let pageCount = 0;

  while (hasMore) {
    const params: Record<string, string | number> = { limit };
    if (isNonEmptyString(cursor)) {
      params.cursor = cursor;
    }

    // eslint-disable-next-line no-await-in-loop
    const response = await get<ContactsPageResponse>('/contacts', params);
    const items = Array.isArray(response.items) ? response.items : [];
    aggregated.push(...items);

    const pagination = response.pagination;
    const candidateCursor = pagination?.cursor;
    const nextCursor = isNonEmptyString(candidateCursor) ? candidateCursor : '';
    const hasMorePagination = pagination?.has_more === true && isNonEmptyString(nextCursor);
    hasMore = hasMorePagination;
    cursor = hasMorePagination ? nextCursor : undefined;
    pageCount += 1;

    if (pageCount >= MAX_CONTACT_PAGES) {
      logger.warn('Contact list pagination aborted due to safety limit', { pageCount });
      break;
    }
  }

  return aggregated;
}
