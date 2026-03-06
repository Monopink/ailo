export interface TextLimitRule {
  label: string;
  displayWidthLimit: number;
  graphemeLimit: number;
}

export interface TextMetrics {
  graphemeCount: number;
  displayWidth: number;
}

export interface TextLimitValidationResult {
  valid: boolean;
  message?: string;
  metrics: TextMetrics;
}

const ZWJ_CODE_POINT = 0x200d;

export const PROFILE_NICKNAME_RULE: TextLimitRule = {
  label: '昵称',
  displayWidthLimit: 24,
  graphemeLimit: 32,
};

export const PROFILE_BIO_RULE: TextLimitRule = {
  label: '个性签名',
  displayWidthLimit: 120,
  graphemeLimit: 120,
};

export const CONTACT_ALIAS_RULE: TextLimitRule = {
  label: '备注',
  displayWidthLimit: 24,
  graphemeLimit: 32,
};

export const CONTACT_REMARK_RULE: TextLimitRule = {
  label: '描述',
  displayWidthLimit: 400,
  graphemeLimit: 400,
};

const isVariationSelector = (codePoint: number): boolean =>
  (codePoint >= 0xfe00 && codePoint <= 0xfe0f) || (codePoint >= 0xe0100 && codePoint <= 0xe01ef);

const isEmojiModifier = (codePoint: number): boolean =>
  codePoint >= 0x1f3fb && codePoint <= 0x1f3ff;

const isRegionalIndicator = (codePoint: number): boolean =>
  codePoint >= 0x1f1e6 && codePoint <= 0x1f1ff;

const isCombiningMark = (codePoint: number): boolean =>
  (codePoint >= 0x0300 && codePoint <= 0x036f) ||
  (codePoint >= 0x1ab0 && codePoint <= 0x1aff) ||
  (codePoint >= 0x1dc0 && codePoint <= 0x1dff) ||
  (codePoint >= 0x20d0 && codePoint <= 0x20ff) ||
  (codePoint >= 0xfe20 && codePoint <= 0xfe2f);

const WIDE_OR_EMOJI_POINTS = new Set([0x2329, 0x232a]);

const WIDE_OR_EMOJI_RANGES: ReadonlyArray<readonly [number, number]> = [
  [0x1100, 0x115f],
  [0x2e80, 0x303e],
  [0x3040, 0x30ff],
  [0x3100, 0x312f],
  [0x3130, 0x318f],
  [0x3190, 0x31ef],
  [0x3200, 0x32ff],
  [0x3300, 0x4dbf],
  [0x4e00, 0xa4cf],
  [0xac00, 0xd7a3],
  [0xf900, 0xfaff],
  [0xfe10, 0xfe19],
  [0xfe30, 0xfe6f],
  [0xff01, 0xff60],
  [0xffe0, 0xffe6],
  [0x2600, 0x27bf],
  [0x1f300, 0x1faff],
];

const isInRanges = (codePoint: number, ranges: ReadonlyArray<readonly [number, number]>): boolean =>
  ranges.some(([start, end]) => codePoint >= start && codePoint <= end);

const isWideOrEmoji = (codePoint: number): boolean =>
  WIDE_OR_EMOJI_POINTS.has(codePoint) || isInRanges(codePoint, WIDE_OR_EMOJI_RANGES);

export const getTextMetrics = (text: string): TextMetrics => {
  let graphemeCount = 0;
  let displayWidth = 0;
  let joinNext = false;
  let regionalPairOpen = false;

  for (const char of text) {
    const codePoint = char.codePointAt(0);
    if (typeof codePoint !== 'number') {
      continue;
    }

    if (codePoint === ZWJ_CODE_POINT) {
      joinNext = true;
      regionalPairOpen = false;
      continue;
    }

    if (
      isCombiningMark(codePoint) ||
      isVariationSelector(codePoint) ||
      isEmojiModifier(codePoint)
    ) {
      continue;
    }

    if (joinNext) {
      joinNext = false;
      regionalPairOpen = false;
      continue;
    }

    if (isRegionalIndicator(codePoint)) {
      if (regionalPairOpen) {
        regionalPairOpen = false;
        continue;
      }
      regionalPairOpen = true;
      graphemeCount += 1;
      displayWidth += 2;
      continue;
    }

    regionalPairOpen = false;
    graphemeCount += 1;
    displayWidth += isWideOrEmoji(codePoint) ? 2 : 1;
  }

  return {
    graphemeCount,
    displayWidth,
  };
};

export const validateTextLimit = (
  value: string,
  rule: TextLimitRule
): TextLimitValidationResult => {
  const metrics = getTextMetrics(value);
  if (metrics.displayWidth > rule.displayWidthLimit) {
    const maxCn = Math.floor(rule.displayWidthLimit / 2);
    return {
      valid: false,
      message: `${rule.label}长度过长，最多${maxCn}个中文或${rule.displayWidthLimit}个英文`,
      metrics,
    };
  }

  if (metrics.graphemeCount > rule.graphemeLimit) {
    return {
      valid: false,
      message: `${rule.label}最多${rule.graphemeLimit}个字符`,
      metrics,
    };
  }

  return {
    valid: true,
    metrics,
  };
};
