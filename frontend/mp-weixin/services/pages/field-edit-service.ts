import {
  refreshStoredContact,
  type ContactUpdatePayload,
  updateContactDetail,
} from '../../utils/contact-service';
import profileService from '../../utils/profile-service';
import { BasePageService } from './base-page-service';

export class FieldEditPageService extends BasePageService {
  async checkUsernameAvailability(username: string): Promise<boolean> {
    const seq = this.startRequest();
    await profileService.checkUsernameAvailability(username);
    return this.isRequestActive(seq);
  }

  async updateProfile(updateData: Record<string, unknown>): Promise<boolean> {
    const seq = this.startRequest();
    await profileService.updateProfile(updateData);
    return this.isRequestActive(seq);
  }

  async updateContactField(convId: string, payload: ContactUpdatePayload): Promise<boolean> {
    const seq = this.startRequest();
    const detail = await updateContactDetail(convId, payload);
    await refreshStoredContact(convId, detail);
    return this.isRequestActive(seq);
  }
}

export const createFieldEditPageService = (): FieldEditPageService => new FieldEditPageService();
