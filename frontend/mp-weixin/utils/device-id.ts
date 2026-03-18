/**
 * Device ID utilities
 * Generates installation-level UUID v4 identifiers.
 */

export const generateDeviceId = (): string =>
  'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (char) => {
    const value = Math.floor(Math.random() * 16);
    const mapped = char === 'x' ? value : (value & 0x3) | 0x8;
    return mapped.toString(16);
  });
