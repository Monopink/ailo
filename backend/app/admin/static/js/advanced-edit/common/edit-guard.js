export function serializeSnapshot(payload) {
  return JSON.stringify(payload);
}

export function createSnapshotGuard(options) {
  const { buildPayload } = options;
  let lastSavedSnapshot = serializeSnapshot(buildPayload());
  const guard = window.qiaoUnsavedGuard.create({
    isDirty: () => serializeSnapshot(buildPayload()) !== lastSavedSnapshot,
  });
  return {
    guard,
    markSaved(payload) {
      if (payload === undefined) {
        lastSavedSnapshot = serializeSnapshot(buildPayload());
        return;
      }
      lastSavedSnapshot = serializeSnapshot(payload);
    },
  };
}
