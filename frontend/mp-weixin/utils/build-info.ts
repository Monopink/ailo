import { BUILD_INFO as RAW_BUILD_INFO } from './build-info.generated';
import { isNonEmptyString } from './guards';

export interface BuildInfo {
  id: string;
  builtAt: string;
  appVersion: string;
}

export interface BuildInfoViewModel {
  show: boolean;
  text: string;
}

const normalizeBuildInfo = (input: unknown): BuildInfo => {
  if (input === null || typeof input !== 'object') {
    return { id: '', builtAt: '', appVersion: '' };
  }
  const record = input as Record<string, unknown>;
  const id = typeof record.id === 'string' ? record.id.trim() : '';
  const builtAt = typeof record.builtAt === 'string' ? record.builtAt.trim() : '';
  const appVersion = typeof record.appVersion === 'string' ? record.appVersion.trim() : '';
  return { id, builtAt, appVersion };
};

export const BUILD_INFO: BuildInfo = normalizeBuildInfo(RAW_BUILD_INFO);

export const formatBuildInfoText = (buildInfo: BuildInfo): string => {
  const segments: string[] = [];
  if (isNonEmptyString(buildInfo.appVersion)) {
    segments.push(`v${buildInfo.appVersion}`);
  }
  if (isNonEmptyString(buildInfo.builtAt)) {
    const date = new Date(buildInfo.builtAt);
    if (!Number.isNaN(date.getTime())) {
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      segments.push(`${year}-${month}-${day} ${hours}:${minutes}`);
    } else {
      segments.push(buildInfo.builtAt);
    }
  }
  if (isNonEmptyString(buildInfo.id)) {
    segments.push(buildInfo.id);
  }
  return segments.join(' · ');
};

export const buildBuildInfoViewModel = (
  buildInfo: BuildInfo,
  options: { isProd: boolean }
): BuildInfoViewModel => {
  const text = formatBuildInfoText(buildInfo);
  return {
    show: !options.isProd && text !== '',
    text,
  };
};
