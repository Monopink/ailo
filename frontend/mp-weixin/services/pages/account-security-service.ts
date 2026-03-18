import accountService, { type AccountViewModel } from '../../utils/account-service';
import { classifyError } from '../../utils/error-classifier';
import { BasePageService } from './base-page-service';
import { createReadyScreenModel, type ScreenModel } from './page-state';

export interface AccountSecurityLoadResult {
  screenModel: ScreenModel;
  account: AccountViewModel | null;
  authInvalid: boolean;
}

export class AccountSecurityPageService extends BasePageService {
  async load(currentAccount: AccountViewModel | null): Promise<AccountSecurityLoadResult | null> {
    const seq = this.startRequest();
    try {
      const account = await accountService.loadAccountInfo();
      if (!this.isRequestActive(seq)) {
        return null;
      }
      return {
        screenModel: createReadyScreenModel({
          contentVariant: 'data',
          refreshState: 'idle',
        }),
        account,
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
        authInvalid: semantics.reason === 'auth-invalid',
      };
    }
  }
}

export const createAccountSecurityPageService = (): AccountSecurityPageService =>
  new AccountSecurityPageService();
