const normalizeDecodedParam = (raw: string | undefined): string => {
  if (typeof raw !== 'string') {
    return '';
  }
  const trimmed = raw.trim();
  if (trimmed === '') {
    return '';
  }
  try {
    return decodeURIComponent(trimmed).trim().toUpperCase();
  } catch {
    return trimmed.toUpperCase();
  }
};

export const normalizeInviteCodeParam = (raw: string | undefined): string =>
  normalizeDecodedParam(raw);

export const normalizeCampaignCodeParam = (raw: string | undefined): string =>
  normalizeDecodedParam(raw);
