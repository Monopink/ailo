import { requestValidated } from '../../utils/api';
import { getAvatarUrl } from '../../utils/avatar';
import { classifyError } from '../../utils/error-classifier';
import { firstNonEmptyString, isNonEmptyString } from '../../utils/guards';
import { getLogger } from '../../utils/logger';
import { StrangerProfileResponseSchema } from '../../utils/schemas';
import { BasePageService } from './base-page-service';
import { createReadyScreenModel, type ScreenModel } from './page-state';

const logger = getLogger('StrangerInfoPageService');

const GENDER_SYMBOL_MAP: Record<number, string> = {
  1: '♂',
  2: '♀',
  3: '⚧',
};

const CATEGORY_TEXT_MAP: Record<string, string> = {
  '1': '交友',
  '2': '恋爱',
  '3': '倾诉',
  '4': '闺蜜',
  '5': '同好',
};

type GenderType = 'success' | 'danger' | 'default';

export interface StrangerProfileView {
  qiaoId: string;
  username: string;
  avatarUrl: string;
  displayName: string;
  gender: number;
  genderText: string;
  genderType: GenderType;
  categoryText: string;
  regionText: string;
  bioText: string;
}

export interface StrangerEntryPayload {
  qiaoId: string;
  username?: string;
  nickname?: string;
  avatarUrl?: string;
  gender?: number | null;
  category?: string | number | null;
  bio?: string;
  region?: string;
}

export interface StrangerInfoBootstrapResult {
  screenModel: ScreenModel;
  profile: StrangerProfileView;
}

export interface StrangerInfoRefreshResult {
  screenModel: ScreenModel;
  profile: StrangerProfileView | null;
  authInvalid: boolean;
}

const toCategoryKey = (value: StrangerEntryPayload['category']): string => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value);
  }
  if (typeof value === 'string') {
    return value;
  }
  return '';
};

const normalizeGender = (
  value: number | null | undefined
): { gender: number; genderType: GenderType } => {
  if (value === 1) {
    return { gender: 1, genderType: 'success' };
  }
  if (value === 2) {
    return { gender: 2, genderType: 'danger' };
  }
  if (value === 3) {
    return { gender: 3, genderType: 'default' };
  }
  return { gender: 0, genderType: 'default' };
};

const toCategoryText = (category: string): string => CATEGORY_TEXT_MAP[category] ?? '';

const buildEntryProfile = (
  qiaoId: string,
  entryPayload: StrangerEntryPayload | null
): StrangerProfileView => {
  const genderState = normalizeGender(entryPayload?.gender ?? null);
  const displayName = firstNonEmptyString(entryPayload?.nickname ?? '', qiaoId) ?? qiaoId;
  return {
    qiaoId,
    username: firstNonEmptyString(entryPayload?.username ?? '', '') ?? '',
    avatarUrl: getAvatarUrl(entryPayload?.avatarUrl ?? ''),
    displayName,
    gender: genderState.gender,
    genderText: GENDER_SYMBOL_MAP[genderState.gender] ?? '',
    genderType: genderState.genderType,
    categoryText: toCategoryText(toCategoryKey(entryPayload?.category ?? null)),
    regionText: firstNonEmptyString(entryPayload?.region ?? '', '') ?? '',
    bioText: firstNonEmptyString(entryPayload?.bio ?? '', '') ?? '',
  };
};

const normalizeProfile = (
  profile: {
    qiao_id: string;
    username?: string | null;
    nickname?: string | null;
    avatar_url?: string | null;
    gender?: number | null;
    category?: string | number | null;
    bio?: string | null;
    region?: string | null;
  },
  fallback: StrangerProfileView
): StrangerProfileView => {
  const genderState = normalizeGender(profile.gender ?? null);
  return {
    qiaoId: profile.qiao_id,
    username: firstNonEmptyString(profile.username ?? '', fallback.username) ?? fallback.username,
    avatarUrl: getAvatarUrl(profile.avatar_url),
    displayName:
      firstNonEmptyString(profile.nickname ?? '', fallback.displayName) ?? fallback.displayName,
    gender: genderState.gender,
    genderText: GENDER_SYMBOL_MAP[genderState.gender] ?? '',
    genderType: genderState.genderType,
    categoryText: toCategoryText(toCategoryKey(profile.category ?? null)),
    regionText:
      firstNonEmptyString(profile.region ?? '', fallback.regionText) ?? fallback.regionText,
    bioText: firstNonEmptyString(profile.bio ?? '', fallback.bioText) ?? fallback.bioText,
  };
};

export class StrangerInfoPageService extends BasePageService {
  private bootstrapPromise: Promise<StrangerInfoBootstrapResult | null> | null = null;
  private bootstrapQiaoId = '';

  async bootstrap(
    qiaoId: string,
    entryPayload: StrangerEntryPayload | null
  ): Promise<StrangerInfoBootstrapResult | null> {
    if (!isNonEmptyString(qiaoId)) {
      return {
        screenModel: createReadyScreenModel({ contentVariant: 'blank' }),
        profile: buildEntryProfile('', null),
      };
    }

    if (this.bootstrapPromise !== null && this.bootstrapQiaoId === qiaoId) {
      return await this.bootstrapPromise;
    }

    const promise = this.bootstrapInternal(qiaoId, entryPayload);
    this.bootstrapPromise = promise;
    this.bootstrapQiaoId = qiaoId;
    const result = await promise;
    if (this.bootstrapPromise === promise) {
      this.bootstrapPromise = null;
      this.bootstrapQiaoId = '';
    }
    return result;
  }

  private bootstrapInternal(
    qiaoId: string,
    entryPayload: StrangerEntryPayload | null
  ): Promise<StrangerInfoBootstrapResult | null> {
    const seq = this.startRequest();
    const profile = buildEntryProfile(qiaoId, entryPayload);
    if (!this.isRequestActive(seq)) {
      return Promise.resolve(null);
    }

    return Promise.resolve({
      screenModel: createReadyScreenModel({ contentVariant: 'data' }),
      profile,
    });
  }

  async refresh(
    qiaoId: string,
    fallbackProfile: StrangerProfileView
  ): Promise<StrangerInfoRefreshResult | null> {
    if (!isNonEmptyString(qiaoId)) {
      return {
        screenModel: createReadyScreenModel({ contentVariant: 'blank' }),
        profile: null,
        authInvalid: false,
      };
    }

    const seq = this.startRequest();
    try {
      const profile = await requestValidated(StrangerProfileResponseSchema, {
        url: `/discovery/profile/${qiaoId}`,
        method: 'GET',
        auth: false,
      });

      if (!this.isRequestActive(seq)) {
        return null;
      }

      return {
        screenModel: createReadyScreenModel({ contentVariant: 'data', refreshState: 'idle' }),
        profile: normalizeProfile(profile, fallbackProfile),
        authInvalid: false,
      };
    } catch (error: unknown) {
      const semantics = classifyError(error);
      if (!this.isRequestActive(seq)) {
        return null;
      }

      if (semantics.reason === 'auth-invalid') {
        logger.warn('Stranger profile refresh hit auth-invalid error', {
          qiaoId,
          reason: semantics.reason,
        });
        return {
          screenModel: createReadyScreenModel({ contentVariant: 'data', refreshState: 'idle' }),
          profile: null,
          authInvalid: true,
        };
      }

      logger.warn('Stranger profile refresh degraded', {
        qiaoId,
        reason: semantics.reason,
      });
      return {
        screenModel: createReadyScreenModel({
          contentVariant: 'data',
          refreshState: 'degraded',
        }),
        profile: null,
        authInvalid: false,
      };
    }
  }
}

export const createStrangerInfoPageService = (): StrangerInfoPageService =>
  new StrangerInfoPageService();
