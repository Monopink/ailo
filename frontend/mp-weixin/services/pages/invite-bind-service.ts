import { requestValidated } from '../../utils/api';
import { getInvitationRuntimeContext, reportRuntimeObservation } from '../../utils/runtime-segment';
import { getDeviceId } from '../../utils/storage';
import {
  InvitationBindResponse,
  InvitationBindResponseSchema,
  InvitationIntakeResponse,
  InvitationIntakeResponseSchema,
  InvitationPolicyResponse,
  InvitationPolicyResponseSchema,
} from '../../utils/schemas';
import { BasePageService } from './base-page-service';

const INVITATIONS_BIND_ENDPOINT = '/invitations/bind';
const INVITATIONS_INTAKE_ENDPOINT = '/invitations/intake';
const INVITATIONS_POLICY_ENDPOINT = '/invitations/policy';

export class InviteBindService extends BasePageService {
  async intakeInviteCode(code: string): Promise<InvitationIntakeResponse | null> {
    const seq = this.startRequest();
    const deviceId = await getDeviceId();
    const runtimeContext = getInvitationRuntimeContext();
    const runtimeObservationId = await reportRuntimeObservation({
      eventName: 'invite_intake_attempt',
      pagePath: '/pages/invite-bind/invite-bind',
      entrySource: 'invite_bind_page',
      eventPayload: {
        trigger: 'manual_input',
        invite_code: code,
      },
    });
    const response = await requestValidated(InvitationIntakeResponseSchema, {
      url: INVITATIONS_INTAKE_ENDPOINT,
      method: 'POST',
      data: {
        source: 'invite_bind_page',
        trigger: 'manual_input',
        invite_code: code,
        device_id: deviceId,
        ...runtimeContext,
        runtime_observation_id: runtimeObservationId ?? runtimeContext.runtime_observation_id,
      },
    });
    if (!this.isRequestActive(seq)) {
      return null;
    }
    return response;
  }

  async bindInviteCode(code: string): Promise<InvitationBindResponse | null> {
    const seq = this.startRequest();
    const response = await requestValidated(InvitationBindResponseSchema, {
      url: INVITATIONS_BIND_ENDPOINT,
      method: 'POST',
      data: { code, source: 'invite_bind_page' },
    });
    if (!this.isRequestActive(seq)) {
      return null;
    }
    return response;
  }

  async getInvitePolicy(): Promise<InvitationPolicyResponse | null> {
    const seq = this.startRequest();
    const response = await requestValidated(InvitationPolicyResponseSchema, {
      url: INVITATIONS_POLICY_ENDPOINT,
      method: 'GET',
    });
    if (!this.isRequestActive(seq)) {
      return null;
    }
    return response;
  }
}

export const createInviteBindService = (): InviteBindService => new InviteBindService();
