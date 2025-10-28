/**
 * Format utility
 * Provides formatting functions for display
 */

/**
 * Format phone number with masking
 * @param {string} phone - Phone number
 * @returns {string} Masked phone number (e.g., 138******00)
 */
export function formatPhone(phone) {
  if (!phone || phone.length !== 11) {
    return phone;
  }
  return `${phone.substring(0, 3)}******${phone.substring(9)}`;
}

/**
 * Format timestamp to readable time
 * @param {number} timestamp - Timestamp in milliseconds
 * @param {boolean} showDate - Whether to show date
 * @returns {string} Formatted time
 */
export function formatTime(timestamp, showDate = false) {
  const date = new Date(timestamp);
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

/**
 * Format message time for chat list
 * @param {number} timestamp - Timestamp in milliseconds
 * @returns {string} Formatted time
 */
export function formatMessageTime(timestamp) {
  const date = new Date(timestamp);
  const now = new Date();
  
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) {
    return '刚刚';
  } else if (diffMins < 60) {
    return `${diffMins}分钟前`;
  } else if (diffHours < 24) {
    return `${diffHours}小时前`;
  } else if (diffDays < 7) {
    return `${diffDays}天前`;
  } else {
    return formatTime(timestamp, false);
  }
}

/**
 * Format chat timestamp (show less frequently)
 * @param {number} currentTimestamp - Current message timestamp
 * @param {number} previousTimestamp - Previous message timestamp
 * @returns {string|null} Formatted time or null if should not show
 */
export function formatChatTimestamp(currentTimestamp, previousTimestamp) {
  // Show timestamp if:
  // 1. First message (no previous)
  // 2. More than 5 minutes apart
  if (!previousTimestamp) {
    return formatTime(currentTimestamp, true);
  }

  const diffMs = currentTimestamp - previousTimestamp;
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins >= 5) {
    return formatTime(currentTimestamp, true);
  }

  return null;
}

/**
 * Format file size
 * @param {number} bytes - File size in bytes
 * @returns {string} Formatted file size
 */
export function formatFileSize(bytes) {
  if (bytes < 1024) {
    return `${bytes} B`;
  } else if (bytes < 1048576) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  } else if (bytes < 1073741824) {
    return `${(bytes / 1048576).toFixed(1)} MB`;
  } else {
    return `${(bytes / 1073741824).toFixed(1)} GB`;
  }
}

/**
 * Format number with K/M suffix
 * @param {number} num - Number to format
 * @returns {string} Formatted number
 */
export function formatNumber(num) {
  if (num < 1000) {
    return num.toString();
  } else if (num < 1000000) {
    return `${(num / 1000).toFixed(1)}K`;
  } else {
    return `${(num / 1000000).toFixed(1)}M`;
  }
}

/**
 * Truncate text with ellipsis
 * @param {string} text - Text to truncate
 * @param {number} maxLength - Maximum length
 * @returns {string} Truncated text
 */
export function truncate(text, maxLength) {
  if (!text || text.length <= maxLength) {
    return text;
  }
  return `${text.substring(0, maxLength)}...`;
}

/**
 * Format gender
 * @param {number} gender - Gender (1=male, 2=female, 0=unknown)
 * @returns {string} Gender text
 */
export function formatGender(gender) {
  switch (gender) {
    case 1:
      return '男';
    case 2:
      return '女';
    default:
      return '未知';
  }
}

/**
 * Format age
 * @param {number} birthYear - Birth year
 * @returns {number} Age
 */
export function formatAge(birthYear) {
  if (!birthYear) {
    return 0;
  }
  const currentYear = new Date().getFullYear();
  return currentYear - birthYear;
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
  formatAge
};

