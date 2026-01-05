export const hasValue = <T>(value: T | null | undefined): value is T =>
  value !== null && value !== undefined;

export const isNonEmptyString = (value: unknown): value is string =>
  typeof value === 'string' && value.trim() !== '';

export const firstNonEmptyString = (
  ...values: Array<string | null | undefined>
): string | undefined => values.find(isNonEmptyString);

export const ensureArray = <T>(value: T[] | null | undefined): T[] =>
  Array.isArray(value) ? value : [];

export const isPositiveNumber = (value: unknown): value is number =>
  typeof value === 'number' && !Number.isNaN(value);
