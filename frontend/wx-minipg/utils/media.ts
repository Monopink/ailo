import { post } from './api';

export interface UploadTokenPayload {
  file_type: number;
  mime_type: string;
  file_size: number;
  file_hash?: string | null;
  original_name?: string | null;
}

export interface UploadTokenResult {
  file_id: string;
  upload_url?: string;
  object_key?: string;
  expires_in?: number;
  url?: string;
  duplicate?: boolean;
}

export interface UploadConfirmResult {
  file_id: string;
  url: string;
  duplicate?: boolean;
}

export async function requestAvatarUploadToken(
  payload: UploadTokenPayload
): Promise<UploadTokenResult> {
  return await post<UploadTokenResult, UploadTokenPayload>('/media/upload-token', payload);
}

export async function confirmAvatarUpload(
  fileId: string,
  etag?: string | null
): Promise<UploadConfirmResult> {
  return await post<UploadConfirmResult>('/media/upload-confirm', {
    file_id: fileId,
    etag,
  });
}
