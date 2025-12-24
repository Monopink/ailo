import { uploadFile } from './api';

export interface AvatarUploadResponse {
  file_id: string;
  url: string;
  duplicate?: boolean;
}

export interface AvatarUploadFormData extends Record<string, string> {
  file_type: string;
  mime_type: string;
  file_size: string;
}

export async function uploadAvatarViaProxy(
  filePath: string,
  formData: AvatarUploadFormData
): Promise<AvatarUploadResponse> {
  const response = await uploadFile<AvatarUploadResponse>(
    '/media/upload',
    filePath,
    'file',
    formData
  );

  if (!response?.file_id || !response?.url) {
    throw new Error('上传响应无效');
  }

  return response;
}
