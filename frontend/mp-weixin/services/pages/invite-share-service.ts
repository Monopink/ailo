import { requestValidated } from '../../utils/api';
import {
  InvitationStatsResponse,
  InvitationStatsResponseSchema,
  InvitationEventTrackResponseSchema,
  InvitationEventType,
  InvitationShareFullResponse,
  InvitationShareFullResponseSchema,
} from '../../utils/schemas';
import { BasePageService } from './base-page-service';

const INVITATIONS_SHARE_ENDPOINT = '/invitations/share';
const INVITATIONS_STATS_ENDPOINT = '/invitations/stats';
const INVITATIONS_EVENTS_ENDPOINT = '/invitations/events';

export class InviteShareService extends BasePageService {
  async getInviteShareText(): Promise<InvitationShareFullResponse | null> {
    const seq = this.startRequest();
    const response = await requestValidated(InvitationShareFullResponseSchema, {
      url: INVITATIONS_SHARE_ENDPOINT,
      method: 'GET',
    });
    if (!this.isRequestActive(seq)) {
      return null;
    }
    return response;
  }

  async getInviteStats(): Promise<InvitationStatsResponse | null> {
    const seq = this.startRequest();
    const response = await requestValidated(InvitationStatsResponseSchema, {
      url: INVITATIONS_STATS_ENDPOINT,
      method: 'GET',
    });
    if (!this.isRequestActive(seq)) {
      return null;
    }
    return response;
  }

  async trackInviteEvent(
    eventType: InvitationEventType,
    options?: { code?: string; payload?: Record<string, unknown> }
  ): Promise<boolean> {
    const seq = this.startRequest();
    const response = await requestValidated(InvitationEventTrackResponseSchema, {
      url: INVITATIONS_EVENTS_ENDPOINT,
      method: 'POST',
      data: {
        event_type: eventType,
        source: 'invite_share_page',
        code: options?.code,
        payload: options?.payload,
      },
    });
    if (!this.isRequestActive(seq)) {
      return false;
    }
    return response.accepted;
  }
}

export const createInviteShareService = (): InviteShareService => new InviteShareService();
