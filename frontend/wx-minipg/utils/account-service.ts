import { requestValidated } from './api';
import { getLogger } from './logger';
import { fetchAccountInfo } from './profile';
import type { AccountInfo } from './schemas';
import { PhoneRefreshResponseSchema } from './schemas';
import { isNonEmptyString } from './guards';

export interface AccountViewModel extends AccountInfo {
  displayPhone: string;
}

class AccountService {
  private logger = getLogger('AccountService');

  async loadAccountInfo(): Promise<AccountViewModel> {
    this.logger.debug('Fetching account info');
    const account = await fetchAccountInfo();
    return this.buildViewModel(account);
  }

  async refreshPhoneNumber(phoneCode: string, loginCode: string): Promise<AccountViewModel> {
    this.logger.info('Refreshing phone number via WeChat', {
      hasPhoneCode: isNonEmptyString(phoneCode),
    });
    const response = await requestValidated(PhoneRefreshResponseSchema, {
      url: '/auth/wechat/refresh-phone',
      method: 'POST',
      data: {
        login_code: loginCode,
        phone_code: phoneCode,
      },
    });

    return {
      phone: response.phone,
      displayPhone: AccountService.formatPhone(response.phone),
    };
  }

  private buildViewModel(account: AccountInfo): AccountViewModel {
    return {
      ...account,
      displayPhone: AccountService.formatPhone(account.phone),
    };
  }

  private static formatPhone(value?: string | null): string {
    if (!isNonEmptyString(value)) {
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
