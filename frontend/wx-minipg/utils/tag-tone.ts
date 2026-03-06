const TAG_TONE_COUNT = 12;
const TAG_TONE_CLASS_PREFIX = 'tag-tone-';
export const TAG_TONE_NEUTRAL_CLASS = 'tag-tone-neutral';

const normalizeTagValue = (value: string): string => value.trim().toLowerCase();

const hashTagValue = (value: string): number => {
  let hash = 2166136261;
  for (const char of Array.from(value)) {
    hash ^= char.codePointAt(0) ?? 0;
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
};

export const getTagToneClass = (tag: string): string => {
  const normalized = normalizeTagValue(tag);
  if (normalized === '') {
    return TAG_TONE_NEUTRAL_CLASS;
  }
  const toneIndex = (hashTagValue(normalized) % TAG_TONE_COUNT) + 1;
  return `${TAG_TONE_CLASS_PREFIX}${toneIndex}`;
};

export const mapTagToneClasses = (tags: string[]): string[] =>
  tags.map((tag) => getTagToneClass(tag));
