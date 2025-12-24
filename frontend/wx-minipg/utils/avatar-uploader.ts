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

const chooseAvatarMedia = (): Promise<ChooseMediaResult | null> =>
  new Promise((resolve, reject) => {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      sizeType: ['original', 'compressed'],
      success: (res) => {
        const file = res.tempFiles?.[0];
        if (!file) {
          resolve(null);
          return;
        }
        const resolvedSource =
          (res as { sourceType?: string[] })?.sourceType?.[0] ||
          file.fileType ||
          (res as { type?: string }).type ||
          undefined;
        resolve({
          tempFilePath: file.tempFilePath,
          mediaType: file.fileType,
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
          resolve(data?.tempFilePath ?? null);
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

const getFileSize = (filePath: string): Promise<number | null> =>
  new Promise((resolve, reject) => {
    const fileSystem = wx.getFileSystemManager();
    fileSystem.getFileInfo({
      filePath,
      success: (result: WechatMiniprogram.GetFileInfoSuccessCallbackResult) => {
        resolve(result.size);
      },
      fail: (error: WechatMiniprogram.GeneralCallbackResult) => {
        if (isUserCancelError(error)) {
          resolve(null);
          return;
        }
        reject(error);
      },
    });
  });

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

  const croppedFilePath = await openCropper(media.tempFilePath);
  if (!croppedFilePath) {
    return null;
  }

  const fileSize = await getFileSize(croppedFilePath);
  if (fileSize === null || fileSize <= 0) {
    logger.error('Avatar file size invalid', { fileSize });
    void wx.showToast({
      title: '无法读取图片，请重试',
      icon: 'none',
    });
    return null;
  }

  return {
    tempFilePath: croppedFilePath,
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

  let selection: CroppedAvatarResult | null = null;
  try {
    selection = await selectAndCropAvatar();
  } catch (error) {
    handleSelectionError(error);
    return null;
  }

  if (!selection) {
    logger.info('[avatar] upload aborted', {
      durationMs: Date.now() - uploadStart,
      ...logContext,
    });
    return null;
  }

  logContext = buildLogContext(context, selection.sourceType);
  logger.info('[avatar] upload start', logContext);

  void wx.showLoading({ title: '上传中', mask: true });
  try {
    const result = await uploadAvatarToBackend(selection.tempFilePath, selection.fileSize);
    logger.info('[avatar] upload success', {
      duplicate: Boolean(result.duplicate),
      durationMs: Date.now() - uploadStart,
      ...logContext,
    });
    return result;
  } catch (error) {
    handleUploadError(error, {
      durationMs: Date.now() - uploadStart,
      ...logContext,
    });
    return null;
  } finally {
    void wx.hideLoading();
  }
}
