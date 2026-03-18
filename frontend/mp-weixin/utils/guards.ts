export const isDefined = <T>(value: T | null | undefined): value is T =>
  value !== null && value !== undefined;

export const isNonEmptyString = (value: string | null | undefined): value is string =>
  typeof value === 'string' && value.trim().length > 0;

export const isStrictNumber = (value: number | null | undefined): value is number =>
  typeof value === 'number' && !Number.isNaN(value);

export const isNonEmptyArray = <T>(value: T[] | null | undefined): value is T[] =>
  Array.isArray(value) && value.length > 0;

export const hasValue = <T>(value: T | null | undefined): value is T =>
  value !== null && value !== undefined;

export const firstNonEmptyString = (
  ...values: Array<string | null | undefined>
): string | undefined => values.find(isNonEmptyString);

export const isPositiveNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value) && value > 0;
