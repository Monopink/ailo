import { requestValidated } from './api';
import { getLogger } from './logger';
import { fetchAccountInfo } from './profile';
import type { AccountInfo } from './schemas';
import { PhoneRefreshResponseSchema } from './schemas';

export interface AccountViewModel extends AccountInfo {
  displayPhone: string;
}

class AccountService {
  private logger = getLogger('AccountService');
  private cachedAccount: AccountViewModel | null = null;
  private loadingPromise: Promise<AccountViewModel> | null = null;

  async loadAccountInfo(forceRefresh = false): Promise<AccountViewModel> {
    if (!forceRefresh && this.cachedAccount) {
      return this.cachedAccount;
    }
    if (!forceRefresh && this.loadingPromise) {
      return this.loadingPromise;
    }

    const promise = (async () => {
      this.logger.debug('Fetching account info', { forceRefresh });
      const account = await fetchAccountInfo();
      const viewModel = this.buildViewModel(account);
      this.cachedAccount = viewModel;
      return viewModel;
    })();

    this.loadingPromise = promise;

    try {
      return await promise;
    } finally {
      if (this.loadingPromise === promise) {
        this.loadingPromise = null;
      }
    }
  }

  async refreshPhoneNumber(phoneCode: string, loginCode: string): Promise<AccountViewModel> {
    this.logger.info('Refreshing phone number via WeChat', {
      hasPhoneCode: Boolean(phoneCode),
    });
    const response = await requestValidated(PhoneRefreshResponseSchema, {
      url: '/auth/wechat/refresh-phone',
      method: 'POST',
      data: {
        login_code: loginCode,
        phone_code: phoneCode,
      },
    });

    const account = this.cachedAccount
      ? {
          ...this.cachedAccount,
          phone: response.phone,
          displayPhone: AccountService.formatPhone(response.phone),
        }
      : null;

    if (account) {
      this.cachedAccount = account;
      return account;
    }

    return this.loadAccountInfo(true);
  }

  private buildViewModel(account: AccountInfo): AccountViewModel {
    return {
      ...account,
      displayPhone: AccountService.formatPhone(account.phone),
    };
  }

  private static formatPhone(value?: string | null): string {
    if (!value) {
      return '未绑定';
    }
    if (value.length >= 7) {
      return `${value.slice(0, 3)}****${value.slice(value.length - 4)}`;
    }
    return value;
  }
}

const accountService = new AccountService();
export default accountService;
