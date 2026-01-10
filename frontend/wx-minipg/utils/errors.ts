import { isNonEmptyString } from './guards';

export const normalizeError = (error: unknown): Error => {
  if (error instanceof Error) {
    return error;
  }
  if (typeof error === 'string') {
    return new Error(error);
  }
  try {
    return new Error(JSON.stringify(error));
  } catch {
    return new Error('Unknown error');
  }
};

export const getErrorMessage = (error: unknown, fallback: string): string => {
  const normalized = normalizeError(error);
  return isNonEmptyString(normalized.message) ? normalized.message : fallback;
};
