import type { ApiError } from './api';
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

interface CroppedAvatarResult {
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
  if (!error) {
    return false;
  }
  if (typeof error === 'string') {
    return error.toLowerCase().includes('cancel');
  }
  if (typeof error === 'object') {
    const errMsg = (error as { errMsg?: string }).errMsg;
    const message = errMsg || (error as { message?: string }).message;
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

// Removed downloadTmpFile - http://tmp/... paths are valid and should be used directly

const ensureLocalFilePath = async (filePath: string): Promise<string> => {
  // http://tmp/... is a valid local file protocol in DevTools (equivalent to wxfile:// on devices)
  // No conversion needed - wx APIs support both protocols natively
  if (HTTP_TMP_PREFIX.test(filePath)) {
    logger.info('[avatar] using DevTools temp file path', {
      pathPrefix: filePath.substring(0, 30),
    });
  }
  return filePath;
};

const resolveEnvironmentTag = (): string => {
  try {
    const info = wx.getSystemInfoSync();
    if (!info) {
      return 'unknown';
    }
    const platform = info.platform || 'unknown';
    const version = (info as { version?: string }).version;
    return version ? `${platform}:${version}` : platform;
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
        if (!file) {
          resolve(null);
          return;
        }
        const resolvedSource =
          (res as { sourceType?: string[] }).sourceType?.[0] ||
          file.fileType ||
          (res as { type?: string }).type ||
          undefined;
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
        reject(error);
      },
    });
  });

const openCropper = (filePath: string): Promise<string | null> =>
  new Promise((resolve, reject) => {
    let resolved = false;
    wx.navigateTo({
      url: '/pages/avatar-cropper/avatar-cropper',
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
          reject(error);
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
      fail: reject,
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
  // DevTools uses http://tmp/... protocol which FileSystemManager APIs don't support
  // Return 0 to signal backend to use actual file size
  if (HTTP_TMP_PREFIX.test(filePath)) {
    logger.info('[avatar] DevTools path - skipping file size check, backend will detect', {
      pathPrefix: filePath.substring(0, 30),
    });
    return 0;
  }

  // Real device uses wxfile:// protocol which FileSystemManager supports
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

const mapApiErrorMessage = (error: ApiError): string => {
  switch (error.statusCode) {
    case 401:
      return '登录已失效，请重新登录';
    case 413:
      return '图片过大（最大2MB）';
    case 415:
      return '图片格式不支持';
    case 429:
      return '今日上传次数已用完';
    default:
      return error.message || '上传失败，请重试';
  }
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

const handleUploadError = (error: unknown, logContext?: Record<string, unknown>): void => {
  if (isUserCancelError(error)) {
    return;
  }

  let message = '上传失败，请重试';

  let statusCode: number | undefined;
  let errorCode: string | number | undefined;
  let retryAfter: string | number | undefined;
  let detail: unknown;

  if (error && typeof error === 'object' && 'statusCode' in error) {
    const apiError = error as ApiError & { detail?: unknown };
    message = mapApiErrorMessage(apiError);
    statusCode = apiError.statusCode ?? apiError.status;
    errorCode = apiError.errorCode;
    retryAfter = apiError.retryAfter;
    const dataRecord =
      apiError.data && typeof apiError.data === 'object'
        ? (apiError.data as Record<string, unknown>)
        : undefined;
    if (dataRecord && 'detail' in dataRecord) {
      detail = dataRecord.detail;
    } else if (apiError.detail !== undefined) {
      detail = apiError.detail;
    }
  } else if (error instanceof Error && error.message) {
    message = error.message;
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

export async function selectAndCropAvatar(): Promise<CroppedAvatarResult | null> {
  const media = await chooseAvatarMedia();
  if (!media) {
    return null;
  }

  const normalizedSourcePath = await ensureLocalFilePath(media.tempFilePath);
  const croppedFilePath = await openCropper(normalizedSourcePath);
  if (!croppedFilePath) {
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

  const fileSize = await resolveFileSize(normalizedCroppedPath);
  if (fileSize === null) {
    logger.error('Avatar file size check failed', { filePath: normalizedCroppedPath });
    void wx.showToast({
      title: '无法读取图片，请重试',
      icon: 'none',
    });
    return null;
  }

  return {
    tempFilePath: normalizedCroppedPath,
    fileSize,
    sourceType: media.sourceType,
  };
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

export async function completeAvatarUpload(
  context?: AvatarUploadContext
): Promise<AvatarUploadResult | null> {
  const uploadStart = Date.now();
  let logContext = buildLogContext(context);
  const environment = resolveEnvironmentTag();

  let selection: CroppedAvatarResult | null = null;
  let selectionDurationMs = 0;
  try {
    selection = await selectAndCropAvatar();
    selectionDurationMs = Date.now() - uploadStart;
  } catch (error) {
    handleSelectionError(error);
    return null;
  }

  if (!selection) {
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
}
