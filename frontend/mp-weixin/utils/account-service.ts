import { requestValidated } from './api';
import { getLogger } from './logger';
import { fetchAccountInfo } from './profile';
import type { AccountInfo } from './schemas-core';
import { PhoneRefreshResponseSchema } from './schemas-validation';
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
      return '';
    }
    const normalized = value.trim();

    const chinaRawMatch = normalized.match(/^\+86\s*(\d{11})$/);
    if (chinaRawMatch !== null) {
      const phone = chinaRawMatch[1];
      return `+86 ${phone.slice(0, 3)}******${phone.slice(-2)}`;
    }

    const chinaMaskedMatch = normalized.match(/^\+86\s*(\d{3}\*{6}\d{2})$/);
    if (chinaMaskedMatch !== null) {
      return `+86 ${chinaMaskedMatch[1]}`;
    }

    if (/^\d{11}$/.test(normalized)) {
      return `${normalized.slice(0, 3)}******${normalized.slice(-2)}`;
    }

    return normalized;
  }
}

const accountService = new AccountService();
export default accountService;
