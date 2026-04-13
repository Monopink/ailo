import { requestValidated } from '../../../utils/api';
import { getAvatarUrl } from '../../../utils/avatar';
import { isValidCategoryKey } from '../../../utils/constants/square';
import { classifyError } from '../../../utils/error-classifier';
import { firstNonEmptyString, isNonEmptyString } from '../../../utils/guards';
import { getLogger } from '../../../utils/logger';
import { StrangerProfileResponseSchema } from '../../../utils/schemas';
import { BasePageService } from './base-page-service';
import { createReadyScreenModel, type ScreenModel } from './page-state';

const logger = getLogger('StrangerInfoPageService');

const GENDER_SYMBOL_MAP: Record<number, string> = {
  1: '♂',
  2: '♀',
  3: '⚧',
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
  categoryKey: string;
  categoryText: string;
  tags: string[];
  remarkText: string;
  regionText: string;
  bioText: string;
}

export interface StrangerEntryPayload {
  qiaoId: string;
  username?: string;
  nickname?: string;
  avatarUrl?: string;
  gender?: number | null;
  categoryKey?: string | null;
  categoryTitle?: string;
  tags?: string[];
  remark?: string | null;
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

const normalizeCategoryKey = (value: string | null | undefined): string => {
  if (!isValidCategoryKey(value ?? '')) {
    return '';
  }
  return value ?? '';
};

const normalizeText = (value: string | null | undefined, fallback = ''): string =>
  firstNonEmptyString(value ?? '', fallback) ?? fallback;

const normalizeTags = (value: unknown): string[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  const seen = new Set<string>();
  const result: string[] = [];
  value.forEach((item) => {
    if (typeof item !== 'string') {
      return;
    }
    const tag = item.trim();
    if (!isNonEmptyString(tag)) {
      return;
    }
    if (seen.has(tag)) {
      return;
    }
    seen.add(tag);
    result.push(tag);
  });
  return result;
};

const buildEntryProfile = (
  qiaoId: string,
  entryPayload: StrangerEntryPayload | null
): StrangerProfileView => {
  const genderState = normalizeGender(entryPayload?.gender ?? null);
  const displayName = normalizeText(entryPayload?.nickname, qiaoId);
  const categoryKey = normalizeCategoryKey(entryPayload?.categoryKey);
  return {
    qiaoId,
    username: normalizeText(entryPayload?.username),
    avatarUrl: getAvatarUrl(entryPayload?.avatarUrl ?? ''),
    displayName,
    gender: genderState.gender,
    genderText: GENDER_SYMBOL_MAP[genderState.gender] ?? '',
    genderType: genderState.genderType,
    categoryKey,
    categoryText: normalizeText(entryPayload?.categoryTitle),
    tags: normalizeTags(entryPayload?.tags),
    remarkText: normalizeText(entryPayload?.remark ?? undefined),
    regionText: normalizeText(entryPayload?.region),
    bioText: normalizeText(entryPayload?.bio),
  };
};

const normalizeProfile = (
  profile: {
    qiao_id: string;
    username?: string | null;
    nickname?: string | null;
    avatar_url?: string | null;
    gender?: number | null;
    category_key?: string | null;
    category_title?: string | null;
    tags?: string[];
    remark?: string | null;
    bio?: string | null;
    region?: string | null;
  },
  fallback: StrangerProfileView
): StrangerProfileView => {
  const genderState = normalizeGender(profile.gender ?? null);
  const categoryKey = normalizeCategoryKey(profile.category_key);
  return {
    qiaoId: profile.qiao_id,
    username: normalizeText(profile.username, fallback.username),
    avatarUrl: getAvatarUrl(profile.avatar_url),
    displayName: normalizeText(profile.nickname, fallback.displayName),
    gender: genderState.gender,
    genderText: GENDER_SYMBOL_MAP[genderState.gender] ?? '',
    genderType: genderState.genderType,
    categoryKey,
    categoryText: normalizeText(profile.category_title, fallback.categoryText),
    tags: normalizeTags(profile.tags),
    remarkText: normalizeText(profile.remark ?? undefined),
    regionText: normalizeText(profile.region, fallback.regionText),
    bioText: normalizeText(profile.bio, fallback.bioText),
  };
};

const buildProfileUrl = (qiaoId: string, categoryKey: string): string => {
  if (!isValidCategoryKey(categoryKey)) {
    return `/discovery/profile/${qiaoId}`;
  }
  return `/discovery/profile/${qiaoId}?category_key=${encodeURIComponent(categoryKey)}`;
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
    fallbackProfile: StrangerProfileView,
    categoryKey: string
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
        url: buildProfileUrl(qiaoId, categoryKey),
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
