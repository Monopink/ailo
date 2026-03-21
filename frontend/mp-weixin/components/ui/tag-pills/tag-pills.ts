import { isNonEmptyString } from '../../../utils/guards';
import { getLogger } from '../../../utils/logger';
import { mapTagToneClasses } from '../../../utils/tag-tone';

const logger = getLogger('TagPills');

const TAG_GAP_RPX = 6;
const FALLBACK_VISIBLE_COUNT = 1;

interface TagMeasureItem {
  key: string;
  text: string;
  kind: 'tag' | 'overflow';
  hiddenCount?: number;
}

const getWindowWidthPx = (): number => {
  if (typeof wx.getWindowInfo === 'function') {
    return wx.getWindowInfo().windowWidth;
  }
  return wx.getSystemInfoSync().windowWidth;
};

const getRectWidth = (rect: unknown): number | undefined => {
  if (rect === null || typeof rect !== 'object') {
    return undefined;
  }
  const candidate = rect as { width?: unknown };
  return typeof candidate.width === 'number' ? candidate.width : undefined;
};

const getValidTags = (tags: unknown): string[] => {
  if (!Array.isArray(tags)) {
    return [];
  }
  return tags
    .filter((tag): tag is string => typeof tag === 'string' && tag.trim().length > 0)
    .map((tag) => tag.trim());
};

const buildMeasureItems = (tags: string[]): TagMeasureItem[] => {
  const tagItems = tags.map<TagMeasureItem>((tag) => ({
    key: `tag:${tag}`,
    text: tag,
    kind: 'tag',
  }));
  const overflowItems: TagMeasureItem[] = [];
  for (let hiddenCount = 1; hiddenCount <= tags.length; hiddenCount += 1) {
    overflowItems.push({
      key: `overflow:${hiddenCount}`,
      text: `+${hiddenCount}`,
      kind: 'overflow',
      hiddenCount,
    });
  }
  return [...tagItems, ...overflowItems];
};

const computeFallbackLayout = (tags: string[]): { visibleTags: string[]; hiddenTagCount: number } => {
  const visibleTags = tags.slice(0, FALLBACK_VISIBLE_COUNT);
  return {
    visibleTags,
    hiddenTagCount: Math.max(0, tags.length - visibleTags.length),
  };
};

Component<
  {
    hasTags: boolean;
    visibleTags: string[];
    visibleTagToneClasses: string[];
    hiddenTagCount: number;
    measureItems: TagMeasureItem[];
  },
  Record<string, never>,
  {
    refreshLayout(): void;
    measureAndCompute(tags: string[], measureItems: TagMeasureItem[]): void;
  }
>({
  properties: {
    tags: {
      type: Array,
      value: [],
    },
    align: {
      type: String,
      value: 'start',
    },
  },

  data: {
    hasTags: false,
    visibleTags: [],
    visibleTagToneClasses: [],
    hiddenTagCount: 0,
    measureItems: [],
  },

  lifetimes: {
    attached() {
      this.refreshLayout();
    },
  },

  observers: {
    tags() {
      this.refreshLayout();
    },
  },

  methods: {
    refreshLayout() {
      const tags = getValidTags(this.properties.tags);
      if (tags.length === 0) {
        this.setData({
          hasTags: false,
          visibleTags: [],
          visibleTagToneClasses: [],
          hiddenTagCount: 0,
          measureItems: [],
        });
        return;
      }

      const measureItems = buildMeasureItems(tags);
      this.setData(
        {
          hasTags: true,
          measureItems,
        },
        () => {
          wx.nextTick(() => {
            this.measureAndCompute(tags, measureItems);
          });
        }
      );
    },

    measureAndCompute(tags, measureItems) {
      if (tags.length === 0) {
        return;
      }

      wx.createSelectorQuery()
        .in(this)
        .selectAll('.tag-pills__measure-item')
        .boundingClientRect()
        .select('.tag-pills__row')
        .boundingClientRect()
        .exec((queryResult) => {
          const queryResultValue: unknown = queryResult;
          if (!Array.isArray(queryResultValue) || queryResultValue.length < 2) {
            return;
          }
          const measureRectValues: unknown = queryResultValue[0];
          const rowRectValue: unknown = queryResultValue[1];
          if (!Array.isArray(measureRectValues) || rowRectValue === null || typeof rowRectValue !== 'object') {
            return;
          }
          if (measureRectValues.length === 0) {
            return;
          }

          const rowWidthPx = getRectWidth(rowRectValue) ?? 0;
          const tagWidths: Array<number | undefined> = [];
          const overflowWidths = new Map<number, number>();

          measureItems.forEach((item, index) => {
            const width = getRectWidth(measureRectValues[index]);
            if (typeof width !== 'number') {
              return;
            }
            if (item.kind === 'tag') {
              tagWidths.push(width);
              return;
            }
            if (typeof item.hiddenCount === 'number') {
              overflowWidths.set(item.hiddenCount, width);
            }
          });

          if (tagWidths.length < Math.min(tags.length, 1)) {
            const fallback = computeFallbackLayout(tags);
            const toneClasses = mapTagToneClasses(tags).slice(0, fallback.visibleTags.length);
            this.setData({
              visibleTags: fallback.visibleTags,
              visibleTagToneClasses: toneClasses,
              hiddenTagCount: fallback.hiddenTagCount,
            });
            return;
          }

          const gapPx = (getWindowWidthPx() / 750) * TAG_GAP_RPX;
          const resolveOverflowWidth = (hiddenCount: number): number | undefined =>
            overflowWidths.get(hiddenCount);

          let bestVisibleCount = 0;
          for (let visibleCount = tags.length; visibleCount >= 0; visibleCount -= 1) {
            const hiddenCount = tags.length - visibleCount;
            let usedWidthPx = 0;
            let ok = true;

            for (let index = 0; index < visibleCount; index += 1) {
              const width = tagWidths[index];
              if (typeof width !== 'number') {
                ok = false;
                break;
              }
              usedWidthPx += width + (index > 0 ? gapPx : 0);
              if (usedWidthPx > rowWidthPx) {
                ok = false;
                break;
              }
            }

            if (!ok) {
              continue;
            }

            if (hiddenCount > 0) {
              const overflowWidth = resolveOverflowWidth(hiddenCount);
              if (typeof overflowWidth !== 'number') {
                continue;
              }
              usedWidthPx += overflowWidth + (visibleCount > 0 ? gapPx : 0);
              if (usedWidthPx > rowWidthPx) {
                continue;
              }
            }

            bestVisibleCount = visibleCount;
            break;
          }

          if (bestVisibleCount === 0 && tags.length > 0) {
            bestVisibleCount = 1;
          }

          const visibleTags = tags.slice(0, bestVisibleCount);
          const hiddenTagCount = Math.max(0, tags.length - visibleTags.length);
          const toneClasses = mapTagToneClasses(tags).slice(0, visibleTags.length);
          this.setData({
            visibleTags,
            visibleTagToneClasses: toneClasses,
            hiddenTagCount,
          });
        });
    },
  },
});
