/**
 * Type-only schema exports.
 *
 * Keep this module free of runtime dependencies to avoid pulling zod into
 * call sites that only need TypeScript types.
 */

export type * from './schemas-validation';

export interface RuntimeSchema<TOutput = unknown> {
  parse(data: unknown): TOutput;
}
