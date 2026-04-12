/**
 * Schema barrel module.
 *
 * - `schemas-core`: type-only exports (no runtime dependency on zod)
 * - `schemas-validation`: runtime validation schemas based on zod
 */

export type * from './schemas-core';
export * from './schemas-validation';
