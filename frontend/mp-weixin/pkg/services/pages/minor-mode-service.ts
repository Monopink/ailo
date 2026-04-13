import { classifyError } from '../../../utils/error-classifier';
import {
  disableMinorMode,
  enableMinorMode,
  fetchMinorModeStatus,
  updateMinorModePin,
  verifyMinorModePin,
  type MinorModeStatus,
} from '../../../utils/minor-mode';
import { BasePageService } from './base-page-service';

export interface MinorModeLoadResult {
  status: MinorModeStatus | null;
  authInvalid: boolean;
}

export interface MinorModeMutationResult {
  status: MinorModeStatus | null;
  authInvalid: boolean;
  reason: string | null;
}

export interface MinorModeVerifyResult {
  verified: boolean | null;
  authInvalid: boolean;
  reason: string | null;
}

interface ErrorLike {
  reason?: string;
}

const resolveReason = (error: unknown): string | null => {
  if (typeof error !== 'object' || error === null) {
    return null;
  }
  const candidate = (error as ErrorLike).reason;
  return typeof candidate === 'string' ? candidate : null;
};

export class MinorModePageService extends BasePageService {
  async load(): Promise<MinorModeLoadResult | null> {
    const seq = this.startRequest();
    try {
      const status = await fetchMinorModeStatus();
      if (!this.isRequestActive(seq)) {
        return null;
      }
      return {
        status,
        authInvalid: false,
      };
    } catch (error: unknown) {
      if (!this.isRequestActive(seq)) {
        return null;
      }
      const semantics = classifyError(error);
      return {
        status: null,
        authInvalid: semantics.reason === 'auth-invalid',
      };
    }
  }

  async enable(pin: string): Promise<MinorModeMutationResult> {
    try {
      const status = await enableMinorMode(pin);
      return {
        status,
        authInvalid: false,
        reason: null,
      };
    } catch (error: unknown) {
      const semantics = classifyError(error);
      return {
        status: null,
        authInvalid: semantics.reason === 'auth-invalid',
        reason: resolveReason(error),
      };
    }
  }

  async disable(pin: string): Promise<MinorModeMutationResult> {
    try {
      const status = await disableMinorMode(pin);
      return {
        status,
        authInvalid: false,
        reason: null,
      };
    } catch (error: unknown) {
      const semantics = classifyError(error);
      return {
        status: null,
        authInvalid: semantics.reason === 'auth-invalid',
        reason: resolveReason(error),
      };
    }
  }

  async updatePin(oldPin: string, newPin: string): Promise<MinorModeMutationResult> {
    try {
      const status = await updateMinorModePin(oldPin, newPin);
      return {
        status,
        authInvalid: false,
        reason: null,
      };
    } catch (error: unknown) {
      const semantics = classifyError(error);
      return {
        status: null,
        authInvalid: semantics.reason === 'auth-invalid',
        reason: resolveReason(error),
      };
    }
  }

  async verifyPin(pin: string): Promise<MinorModeVerifyResult> {
    try {
      const result = await verifyMinorModePin(pin);
      return {
        verified: result.verified,
        authInvalid: false,
        reason: null,
      };
    } catch (error: unknown) {
      const semantics = classifyError(error);
      return {
        verified: null,
        authInvalid: semantics.reason === 'auth-invalid',
        reason: resolveReason(error),
      };
    }
  }
}

export const createMinorModePageService = (): MinorModePageService => new MinorModePageService();
