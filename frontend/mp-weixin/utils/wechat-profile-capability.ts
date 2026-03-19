type WechatProfileCapabilities = {
  canUseChooseAvatar: boolean;
  canUseNicknameInput: boolean;
  canUseNicknameReview: boolean;
};

const MIN_AVATAR_NICKNAME_VERSION = '2.21.2';
const MIN_NICKNAME_REVIEW_VERSION = '2.29.1';

const compareVersion = (left: string, right: string): number => {
  const leftParts = left.split('.');
  const rightParts = right.split('.');
  const length = Math.max(leftParts.length, rightParts.length);

  while (leftParts.length < length) {
    leftParts.push('0');
  }
  while (rightParts.length < length) {
    rightParts.push('0');
  }

  for (let index = 0; index < length; index += 1) {
    const leftNumber = Number.parseInt(leftParts[index] ?? '0', 10);
    const rightNumber = Number.parseInt(rightParts[index] ?? '0', 10);
    if (leftNumber > rightNumber) {
      return 1;
    }
    if (leftNumber < rightNumber) {
      return -1;
    }
  }

  return 0;
};

const getSdkVersion = (): string => {
  try {
    return wx.getAppBaseInfo().SDKVersion;
  } catch {
    return '0.0.0';
  }
};

export const getWechatProfileCapabilities = (): WechatProfileCapabilities => {
  const sdkVersion = getSdkVersion();
  return {
    canUseChooseAvatar: compareVersion(sdkVersion, MIN_AVATAR_NICKNAME_VERSION) >= 0,
    canUseNicknameInput: compareVersion(sdkVersion, MIN_AVATAR_NICKNAME_VERSION) >= 0,
    canUseNicknameReview: compareVersion(sdkVersion, MIN_NICKNAME_REVIEW_VERSION) >= 0,
  };
};
