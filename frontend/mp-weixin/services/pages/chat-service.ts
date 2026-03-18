import { getAvatarUrl } from '../../utils/avatar';
import { firstNonEmptyString, isNonEmptyString } from '../../utils/guards';
import { getChatContactViewModel } from '../../utils/contact-service';
import { getContactByConvId } from '../../utils/storage';
import { classifyError } from '../../utils/error-classifier';
import { getLogger } from '../../utils/logger';
import { BasePageService } from './base-page-service';
import { createReadyScreenModel, type ScreenModel } from './page-state';

const logger = getLogger('ChatPageService');

export interface ChatHeaderViewModel {
  convId: string;
  contactName: string;
  navbarTitle: string;
  contactAvatar: string;
  contactQiaoId: string;
  imConvId: string;
}

export interface ChatBootstrapResult {
  screenModel: ScreenModel;
  header: ChatHeaderViewModel;
}

export interface ChatRefreshResult {
  screenModel: ScreenModel;
  headerPatch: Partial<ChatHeaderViewModel>;
  authInvalid: boolean;
}

export class ChatPageService extends BasePageService {
  private bootstrapPromise: Promise<ChatBootstrapResult | null> | null = null;
  private bootstrapConvId = '';

  async bootstrap(convId: string): Promise<ChatBootstrapResult | null> {
    if (!isNonEmptyString(convId)) {
      return {
        screenModel: createReadyScreenModel({ contentVariant: 'blank' }),
        header: {
          convId: '',
          contactName: '',
          navbarTitle: '',
          contactAvatar: '',
          contactQiaoId: '',
          imConvId: '',
        },
      };
    }

    if (this.bootstrapPromise !== null && this.bootstrapConvId === convId) {
      return await this.bootstrapPromise;
    }

    const promise = this.bootstrapInternal(convId);
    this.bootstrapPromise = promise;
    this.bootstrapConvId = convId;
    const result = await promise;
    if (this.bootstrapPromise === promise) {
      this.bootstrapPromise = null;
      this.bootstrapConvId = '';
    }
    return result;
  }

  private async bootstrapInternal(convId: string): Promise<ChatBootstrapResult | null> {
    const seq = this.startRequest();
    const storedContact = await getContactByConvId(convId);
    if (!this.isRequestActive(seq)) {
      return null;
    }

    const nicknameFromProfile =
      typeof storedContact?.profile?.nickname === 'string' ? storedContact.profile.nickname : '';
    const contactName =
      firstNonEmptyString(
        storedContact?.alias ?? '',
        nicknameFromProfile,
        storedContact?.contact_qiao_id ?? ''
      ) ?? '';
    const imConvId = typeof storedContact?.im_conv_id === 'string' ? storedContact.im_conv_id : '';
    const avatarSource =
      firstNonEmptyString(
        storedContact?.avatar_url ?? '',
        storedContact?.profile?.avatar_url ?? ''
      ) ?? '';

    return {
      screenModel: createReadyScreenModel({ contentVariant: 'data' }),
      header: {
        convId,
        contactName,
        navbarTitle: contactName,
        contactAvatar: getAvatarUrl(avatarSource),
        contactQiaoId:
          typeof storedContact?.contact_qiao_id === 'string' ? storedContact.contact_qiao_id : '',
        imConvId,
      },
    };
  }

  async refresh(convId: string): Promise<ChatRefreshResult | null> {
    if (!isNonEmptyString(convId)) {
      return {
        screenModel: createReadyScreenModel({ contentVariant: 'blank' }),
        headerPatch: {},
        authInvalid: false,
      };
    }

    const seq = this.startRequest();
    try {
      const viewModel = await getChatContactViewModel(convId);
      if (!this.isRequestActive(seq)) {
        return null;
      }

      const contactName = firstNonEmptyString(viewModel.displayName, viewModel.contactQiaoId) ?? '';
      return {
        screenModel: createReadyScreenModel({ contentVariant: 'data', refreshState: 'idle' }),
        headerPatch: {
          contactName,
          navbarTitle: contactName,
          contactAvatar: viewModel.displayAvatar,
          contactQiaoId: viewModel.contactQiaoId,
          imConvId: viewModel.imConvId,
        },
        authInvalid: false,
      };
    } catch (error: unknown) {
      const semantics = classifyError(error);
      if (!this.isRequestActive(seq)) {
        return null;
      }

      if (semantics.reason === 'auth-invalid') {
        logger.warn('Chat refresh hit auth-invalid error', { convId, reason: semantics.reason });
        return {
          screenModel: createReadyScreenModel({ contentVariant: 'data', refreshState: 'idle' }),
          headerPatch: {},
          authInvalid: true,
        };
      }

      logger.warn('Chat refresh degraded', {
        convId,
        reason: semantics.reason,
      });
      return {
        screenModel: createReadyScreenModel({
          contentVariant: 'data',
          refreshState: 'degraded',
        }),
        headerPatch: {},
        authInvalid: false,
      };
    }
  }
}

export const createChatPageService = (): ChatPageService => new ChatPageService();
