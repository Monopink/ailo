import { createReadyScreenModel, type ScreenModel } from './page-state';
import { BasePageService } from './base-page-service';

export interface ContactRequestItem {
  id: string;
  nickname: string;
  avatar: string;
  message: string;
  gender?: number | null;
}

export interface ContactRequestsLoadResult {
  screenModel: ScreenModel;
  requests: ContactRequestItem[];
}

export class ContactRequestsPageService extends BasePageService {
  load(requests: ContactRequestItem[]): ContactRequestsLoadResult | null {
    const seq = this.startRequest();
    if (!this.isRequestActive(seq)) {
      return null;
    }
    return {
      screenModel: createReadyScreenModel({
        contentVariant: requests.length === 0 ? 'empty' : 'data',
        refreshState: 'idle',
      }),
      requests,
    };
  }
}

export const createContactRequestsPageService = (): ContactRequestsPageService =>
  new ContactRequestsPageService();
