import type { ApiError } from './api';
import { exportCenteredSquareAvatar } from './avatar-image';
import { isDefined, isNonEmptyString } from './guards';
import { getLogger } from './logger';
import {
  uploadAvatarViaProxy,
  type AvatarUploadFormData,
  type AvatarUploadResponse,
} from './media';

const logger = getLogger('AvatarUploader');
const AVATAR_FILE_TYPE = '1';
const AVATAR_MIME_TYPE = 'image/webp';
const HTTP_TMP_PREFIX = /^https?:\/\/tmp\//i;
const AVATAR_EXPORT_CANVAS_2D_SELECTOR = '#avatarExportCanvas2d';
const AVATAR_EXPORT_CANVAS_LEGACY_ID = 'avatarExportCanvasLegacy';
const AVATAR_MAX_UPLOAD_BYTES = 1024 * 1024;
const AVATAR_REENCODE_QUALITY_STEPS = [0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5];

interface PreparedAvatarResult {
  tempFilePath: string;
  fileSize: number;
  sourceType?: string;
}

interface ChooseMediaResult {
  tempFilePath: string;
  sourceType?: string;
}

export interface AvatarUploadResult {
  fileId: string;
  url: string;
  duplicate?: boolean;
}

export interface AvatarUploadContext {
  page?: string;
  sourceType?: string;
}

const buildLogContext = (
  context?: AvatarUploadContext,
  actualSourceType?: string
): Record<string, unknown> => ({
  page: context?.page ?? 'unknown',
  sourceType: actualSourceType ?? context?.sourceType ?? 'unknown',
});

const isUserCancelError = (error: unknown): boolean => {
  if (error === null || error === undefined) {
    return false;
  }
  if (typeof error === 'string') {
    return error.toLowerCase().includes('cancel');
  }
  if (typeof error === 'object') {
    const errMsg = (error as { errMsg?: string }).errMsg;
    const message = errMsg ?? (error as { message?: string }).message;
    if (typeof message === 'string') {
      return message.toLowerCase().includes('cancel');
    }
  }
  return false;
};

const serializeError = (error: unknown): string => {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === 'string') {
    return error;
  }
  try {
    return JSON.stringify(error);
  } catch {
    return String(error);
  }
};

const pickNonEmptyString = (...values: Array<string | undefined | null>): string | undefined =>
  values.find((value) => isNonEmptyString(value));

const ensureLocalFilePath = (filePath: string): Promise<string> => {
  if (HTTP_TMP_PREFIX.test(filePath)) {
    logger.info('[avatar] using DevTools temp file path', {
      pathPrefix: filePath.substring(0, 30),
    });
  }
  return Promise.resolve(filePath);
};

const resolveEnvironmentTag = (): string => {
  try {
    const deviceInfo = typeof wx.getDeviceInfo === 'function' ? wx.getDeviceInfo() : undefined;
    const platform = isNonEmptyString(deviceInfo?.platform) ? deviceInfo.platform : 'unknown';
    const version =
      typeof wx.getAppBaseInfo === 'function' ? wx.getAppBaseInfo().version : undefined;
    return isNonEmptyString(version) ? `${platform}:${version}` : platform;
  } catch {
    return 'unknown';
  }
};

const chooseAvatarMedia = (): Promise<ChooseMediaResult | null> =>
  new Promise((resolve, reject) => {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      sizeType: ['original', 'compressed'],
      success: (res) => {
        const file = res.tempFiles[0];
        if (!isDefined(file)) {
          resolve(null);
          return;
        }
        const resolvedSource = pickNonEmptyString(
          (res as { sourceType?: string[] }).sourceType?.[0],
          file.fileType,
          (res as { type?: string }).type
        );
        resolve({
          tempFilePath: file.tempFilePath,
          sourceType: resolvedSource,
        });
      },
      fail: (error) => {
        if (isUserCancelError(error)) {
          resolve(null);
          return;
        }
        reject(new Error(serializeError(error)));
      },
    });
  });

const openCropper = (filePath: string): Promise<string | null> =>
  new Promise((resolve, reject) => {
    let resolved = false;
    wx.navigateTo({
      url: '/pkg/avatar-cropper/avatar-cropper',
      events: {
        cropComplete: (data: { tempFilePath?: string }) => {
          resolved = true;
          resolve(data.tempFilePath ?? null);
        },
        cropCancel: () => {
          resolved = true;
          resolve(null);
        },
      },
      success: (res) => {
        res.eventChannel.emit('init', { filePath });
      },
      fail: (error) => {
        if (!resolved) {
          reject(new Error(serializeError(error)));
        }
      },
    });
  });

const readFileSize = (filePath: string): Promise<number> =>
  new Promise((resolve, reject) => {
    const fileSystem = wx.getFileSystemManager();
    type ReadFileOption = Parameters<typeof fileSystem.readFile>[0];
    type ReadFileSuccess = NonNullable<ReadFileOption['success']>;
    type ReadFileResult = Parameters<ReadFileSuccess>[0];
    fileSystem.readFile({
      filePath,
      success: (result: ReadFileResult) => {
        const data = result.data;
        if (data instanceof ArrayBuffer) {
          resolve(data.byteLength);
          return;
        }
        if (typeof data === 'string') {
          resolve(data.length);
          return;
        }
        reject(new Error('无法解析文件内容'));
      },
      fail: (error) => reject(new Error(serializeError(error))),
    });
  });

const getFileInfoSize = (filePath: string): Promise<number> =>
  new Promise((resolve, reject) => {
    const fileSystem = wx.getFileSystemManager();
    fileSystem.getFileInfo({
      filePath,
      success: (result: WechatMiniprogram.GetFileInfoSuccessCallbackResult) => {
        resolve(result.size);
      },
      fail: reject,
    });
  });

const resolveFileSize = async (filePath: string): Promise<number | null> => {
  if (HTTP_TMP_PREFIX.test(filePath)) {
    logger.info('[avatar] DevTools path - skipping file size check, backend will detect', {
      pathPrefix: filePath.substring(0, 30),
    });
    return 0;
  }

  try {
    return await getFileInfoSize(filePath);
  } catch (error) {
    if (isUserCancelError(error)) {
      return null;
    }
    logger.warn('[avatar] file info unavailable, fallback to readFile', {
      filePath,
      error: serializeError(error),
    });
    try {
      return await readFileSize(filePath);
    } catch (fallbackError) {
      if (isUserCancelError(fallbackError)) {
        return null;
      }
      logger.error('[avatar] unable to read file size', {
        filePath,
        error: serializeError(fallbackError),
      });
      throw fallbackError;
    }
  }
};

interface ApiErrorMetadata {
  message: string;
  statusCode?: number;
  errorCode?: string | number;
  retryAfter?: string | number;
  detail?: unknown;
}

const mapApiErrorMessage = (error: ApiError): string => {
  switch (error.statusCode) {
    case 401:
      return '登录已失效，请重新登录';
    case 413:
      return '图片过大（最大1MB）';
    case 415:
      return '图片格式不支持';
    case 429:
      return '今日上传次数已用完';
    default:
      return isNonEmptyString(error.message) ? error.message : '上传失败，请重试';
  }
};

const extractApiErrorMetadata = (apiError: ApiError & { detail?: unknown }): ApiErrorMetadata => {
  const dataRecord =
    apiError.data !== null && apiError.data !== undefined && typeof apiError.data === 'object'
      ? (apiError.data as Record<string, unknown>)
      : undefined;
  let detail: unknown;
  if (dataRecord !== undefined && 'detail' in dataRecord) {
    detail = dataRecord.detail;
  } else if (apiError.detail !== undefined) {
    detail = apiError.detail;
  }
  const retryAfter = apiError.retryAfter === null ? undefined : apiError.retryAfter;
  return {
    message: mapApiErrorMessage(apiError),
    statusCode: apiError.statusCode ?? apiError.status,
    errorCode: apiError.errorCode,
    retryAfter,
    detail,
  };
};

const handleSelectionError = (error: unknown): void => {
  if (isUserCancelError(error)) {
    return;
  }
  logger.error('Avatar selection failed', { error: serializeError(error) });
  void wx.showToast({
    title: '选择图片失败，请重试',
    icon: 'none',
  });
};

const handlePreparationError = (error: unknown): void => {
  if (isUserCancelError(error)) {
    return;
  }
  logger.error('Avatar preparation failed', { error: serializeError(error) });
  void wx.showToast({
    title: '处理图片失败，请重试',
    icon: 'none',
  });
};

const handleUploadError = (error: unknown, logContext?: Record<string, unknown>): void => {
  if (isUserCancelError(error)) {
    return;
  }

  let message = '上传失败，请重试';

  let statusCode: number | undefined;
  let errorCode: string | number | undefined;
  let retryAfter: string | number | undefined;
  let detail: unknown;

  if (error !== null && error !== undefined && typeof error === 'object' && 'statusCode' in error) {
    const apiError = error as ApiError & { detail?: unknown };
    const metadata = extractApiErrorMetadata(apiError);
    message = metadata.message;
    statusCode = metadata.statusCode;
    errorCode = metadata.errorCode;
    retryAfter = metadata.retryAfter;
    detail = metadata.detail;
  } else if (error instanceof Error) {
    const errorMessage = error.message;
    if (isNonEmptyString(errorMessage)) {
      message = errorMessage;
    }
  }

  logger.error('[avatar] upload fail', {
    error: serializeError(error),
    statusCode,
    errorCode,
    retryAfter,
    detail,
    ...(logContext ?? {}),
  });
  void wx.showToast({
    title: message,
    icon: 'none',
  });
};

const finalizePreparedAvatarFile = async (
  tempFilePath: string,
  sourceType?: string
): Promise<PreparedAvatarResult | null> => {
  const limitedFile = await ensureAvatarUploadWithinLimit(tempFilePath);
  const fileSize = limitedFile.fileSize;
  if (fileSize === null) {
    logger.error('Avatar file size check failed', { filePath: tempFilePath });
    void wx.showToast({
      title: '无法读取图片，请重试',
      icon: 'none',
    });
    return null;
  }

  return {
    tempFilePath: limitedFile.filePath,
    fileSize,
    sourceType,
  };
};

const ensureAvatarUploadWithinLimit = async (
  tempFilePath: string
): Promise<{ filePath: string; fileSize: number | null }> => {
  const originalSize = await resolveFileSize(tempFilePath);
  if (originalSize === null) {
    return { filePath: tempFilePath, fileSize: null };
  }
  if (originalSize === 0 || originalSize <= AVATAR_MAX_UPLOAD_BYTES) {
    return { filePath: tempFilePath, fileSize: originalSize };
  }

  logger.info('[avatar] file too large, start auto-reencode', {
    originalSize,
    maxUploadBytes: AVATAR_MAX_UPLOAD_BYTES,
  });

  const result = await tryReencodeAvatarToLimit({
    qualityIndex: 0,
    bestPath: tempFilePath,
    bestSize: originalSize,
  });
  if (result.fileSize > AVATAR_MAX_UPLOAD_BYTES) {
    logger.warn('[avatar] auto-reencode still exceeds upload limit', {
      originalSize,
      bestSize: result.fileSize,
      maxUploadBytes: AVATAR_MAX_UPLOAD_BYTES,
    });
  }
  return result;
};

const tryReencodeAvatarToLimit = async (params: {
  qualityIndex: number;
  bestPath: string;
  bestSize: number;
}): Promise<{ filePath: string; fileSize: number }> => {
  const { qualityIndex, bestPath, bestSize } = params;
  if (qualityIndex >= AVATAR_REENCODE_QUALITY_STEPS.length) {
    return { filePath: bestPath, fileSize: bestSize };
  }

  const quality = AVATAR_REENCODE_QUALITY_STEPS[qualityIndex];
  const reencodedPath = await exportCenteredSquareAvatar({
    imagePath: bestPath,
    canvas2dSelector: AVATAR_EXPORT_CANVAS_2D_SELECTOR,
    legacyCanvasId: AVATAR_EXPORT_CANVAS_LEGACY_ID,
    quality,
  });
  const reencodedSize = await resolveFileSize(reencodedPath);
  if (reencodedSize === null) {
    return await tryReencodeAvatarToLimit({
      qualityIndex: qualityIndex + 1,
      bestPath,
      bestSize,
    });
  }
  if (reencodedSize === 0) {
    return { filePath: reencodedPath, fileSize: 0 };
  }
  const nextBest =
    reencodedSize < bestSize
      ? { bestPath: reencodedPath, bestSize: reencodedSize }
      : { bestPath, bestSize };
  if (reencodedSize <= AVATAR_MAX_UPLOAD_BYTES) {
    logger.info('[avatar] auto-reencode reached upload limit', {
      quality,
      fileSize: reencodedSize,
    });
    return { filePath: reencodedPath, fileSize: reencodedSize };
  }
  return await tryReencodeAvatarToLimit({
    qualityIndex: qualityIndex + 1,
    bestPath: nextBest.bestPath,
    bestSize: nextBest.bestSize,
  });
};

const selectAndCropAvatarFromTempFile = async (
  tempFilePath: string,
  sourceType?: string
): Promise<PreparedAvatarResult | null> => {
  const normalizedSourcePath = await ensureLocalFilePath(tempFilePath);
  const croppedFilePath = await openCropper(normalizedSourcePath);
  if (croppedFilePath === null) {
    return null;
  }

  let normalizedCroppedPath: string;
  try {
    normalizedCroppedPath = await ensureLocalFilePath(croppedFilePath);
  } catch (error) {
    logger.error('[avatar] cropped file normalization failed', {
      filePath: croppedFilePath,
      error: serializeError(error),
    });
    void wx.showToast({
      title: '处理图片失败，请重试',
      icon: 'none',
    });
    return null;
  }

  return await finalizePreparedAvatarFile(normalizedCroppedPath, sourceType);
};

const prepareWechatAvatarFromTempFile = async (
  tempFilePath: string,
  sourceType?: string
): Promise<PreparedAvatarResult | null> => {
  let normalizedSourcePath: string;
  let exportedTempFilePath: string;

  try {
    normalizedSourcePath = await ensureLocalFilePath(tempFilePath);
    exportedTempFilePath = await exportCenteredSquareAvatar({
      imagePath: normalizedSourcePath,
      canvas2dSelector: AVATAR_EXPORT_CANVAS_2D_SELECTOR,
      legacyCanvasId: AVATAR_EXPORT_CANVAS_LEGACY_ID,
    });
  } catch (error) {
    logger.error('[avatar] wechat avatar export failed', {
      filePath: tempFilePath,
      error: serializeError(error),
    });
    void wx.showToast({
      title: '处理图片失败，请重试',
      icon: 'none',
    });
    return null;
  }

  const normalizedExportedPath = await ensureLocalFilePath(exportedTempFilePath);
  return await finalizePreparedAvatarFile(normalizedExportedPath, sourceType);
};

export async function selectAndCropAvatar(): Promise<PreparedAvatarResult | null> {
  const media = await chooseAvatarMedia();
  if (!isDefined(media)) {
    return null;
  }
  return await selectAndCropAvatarFromTempFile(media.tempFilePath, media.sourceType);
}

export async function uploadAvatarToBackend(
  filePath: string,
  fileSize: number
): Promise<AvatarUploadResult> {
  const formData: AvatarUploadFormData = {
    file_type: AVATAR_FILE_TYPE,
    mime_type: AVATAR_MIME_TYPE,
    file_size: String(fileSize),
  };

  const response: AvatarUploadResponse = await uploadAvatarViaProxy(filePath, formData);
  return {
    fileId: response.file_id,
    url: response.url,
    duplicate: response.duplicate,
  };
}

interface CompleteAvatarUploadOptions {
  context?: AvatarUploadContext;
  prepare: () => Promise<PreparedAvatarResult | null>;
  onPrepareError: (error: unknown) => void;
}

const completePreparedAvatarUpload = async ({
  context,
  prepare,
  onPrepareError,
}: CompleteAvatarUploadOptions): Promise<AvatarUploadResult | null> => {
  const uploadStart = Date.now();
  let logContext = buildLogContext(context);
  const environment = resolveEnvironmentTag();

  let selection: PreparedAvatarResult | null = null;
  let selectionDurationMs = 0;
  try {
    selection = await prepare();
    selectionDurationMs = Date.now() - uploadStart;
  } catch (error) {
    onPrepareError(error);
    return null;
  }

  if (!isDefined(selection)) {
    logger.info('[avatar] upload aborted', {
      durationMs: Date.now() - uploadStart,
      selectionDurationMs,
      environment,
      ...logContext,
    });
    return null;
  }

  logContext = buildLogContext(context, selection.sourceType);
  logger.info('[avatar] upload start', {
    environment,
    selectionDurationMs,
    ...logContext,
  });

  void wx.showLoading({ title: '上传中', mask: true });
  try {
    const result = await uploadAvatarToBackend(selection.tempFilePath, selection.fileSize);
    logger.info('[avatar] upload success', {
      duplicate: Boolean(result.duplicate),
      durationMs: Date.now() - uploadStart,
      selectionDurationMs,
      uploadDurationMs: Date.now() - uploadStart - selectionDurationMs,
      environment,
      ...logContext,
    });
    return result;
  } catch (error) {
    handleUploadError(error, {
      durationMs: Date.now() - uploadStart,
      selectionDurationMs,
      environment,
      ...logContext,
    });
    return null;
  } finally {
    void wx.hideLoading();
  }
};

export async function completeAvatarUpload(
  context?: AvatarUploadContext
): Promise<AvatarUploadResult | null> {
  return await completePreparedAvatarUpload({
    context,
    prepare: async () => await selectAndCropAvatar(),
    onPrepareError: handleSelectionError,
  });
}

export async function completeWechatAvatarUpload(
  tempFilePath: string,
  context?: AvatarUploadContext
): Promise<AvatarUploadResult | null> {
  return await completePreparedAvatarUpload({
    context,
    prepare: async () => await prepareWechatAvatarFromTempFile(tempFilePath, context?.sourceType),
    onPrepareError: handlePreparationError,
  });
}
