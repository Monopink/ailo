import { mapTagToneClasses } from '../../../utils/tag-tone';

const TAG_GAP_RPX = 6;
const FALLBACK_VISIBLE_COUNT = 1;

interface TagMeasureItem {
  key: string;
  text: string;
  kind: 'tag' | 'overflow';
  hiddenCount?: number;
}

interface TagMeasureSnapshot {
  rowWidthPx: number;
  tagWidths: Array<number | undefined>;
  overflowWidths: Map<number, number>;
}

interface TagFitContext {
  tagsCount: number;
  tagWidths: Array<number | undefined>;
  rowWidthPx: number;
  gapPx: number;
  overflowWidths: Map<number, number>;
}

interface TagLayoutPayload {
  visibleTags: string[];
  visibleTagToneClasses: string[];
  hiddenTagCount: number;
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

const computeFallbackLayout = (
  tags: string[]
): { visibleTags: string[]; hiddenTagCount: number } => {
  const visibleTags = tags.slice(0, FALLBACK_VISIBLE_COUNT);
  return {
    visibleTags,
    hiddenTagCount: Math.max(0, tags.length - visibleTags.length),
  };
};

const parseMeasureSnapshot = (
  queryResult: unknown,
  measureItems: TagMeasureItem[]
): TagMeasureSnapshot | null => {
  if (!Array.isArray(queryResult) || queryResult.length < 2) {
    return null;
  }

  const measureRectValues: unknown = queryResult[0];
  const rowRectValue: unknown = queryResult[1];
  if (
    !Array.isArray(measureRectValues) ||
    rowRectValue === null ||
    typeof rowRectValue !== 'object'
  ) {
    return null;
  }
  if (measureRectValues.length === 0) {
    return null;
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

  return {
    rowWidthPx,
    tagWidths,
    overflowWidths,
  };
};

const canFitVisibleCount = (visibleCount: number, context: TagFitContext): boolean => {
  const { tagsCount, tagWidths, rowWidthPx, gapPx, overflowWidths } = context;
  const hiddenCount = tagsCount - visibleCount;
  let usedWidthPx = 0;

  for (let index = 0; index < visibleCount; index += 1) {
    const width = tagWidths[index];
    if (typeof width !== 'number') {
      return false;
    }
    usedWidthPx += width + (index > 0 ? gapPx : 0);
    if (usedWidthPx > rowWidthPx) {
      return false;
    }
  }

  if (hiddenCount === 0) {
    return true;
  }

  const overflowWidth = overflowWidths.get(hiddenCount);
  if (typeof overflowWidth !== 'number') {
    return false;
  }

  usedWidthPx += overflowWidth + (visibleCount > 0 ? gapPx : 0);
  return usedWidthPx <= rowWidthPx;
};

const resolveVisibleCount = (
  tagsCount: number,
  tagWidths: Array<number | undefined>,
  rowWidthPx: number,
  overflowWidths: Map<number, number>
): number => {
  const gapPx = (getWindowWidthPx() / 750) * TAG_GAP_RPX;
  const fitContext: TagFitContext = {
    tagsCount,
    tagWidths,
    rowWidthPx,
    gapPx,
    overflowWidths,
  };

  for (let visibleCount = tagsCount; visibleCount >= 0; visibleCount -= 1) {
    if (canFitVisibleCount(visibleCount, fitContext)) {
      return visibleCount === 0 && tagsCount > 0 ? 1 : visibleCount;
    }
  }

  return tagsCount > 0 ? 1 : 0;
};

const buildLayoutPayload = (tags: string[], visibleCount: number): TagLayoutPayload => {
  const visibleTags = tags.slice(0, visibleCount);
  return {
    visibleTags,
    visibleTagToneClasses: mapTagToneClasses(tags).slice(0, visibleTags.length),
    hiddenTagCount: Math.max(0, tags.length - visibleTags.length),
  };
};

Component({
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
    visibleTags: [] as string[],
    visibleTagToneClasses: [] as string[],
    hiddenTagCount: 0,
    measureItems: [] as TagMeasureItem[],
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

    measureAndCompute(tags: string[], measureItems: TagMeasureItem[]) {
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
          const snapshot = parseMeasureSnapshot(queryResult, measureItems);
          if (snapshot === null) {
            return;
          }
          const { rowWidthPx, tagWidths, overflowWidths } = snapshot;

          if (tagWidths.length < Math.min(tags.length, 1)) {
            const fallback = computeFallbackLayout(tags);
            this.setData({
              visibleTags: fallback.visibleTags,
              visibleTagToneClasses: mapTagToneClasses(tags).slice(0, fallback.visibleTags.length),
              hiddenTagCount: fallback.hiddenTagCount,
            });
            return;
          }

          const visibleCount = resolveVisibleCount(
            tags.length,
            tagWidths,
            rowWidthPx,
            overflowWidths
          );
          this.setData(buildLayoutPayload(tags, visibleCount));
        });
    },
  },
});
