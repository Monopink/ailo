/**
 * Format utility
 * Provides formatting functions for display
 */

export function formatPhone(phone: string | null | undefined): string {
  if (!phone || phone.length !== 11) {
    return phone || '';
  }
  return `${phone.substring(0, 3)}******${phone.substring(9)}`;
}

export function formatTime(
  timestamp: number | string | null | undefined,
  showDate = false
): string {
  if (!timestamp && timestamp !== 0) {
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
  if (!timestamp && timestamp !== 0) {
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
  if (!currentTimestamp && currentTimestamp !== 0) {
    return '';
  }
  if (!previousTimestamp && previousTimestamp !== 0) {
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
  if (!text || text.length <= maxLength) {
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
  if (!birthYear) {
    return 0;
  }
  const currentYear = new Date().getFullYear();
  return currentYear - birthYear;
}

// Region formatting
// Remove suffixes (省/市/自治区/特别行政区) and merge duplicates for municipalities
export function formatRegion(
  province: string | null | undefined,
  city: string | null | undefined
): string {
  if (!province || !city) {
    return '';
  }

  // Remove common suffixes and ethnic names for autonomous regions (province level)
  const cleanProvince = province
    .replace(/维吾尔自治区$/, '')
    .replace(/壮族自治区$/, '')
    .replace(/回族自治区$/, '')
    .replace(/藏族自治区$/, '')
    .replace(/蒙古自治区$/, '')
    .replace(/自治区$/, '')
    .replace(/省$/, '')
    .replace(/特别行政区$/, '')
    .replace(/市$/, '');

  // Remove suffixes and ethnic names for autonomous prefectures (city level)
  const cleanCity = city
    .replace(/土家族苗族自治州$/, '')
    .replace(/藏族羌族自治州$/, '')
    .replace(/彝族自治州$/, '')
    .replace(/白族自治州$/, '')
    .replace(/哈尼族彝族自治州$/, '')
    .replace(/傣族景颇族自治州$/, '')
    .replace(/傣族自治州$/, '')
    .replace(/蒙古族藏族自治州$/, '')
    .replace(/藏族自治州$/, '')
    .replace(/回族自治州$/, '')
    .replace(/蒙古自治州$/, '')
    .replace(/朝鲜族自治州$/, '')
    .replace(/哈萨克自治州$/, '')
    .replace(/柯尔克孜自治州$/, '')
    .replace(/自治州$/, '')
    .replace(/盟$/, '')
    .replace(/市$/, '');

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
