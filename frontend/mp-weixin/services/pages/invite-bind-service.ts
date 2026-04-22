import { requestValidated } from '../../utils/api';
import {
  InvitationBindResponse,
  InvitationBindResponseSchema,
  InvitationIntakeResponse,
  InvitationIntakeResponseSchema,
} from '../../utils/schemas';
import { BasePageService } from './base-page-service';

const INVITATIONS_BIND_ENDPOINT = '/invitations/bind';
const INVITATIONS_INTAKE_ENDPOINT = '/invitations/intake';

export class InviteBindService extends BasePageService {
  async intakeInviteCode(code: string): Promise<InvitationIntakeResponse | null> {
    const seq = this.startRequest();
    const response = await requestValidated(InvitationIntakeResponseSchema, {
      url: INVITATIONS_INTAKE_ENDPOINT,
      method: 'POST',
      data: {
        source: 'invite_bind_page',
        trigger: 'manual_input',
        invite_code: code,
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
}

export const createInviteBindService = (): InviteBindService => new InviteBindService();
