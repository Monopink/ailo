/**
 * Format utility
 * Provides formatting functions for display
 */
import { isDefined, isNonEmptyString } from './guards';

export function formatPhone(phone: string | null | undefined): string {
  if (!isNonEmptyString(phone) || phone.length !== 11) {
    return phone ?? '';
  }
  return `${phone.substring(0, 3)}******${phone.substring(9)}`;
}

export function formatTime(
  timestamp: number | string | null | undefined,
  showDate = false
): string {
  if (!isDefined(timestamp) || timestamp === '') {
    return '';
  }
  const date = new Date(Number(timestamp));
  if (Number.isNaN(date.getTime())) {
    return '';
  }

  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();
  const isYesterday = new Date(now.getTime() - 86400000).toDateString() === date.toDateString();
  const isThisYear = date.getFullYear() === now.getFullYear();

  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  const timeStr = `${hours}:${minutes}`;

  if (isToday) {
    return timeStr;
  } else if (isYesterday) {
    return `昨天 ${timeStr}`;
  } else if (isThisYear) {
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const day = date.getDate().toString().padStart(2, '0');
    return showDate ? `${month}-${day} ${timeStr}` : `${month}-${day}`;
  } else {
    const year = date.getFullYear();
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const day = date.getDate().toString().padStart(2, '0');
    return showDate ? `${year}-${month}-${day} ${timeStr}` : `${year}-${month}-${day}`;
  }
}

export function formatMessageTime(timestamp: number | string | null | undefined): string {
  if (!isDefined(timestamp) || timestamp === '') {
    return '';
  }
  const date = new Date(Number(timestamp));
  if (Number.isNaN(date.getTime())) {
    return '';
  }

  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) {
    return '刚刚';
  }
  if (diffMins < 60) {
    return `${diffMins}分钟前`;
  }
  if (diffHours < 24) {
    return `${diffHours}小时前`;
  }
  if (diffDays < 7) {
    return `${diffDays}天前`;
  }
  return formatTime(timestamp, false);
}

export function formatChatTimestamp(
  currentTimestamp: number | string,
  previousTimestamp: number | string | null | undefined
): string | null {
  if (currentTimestamp === '') {
    return '';
  }
  if (previousTimestamp === undefined || previousTimestamp === null || previousTimestamp === '') {
    return formatTime(currentTimestamp, true);
  }
  const diff = Number(currentTimestamp) - Number(previousTimestamp);
  if (diff >= 5 * 60 * 1000) {
    return formatTime(currentTimestamp, true);
  }
  return null;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1048576) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  if (bytes < 1073741824) {
    return `${(bytes / 1048576).toFixed(1)} MB`;
  }
  return `${(bytes / 1073741824).toFixed(1)} GB`;
}

export function formatNumber(num: number): string {
  if (num < 1000) {
    return num.toString();
  }
  if (num < 1000000) {
    return `${(num / 1000).toFixed(1)}K`;
  }
  return `${(num / 1000000).toFixed(1)}M`;
}

export function truncate(text: string, maxLength: number): string {
  if (!isNonEmptyString(text)) {
    return text;
  }
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.substring(0, maxLength)}...`;
}

export function formatGender(gender: number | string | null | undefined): string {
  switch (gender) {
    case 1:
      return '男';
    case 2:
      return '女';
    default:
      return '未知';
  }
}

export function formatAge(birthYear: number | null | undefined): number {
  if (birthYear === undefined || birthYear === null) {
    return 0;
  }
  const currentYear = new Date().getFullYear();
  return currentYear - birthYear;
}

// Region formatting
const AUTONOMOUS_DESCRIPTOR_SUFFIXES = [
  '哈萨克',
  '柯尔克孜',
  '蒙古',
  '维吾尔',
  '壮',
  '回',
  '藏',
  '彝',
  '白',
  '傣',
  '苗',
  '羌',
  '土家',
  '哈尼',
  '景颇',
  '朝鲜',
] as const;

const stripTrailingAutonomyDescriptor = (raw: string): string => {
  let name = raw.trim();
  let changed = true;

  while (changed && name !== '') {
    changed = false;

    for (const suffix of AUTONOMOUS_DESCRIPTOR_SUFFIXES) {
      const withZu = `${suffix}族`;
      if (name.endsWith(withZu)) {
        name = name.slice(0, -withZu.length).trim();
        changed = true;
        break;
      }
    }
    if (changed) {
      continue;
    }

    for (const suffix of AUTONOMOUS_DESCRIPTOR_SUFFIXES) {
      if (name.endsWith(suffix)) {
        name = name.slice(0, -suffix.length).trim();
        changed = true;
        break;
      }
    }
  }

  return name;
};

const cleanCnProvinceName = (raw: string): string => {
  return raw
    .trim()
    .replace(/特别行政区$/u, '')
    .replace(/省$/u, '')
    .replace(/市$/u, '')
    .replace(/(壮族自治区|回族自治区|维吾尔自治区)$/u, '')
    .replace(/自治区$/u, '')
    .trim();
};

const cleanCnCityName = (raw: string): string => {
  let name = raw
    .trim()
    .replace(/自治州$/u, '')
    .replace(/自治县$/u, '')
    .replace(/自治旗$/u, '')
    .replace(/自治市$/u, '')
    .replace(/市$/u, '')
    .replace(/地区$/u, '')
    .replace(/盟$/u, '')
    .trim();

  name = stripTrailingAutonomyDescriptor(name).trim();
  return name;
};

const formatCnRegionCity = (province: string, city: string): string => {
  const cleanProvince = cleanCnProvinceName(province);
  const cleanCity = cleanCnCityName(city);

  if (!isNonEmptyString(cleanProvince) || !isNonEmptyString(cleanCity)) {
    return '';
  }

  if (cleanProvince === cleanCity) {
    return cleanProvince;
  }

  return `${cleanProvince} ${cleanCity}`;
};

export function formatRegion(
  province: string | null | undefined,
  city: string | null | undefined
): string {
  if (!isNonEmptyString(province) || !isNonEmptyString(city)) {
    return '';
  }

  const normalized = formatCnRegionCity(province, city);
  if (normalized !== '') {
    return normalized;
  }

  const cleanProvince = province
    .trim()
    .replace(/特别行政区$/, '')
    .replace(/省$/, '')
    .replace(/市$/, '')
    .replace(/(壮族自治区|回族自治区|维吾尔自治区)$/, '')
    .replace(/自治区$/, '');

  const cleanCity = city
    .trim()
    .replace(/自治州$/, '')
    .replace(/地区$/, '')
    .replace(/盟$/, '')
    .replace(/市$/, '');

  if (!isNonEmptyString(cleanProvince) || !isNonEmptyString(cleanCity)) {
    return '';
  }

  // Merge if province and city are the same (municipalities)
  if (cleanProvince === cleanCity) {
    return cleanProvince;
  }

  return `${cleanProvince} ${cleanCity}`;
}

export default {
  formatPhone,
  formatTime,
  formatMessageTime,
  formatChatTimestamp,
  formatFileSize,
  formatNumber,
  truncate,
  formatGender,
  formatAge,
  formatRegion,
};
