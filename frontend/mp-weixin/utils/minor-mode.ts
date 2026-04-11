import { requestValidated } from './api';
import {
  MinorModePinVerifyResponseSchema,
  MinorModeStatusSchema,
  type MinorModePinVerifyResponse,
  type MinorModeStatus,
} from './schemas';
import { getLogger } from './logger';

const MINOR_MODE_ENDPOINT = '/user/minor-mode';
const MINOR_MODE_STATUS_CACHE_KEY = 'minor_mode_status';
const logger = getLogger('MinorModeApi');

export const MINOR_MODE_DISCOVERY_BLOCK_START_HOUR = 22;
export const MINOR_MODE_DISCOVERY_BLOCK_END_HOUR = 6;

const saveCachedMinorModeStatus = (status: MinorModeStatus): void => {
  try {
    wx.setStorageSync(MINOR_MODE_STATUS_CACHE_KEY, status);
  } catch (error: unknown) {
    logger.warn('Failed to cache minor mode status', { error });
  }
};

export const getCachedMinorModeStatus = (): MinorModeStatus | null => {
  try {
    const stored = wx.getStorageSync<MinorModeStatus | null>(MINOR_MODE_STATUS_CACHE_KEY);
    if (stored === null || typeof stored !== 'object') {
      return null;
    }
    const parsed = MinorModeStatusSchema.safeParse(stored);
    if (!parsed.success) {
      return null;
    }
    return parsed.data;
  } catch (error: unknown) {
    logger.warn('Failed to read cached minor mode status', { error });
    return null;
  }
};

export async function fetchMinorModeStatus(): Promise<MinorModeStatus> {
  const status = await requestValidated(MinorModeStatusSchema, {
    url: MINOR_MODE_ENDPOINT,
    method: 'GET',
  });
  saveCachedMinorModeStatus(status);
  return status;
}

export async function enableMinorMode(pin: string): Promise<MinorModeStatus> {
  const status = await requestValidated(MinorModeStatusSchema, {
    url: `${MINOR_MODE_ENDPOINT}/enable`,
    method: 'PUT',
    data: { pin },
  });
  saveCachedMinorModeStatus(status);
  return status;
}

export async function disableMinorMode(pin: string): Promise<MinorModeStatus> {
  const status = await requestValidated(MinorModeStatusSchema, {
    url: `${MINOR_MODE_ENDPOINT}/disable`,
    method: 'PUT',
    data: { pin },
  });
  saveCachedMinorModeStatus(status);
  return status;
}

export async function updateMinorModePin(oldPin: string, newPin: string): Promise<MinorModeStatus> {
  const status = await requestValidated(MinorModeStatusSchema, {
    url: `${MINOR_MODE_ENDPOINT}/pin`,
    method: 'PUT',
    data: {
      old_pin: oldPin,
      new_pin: newPin,
    },
  });
  saveCachedMinorModeStatus(status);
  return status;
}

export async function verifyMinorModePin(pin: string): Promise<MinorModePinVerifyResponse> {
  return await requestValidated(MinorModePinVerifyResponseSchema, {
    url: `${MINOR_MODE_ENDPOINT}/pin/verify`,
    method: 'POST',
    data: { pin },
  });
}

export function isMinorModeDiscoveryBlockedAt(date: Date): boolean {
  const hour = date.getHours();
  return (
    hour >= MINOR_MODE_DISCOVERY_BLOCK_START_HOUR || hour < MINOR_MODE_DISCOVERY_BLOCK_END_HOUR
  );
}

export function isMinorModeDiscoveryBlockedNow(): boolean {
  return isMinorModeDiscoveryBlockedAt(new Date());
}

export function isMinorModeDiscoveryRestricted(status: MinorModeStatus | null): boolean {
  return status?.enabled === true && isMinorModeDiscoveryBlockedNow();
}

export type { MinorModeStatus, MinorModePinVerifyResponse };
