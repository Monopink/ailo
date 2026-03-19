import { isDefined } from './guards';
import { getLogger } from './logger';

const logger = getLogger('AvatarImage');

export const AVATAR_OUTPUT_SIZE = 512;

export interface SquareCropSourceRect {
  sourceX: number;
  sourceY: number;
  sourceSize: number;
}

interface CanvasExportOptions {
  imagePath: string;
  cropSourceRect: SquareCropSourceRect;
  canvas2dSelector: string;
  legacyCanvasId: string;
}

export function getAvatarImageInfo(
  filePath: string
): Promise<WechatMiniprogram.GetImageInfoSuccessCallbackResult> {
  return new Promise((resolve, reject) => {
    wx.getImageInfo({
      src: filePath,
      success: resolve,
      fail: reject,
    });
  });
}

export function resolveCenteredSquareCropSourceRect(imageInfo: {
  width: number;
  height: number;
}): SquareCropSourceRect {
  const sourceSize = Math.min(imageInfo.width, imageInfo.height);
  return {
    sourceX: Math.max(0, (imageInfo.width - sourceSize) / 2),
    sourceY: Math.max(0, (imageInfo.height - sourceSize) / 2),
    sourceSize,
  };
}

export async function exportCenteredSquareAvatar(options: {
  imagePath: string;
  canvas2dSelector: string;
  legacyCanvasId: string;
}): Promise<string> {
  const imageInfo = await getAvatarImageInfo(options.imagePath);
  const cropSourceRect = resolveCenteredSquareCropSourceRect(imageInfo);
  return await exportSquareAvatar({
    imagePath: options.imagePath,
    cropSourceRect,
    canvas2dSelector: options.canvas2dSelector,
    legacyCanvasId: options.legacyCanvasId,
  });
}

export async function exportSquareAvatar(options: CanvasExportOptions): Promise<string> {
  try {
    const canvas = await getCanvasNode(options.canvas2dSelector);
    const context = canvas.getContext('2d');
    const dpr = resolvePixelRatio();

    canvas.width = AVATAR_OUTPUT_SIZE * dpr;
    canvas.height = AVATAR_OUTPUT_SIZE * dpr;

    if (typeof context.setTransform === 'function') {
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
    } else {
      context.scale(dpr, dpr);
    }
    context.clearRect(0, 0, AVATAR_OUTPUT_SIZE, AVATAR_OUTPUT_SIZE);

    const image = await loadCanvasImage(canvas, options.imagePath);
    context.drawImage(
      image,
      options.cropSourceRect.sourceX,
      options.cropSourceRect.sourceY,
      options.cropSourceRect.sourceSize,
      options.cropSourceRect.sourceSize,
      0,
      0,
      AVATAR_OUTPUT_SIZE,
      AVATAR_OUTPUT_SIZE
    );

    return await exportCanvasToTempFile2D(canvas);
  } catch (error) {
    logger.warn('Canvas 2D export failed, fallback to legacy canvas', {
      error: serializeError(error),
    });
    return await exportSquareAvatarWithLegacyCanvas(options);
  }
}

function resolvePixelRatio(): number {
  if (typeof wx.getWindowInfo === 'function') {
    const windowInfo = wx.getWindowInfo();
    if (typeof windowInfo.pixelRatio === 'number' && Number.isFinite(windowInfo.pixelRatio)) {
      return Math.max(1, windowInfo.pixelRatio);
    }
  }
  return 2;
}

function getCanvasNode(canvasSelector: string): Promise<WechatMiniprogram.Canvas> {
  return new Promise((resolve, reject) => {
    wx.createSelectorQuery()
      .select(canvasSelector)
      .fields({ node: true, size: true }, (result) => {
        const canvas = (result as { node?: WechatMiniprogram.Canvas } | null)?.node;
        if (isDefined(canvas)) {
          resolve(canvas);
          return;
        }
        reject(new Error('CANVAS_NODE_NOT_FOUND'));
      })
      .exec();
  });
}

function loadCanvasImage(
  canvas: WechatMiniprogram.Canvas,
  imagePath: string
): Promise<WechatMiniprogram.Image> {
  return new Promise((resolve, reject) => {
    const image = canvas.createImage();
    image.onload = () => resolve(image);
    image.onerror = (error: unknown) =>
      reject(error instanceof Error ? error : new Error(String(error)));
    image.src = imagePath;
  });
}

function exportCanvasToTempFile2D(canvas: WechatMiniprogram.Canvas): Promise<string> {
  return new Promise((resolve, reject) => {
    const exportOptions = {
      canvas: canvas as unknown as WechatMiniprogram.IAnyObject,
      width: canvas.width,
      height: canvas.height,
      destWidth: AVATAR_OUTPUT_SIZE,
      destHeight: AVATAR_OUTPUT_SIZE,
      fileType: 'webp',
      quality: 0.85,
      success: (res: WechatMiniprogram.CanvasToTempFilePathSuccessCallbackResult) =>
        resolve(res.tempFilePath),
      fail: reject,
    } as unknown as WechatMiniprogram.CanvasToTempFilePathOption;
    void wx.canvasToTempFilePath(exportOptions);
  });
}

function exportSquareAvatarWithLegacyCanvas(options: CanvasExportOptions): Promise<string> {
  return new Promise((resolve, reject) => {
    const ctx = wx.createCanvasContext(options.legacyCanvasId);
    ctx.drawImage(
      options.imagePath,
      options.cropSourceRect.sourceX,
      options.cropSourceRect.sourceY,
      options.cropSourceRect.sourceSize,
      options.cropSourceRect.sourceSize,
      0,
      0,
      AVATAR_OUTPUT_SIZE,
      AVATAR_OUTPUT_SIZE
    );
    ctx.draw(false, () => {
      const exportOptions = {
        canvasId: options.legacyCanvasId,
        width: AVATAR_OUTPUT_SIZE,
        height: AVATAR_OUTPUT_SIZE,
        destWidth: AVATAR_OUTPUT_SIZE,
        destHeight: AVATAR_OUTPUT_SIZE,
        fileType: 'webp',
        quality: 0.85,
        success: (res: WechatMiniprogram.CanvasToTempFilePathSuccessCallbackResult) =>
          resolve(res.tempFilePath),
        fail: reject,
      } as unknown as WechatMiniprogram.CanvasToTempFilePathOption;
      void wx.canvasToTempFilePath(exportOptions, undefined);
    });
  });
}

function serializeError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}
