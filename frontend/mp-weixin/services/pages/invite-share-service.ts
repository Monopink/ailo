import { requestValidated } from '../../utils/api';
import {
  InvitationCodeResponse,
  InvitationCodeResponseSchema,
  InvitationPolicyResponse,
  InvitationPolicyResponseSchema,
  InvitationStatsResponse,
  InvitationStatsResponseSchema,
  InvitationEventTrackResponseSchema,
  InvitationEventType,
  InvitationShareCommandResponse,
  InvitationShareCommandResponseSchema,
  InvitationShareCardResponse,
  InvitationShareCardResponseSchema,
} from '../../utils/schemas';
import { BasePageService } from './base-page-service';

const INVITATIONS_CODE_ENDPOINT = '/invitations/code';
const INVITATIONS_SHARE_COMMAND_ENDPOINT = '/invitations/share-command';
const INVITATIONS_SHARE_CARD_ENDPOINT = '/invitations/share-card';
const INVITATIONS_POLICY_ENDPOINT = '/invitations/policy';
const INVITATIONS_STATS_ENDPOINT = '/invitations/stats';
const INVITATIONS_EVENTS_ENDPOINT = '/invitations/events';

export class InviteShareService extends BasePageService {
  async getInviteCode(): Promise<InvitationCodeResponse | null> {
    const requestKey = 'invite_share.code';
    const seq = this.startRequest(requestKey);
    const response = await requestValidated(InvitationCodeResponseSchema, {
      url: INVITATIONS_CODE_ENDPOINT,
      method: 'GET',
    });
    if (!this.isRequestActive(seq, requestKey)) {
      return null;
    }
    return response;
  }

  async getInviteShareCommand(): Promise<InvitationShareCommandResponse | null> {
    const requestKey = 'invite_share.share_command';
    const seq = this.startRequest(requestKey);
    const response = await requestValidated(InvitationShareCommandResponseSchema, {
      url: INVITATIONS_SHARE_COMMAND_ENDPOINT,
      method: 'GET',
    });
    if (!this.isRequestActive(seq, requestKey)) {
      return null;
    }
    return response;
  }

  async getInviteShareCard(): Promise<InvitationShareCardResponse | null> {
    const requestKey = 'invite_share.share_card';
    const seq = this.startRequest(requestKey);
    const response = await requestValidated(InvitationShareCardResponseSchema, {
      url: INVITATIONS_SHARE_CARD_ENDPOINT,
      method: 'GET',
    });
    if (!this.isRequestActive(seq, requestKey)) {
      return null;
    }
    return response;
  }

  async getInviteStats(): Promise<InvitationStatsResponse | null> {
    const requestKey = 'invite_share.stats';
    const seq = this.startRequest(requestKey);
    const response = await requestValidated(InvitationStatsResponseSchema, {
      url: INVITATIONS_STATS_ENDPOINT,
      method: 'GET',
    });
    if (!this.isRequestActive(seq, requestKey)) {
      return null;
    }
    return response;
  }

  async getInvitePolicy(): Promise<InvitationPolicyResponse | null> {
    const requestKey = 'invite_share.policy';
    const seq = this.startRequest(requestKey);
    const response = await requestValidated(InvitationPolicyResponseSchema, {
      url: INVITATIONS_POLICY_ENDPOINT,
      method: 'GET',
    });
    if (!this.isRequestActive(seq, requestKey)) {
      return null;
    }
    return response;
  }

  async trackInviteEvent(
    eventType: InvitationEventType,
    options?: { code?: string; payload?: Record<string, unknown> }
  ): Promise<boolean> {
    const requestKey = 'invite_share.track';
    const seq = this.startRequest(requestKey);
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
    if (!this.isRequestActive(seq, requestKey)) {
      return false;
    }
    return response.accepted;
  }
}

export const createInviteShareService = (): InviteShareService => new InviteShareService();
