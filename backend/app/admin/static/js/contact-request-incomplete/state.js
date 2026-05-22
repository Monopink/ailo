export const STATUS_LABELS = {
  1: 'PENDING',
  2: 'ACCEPTED',
  3: 'IGNORED',
  8: 'PROCESSING',
  9: 'FAILED',
};

export const CONTACT_TYPE_USER = 1;

export function createPageState() {
  return {
    rows: [],
    aiTypeOptions: new Map(),
    failureOptions: new Map(),
    page: 1,
    pageSize: 20,
    total: 0,
  };
}
