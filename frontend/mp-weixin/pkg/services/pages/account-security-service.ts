import accountService, { type AccountViewModel } from '../../utils/account-service';
import { classifyError } from '../../../utils/error-classifier';
import {
  fetchMinorModeStatus,
  getCachedMinorModeStatus,
  type MinorModeStatus,
} from '../../../utils/minor-mode';
import { BasePageService } from './base-page-service';
import { createReadyScreenModel, type ScreenModel } from './page-state';

export interface AccountSecurityLoadResult {
  screenModel: ScreenModel;
  account: AccountViewModel | null;
  minorModeStatus: MinorModeStatus | null;
  authInvalid: boolean;
}

export class AccountSecurityPageService extends BasePageService {
  async load(currentAccount: AccountViewModel | null): Promise<AccountSecurityLoadResult | null> {
    const seq = this.startRequest();
    const cachedMinorModeStatus = getCachedMinorModeStatus();
    try {
      const [account, minorModeStatus] = await Promise.all([
        accountService.loadAccountInfo(),
        fetchMinorModeStatus(),
      ]);
      if (!this.isRequestActive(seq)) {
        return null;
      }
      return {
        screenModel: createReadyScreenModel({
          contentVariant: 'data',
          refreshState: 'idle',
        }),
        account,
        minorModeStatus,
        authInvalid: false,
      };
    } catch (error: unknown) {
      const semantics = classifyError(error);
      if (!this.isRequestActive(seq)) {
        return null;
      }
      return {
        screenModel: createReadyScreenModel({
          contentVariant: 'data',
          refreshState: 'degraded',
        }),
        account: currentAccount,
        minorModeStatus: cachedMinorModeStatus,
        authInvalid: semantics.reason === 'auth-invalid',
      };
    }
  }
}

export const createAccountSecurityPageService = (): AccountSecurityPageService =>
  new AccountSecurityPageService();
