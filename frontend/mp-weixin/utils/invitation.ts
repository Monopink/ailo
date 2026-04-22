import { requestValidated } from './api';
import type { InvitationBindingStatusResponse } from './schemas-core';
import { InvitationBindingStatusResponseSchema } from './schemas-validation';

const INVITATIONS_BINDING_STATUS_ENDPOINT = '/invitations/binding-status';

export async function fetchInvitationBindingStatus(): Promise<InvitationBindingStatusResponse> {
  return await requestValidated(InvitationBindingStatusResponseSchema, {
    url: INVITATIONS_BINDING_STATUS_ENDPOINT,
    method: 'GET',
  });
}
