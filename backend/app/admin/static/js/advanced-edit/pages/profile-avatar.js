import { withButtonLoading } from '../common/save-flow.js';

const config = window.qiaoAdvancedEditProfileAvatarConfig || {};

function requireNumericId(value, name) {
  const strValue = typeof value === 'string' ? value : String(value ?? '');
  if (!/^\d+$/.test(strValue)) {
    throw new Error(`Invalid ${name} for profile avatar advanced edit page`);
  }
  return strValue;
}

const profileId = requireNumericId(config.profileId, 'profileId');

const uploadUrl = `/admin-api/profile/${profileId}/avatar/upload`;
const clearUrl = `/admin-api/profile/${profileId}/avatar/clear`;

const avatarFile = document.getElementById('avatarFile');
const avatarDropZone = document.getElementById('avatarDropZone');
const sourceImage = document.getElementById('sourceImage');
const cropPreviewSquare = document.getElementById('cropPreviewSquare');
const cropPreviewCircle = document.getElementById('cropPreviewCircle');
const statusText = document.getElementById('statusText');
const cropX = document.getElementById('cropX');
const cropY = document.getElementById('cropY');
const cropSize = document.getElementById('cropSize');
const currentAvatar = document.getElementById('currentAvatar');
const currentMediaId = document.getElementById('currentMediaId');
const avatarForm = document.getElementById('avatarForm');
const uploadBtn = document.getElementById('uploadBtn');
const clearBtn = document.getElementById('clearBtn');
const resetCropBtn = document.getElementById('resetCropBtn');

let imageNaturalWidth = 0;
let imageNaturalHeight = 0;
let activeObjectUrl = null;
const POSITION_SLIDER_MIN = 0;
const POSITION_SLIDER_MAX = 1000;
const cropState = {
  centerX: 0,
  centerY: 0,
  size: 1,
};

function setStatus(message, isError = false) {
  statusText.textContent = message;
  statusText.classList.toggle('text-danger', isError);
  statusText.classList.toggle('text-secondary', !isError);
}

function isImageFile(file) {
  return !!(file && typeof file.type === 'string' && file.type.startsWith('image/'));
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function getImageSide() {
  return Math.min(imageNaturalWidth, imageNaturalHeight);
}

function getMaxOffset(size) {
  return {
    x: Math.max(0, imageNaturalWidth - size),
    y: Math.max(0, imageNaturalHeight - size),
  };
}

function sliderValueToSize(value) {
  const side = getImageSide();
  if (side <= 0) {
    return 1;
  }
  const raw = Number(value);
  const clampedRaw = clamp(Number.isFinite(raw) ? raw : 1, 1, side);
  // Keep existing slider semantics: left (1) means max crop size.
  return side - clampedRaw + 1;
}

function sizeToSliderValue(size) {
  const side = getImageSide();
  if (side <= 0) {
    return 1;
  }
  const clampedSize = clamp(size, 1, side);
  return side - clampedSize + 1;
}

function clampCropState() {
  const side = getImageSide();
  if (side <= 0) {
    cropState.size = 1;
    cropState.centerX = 0.5;
    cropState.centerY = 0.5;
    return;
  }
  cropState.size = clamp(cropState.size, 1, side);
  const half = cropState.size / 2;
  cropState.centerX = clamp(cropState.centerX, half, imageNaturalWidth - half);
  cropState.centerY = clamp(cropState.centerY, half, imageNaturalHeight - half);
}

function getCropRectFromState() {
  clampCropState();
  const { x: maxX, y: maxY } = getMaxOffset(cropState.size);
  const x = clamp(cropState.centerX - cropState.size / 2, 0, maxX);
  const y = clamp(cropState.centerY - cropState.size / 2, 0, maxY);
  return {
    x,
    y,
    size: cropState.size,
  };
}

function syncSizeSliderFromState() {
  const side = getImageSide();
  cropSize.min = '1';
  cropSize.max = String(Math.max(1, side));
  cropSize.value = String(Math.round(sizeToSliderValue(cropState.size)));
}

function syncPositionSlidersFromState() {
  const rect = getCropRectFromState();
  const { x: maxX, y: maxY } = getMaxOffset(rect.size);
  const range = POSITION_SLIDER_MAX - POSITION_SLIDER_MIN;
  const normalizedX = maxX > 0 ? rect.x / maxX : 0.5;
  const normalizedY = maxY > 0 ? rect.y / maxY : 0.5;
  cropX.min = String(POSITION_SLIDER_MIN);
  cropX.max = String(POSITION_SLIDER_MAX);
  cropY.min = String(POSITION_SLIDER_MIN);
  cropY.max = String(POSITION_SLIDER_MAX);
  cropX.value = String(Math.round(POSITION_SLIDER_MIN + normalizedX * range));
  cropY.value = String(Math.round(POSITION_SLIDER_MIN + normalizedY * range));
}

function drawPreview() {
  if (!sourceImage.src || imageNaturalWidth === 0 || imageNaturalHeight === 0) {
    return;
  }
  const { x, y, size } = getCropRectFromState();
  if (cropPreviewSquare) {
    const squareCtx = cropPreviewSquare.getContext('2d');
    if (!squareCtx) {
      setStatus('Square canvas context unavailable.', true);
      return;
    }
    squareCtx.clearRect(0, 0, cropPreviewSquare.width, cropPreviewSquare.height);
    squareCtx.drawImage(sourceImage, x, y, size, size, 0, 0, cropPreviewSquare.width, cropPreviewSquare.height);
  }

  if (cropPreviewCircle) {
    const circleCtx = cropPreviewCircle.getContext('2d');
    if (!circleCtx) {
      setStatus('Circle canvas context unavailable.', true);
      return;
    }
    circleCtx.clearRect(0, 0, cropPreviewCircle.width, cropPreviewCircle.height);
    circleCtx.save();
    circleCtx.beginPath();
    circleCtx.arc(
      cropPreviewCircle.width / 2,
      cropPreviewCircle.height / 2,
      cropPreviewCircle.width / 2,
      0,
      Math.PI * 2
    );
    circleCtx.closePath();
    circleCtx.clip();
    circleCtx.drawImage(sourceImage, x, y, size, size, 0, 0, cropPreviewCircle.width, cropPreviewCircle.height);
    circleCtx.restore();
  }
}

function centerCrop() {
  const side = getImageSide();
  cropState.size = Math.max(1, side);
  cropState.centerX = imageNaturalWidth / 2;
  cropState.centerY = imageNaturalHeight / 2;
  clampCropState();
  syncSizeSliderFromState();
  syncPositionSlidersFromState();
  drawPreview();
}

function resetCropToInitial() {
  if (!sourceImage.src || imageNaturalWidth <= 0 || imageNaturalHeight <= 0) {
    setStatus('Please load an image first.', true);
    return;
  }
  centerCrop();
  setStatus('Crop reset to center.');
}

function assignFileInput(file) {
  if (typeof window.DataTransfer === 'undefined') {
    return false;
  }
  try {
    const dt = new window.DataTransfer();
    dt.items.add(file);
    avatarFile.files = dt.files;
    return true;
  } catch {
    return false;
  }
}

function getFirstImageFile(dataTransferLike) {
  if (!dataTransferLike) {
    return null;
  }
  const files = Array.from(dataTransferLike.files || []);
  const fromFiles = files.find((file) => isImageFile(file));
  if (fromFiles) {
    return fromFiles;
  }
  const items = Array.from(dataTransferLike.items || []);
  for (const item of items) {
    if (item.kind === 'file' && typeof item.type === 'string' && item.type.startsWith('image/')) {
      const file = item.getAsFile();
      if (file) {
        return file;
      }
    }
  }
  return null;
}

function loadImageFile(file, sourceLabel, syncInput = false) {
  if (!isImageFile(file)) {
    setStatus('Only image files are supported.', true);
    return;
  }

  if (syncInput && !assignFileInput(file)) {
    setStatus('Image loaded, but browser blocked syncing to file input. Please re-select manually.', true);
  }

  if (activeObjectUrl) {
    window.URL.revokeObjectURL(activeObjectUrl);
    activeObjectUrl = null;
  }

  const objectUrl = window.URL.createObjectURL(file);
  activeObjectUrl = objectUrl;
  sourceImage.onload = () => {
    imageNaturalWidth = sourceImage.naturalWidth;
    imageNaturalHeight = sourceImage.naturalHeight;
    centerCrop();
    setStatus(`Image loaded (${sourceLabel}): ${imageNaturalWidth}x${imageNaturalHeight}`);
  };
  sourceImage.onerror = () => {
    setStatus('Failed to parse selected image.', true);
  };
  sourceImage.src = objectUrl;
  sourceImage.classList.remove('d-none');
}

async function parseResponseJson(resp) {
  try {
    return await resp.json();
  } catch {
    return {};
  }
}

async function uploadAvatar(event) {
  event.preventDefault();
  const file = avatarFile.files && avatarFile.files[0];
  if (!file) {
    setStatus('Please choose an image file first.', true);
    return;
  }
  if (!isImageFile(file)) {
    setStatus('Only image files are supported.', true);
    return;
  }

  const shouldUpload = window.confirm('确认上传并覆盖当前头像吗？');
  if (!shouldUpload) {
    setStatus('Upload cancelled.');
    return;
  }

  await withButtonLoading(
    uploadBtn,
    '<span class="spinner-border spinner-border-sm me-2"></span>Uploading...',
    async () => {
      setStatus('Uploading...');
      try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('file_type', '1');
        formData.append('mime_type', file.type || 'image/webp');
        formData.append('file_size', String(file.size));
        formData.append('original_name', file.name);
        const cropRect = getCropRectFromState();
        formData.append('crop_x', String(Math.round(cropRect.x)));
        formData.append('crop_y', String(Math.round(cropRect.y)));
        formData.append('crop_size', String(Math.round(cropRect.size)));

        const resp = await fetch(uploadUrl, { method: 'POST', body: formData, credentials: 'same-origin' });
        const payload = await parseResponseJson(resp);
        if (!resp.ok) {
          throw new Error(payload.detail || payload.message || 'Upload failed');
        }

        currentAvatar.src = payload.avatar_url;
        currentMediaId.textContent = payload.avatar_media_id || '-';
        setStatus(payload.duplicate ? 'Uploaded (deduplicated).' : 'Uploaded successfully.');
      } catch (error) {
        setStatus(error instanceof Error ? error.message : 'Upload failed', true);
      }
    }
  );
}

async function clearAvatar() {
  const shouldClear = window.confirm('确认清空当前头像吗？');
  if (!shouldClear) {
    setStatus('Clear cancelled.');
    return;
  }

  await withButtonLoading(
    clearBtn,
    '<span class="spinner-border spinner-border-sm me-2"></span>Clearing...',
    async () => {
      setStatus('Clearing avatar...');
      try {
        const resp = await fetch(clearUrl, { method: 'POST', credentials: 'same-origin' });
        const payload = await parseResponseJson(resp);
        if (!resp.ok) {
          throw new Error(payload.detail || payload.message || 'Clear failed');
        }
        currentAvatar.src = payload.avatar_url;
        currentMediaId.textContent = '-';
        setStatus('Avatar cleared.');
      } catch (error) {
        setStatus(error instanceof Error ? error.message : 'Clear failed', true);
      }
    }
  );
}

function bindDropZone() {
  if (!avatarDropZone) {
    return;
  }

  const activate = (active) => {
    avatarDropZone.classList.toggle('is-dragover', active);
  };

  ['dragenter', 'dragover'].forEach((eventName) => {
    avatarDropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      activate(true);
    });
  });

  ['dragleave', 'dragend'].forEach((eventName) => {
    avatarDropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      activate(false);
    });
  });

  avatarDropZone.addEventListener('drop', (event) => {
    event.preventDefault();
    event.stopPropagation();
    activate(false);
    const file = getFirstImageFile(event.dataTransfer);
    if (!file) {
      setStatus('No image file found in dropped content.', true);
      return;
    }
    loadImageFile(file, 'drag-and-drop', true);
  });
}

function bindPaste() {
  document.addEventListener('paste', (event) => {
    const file = getFirstImageFile(event.clipboardData);
    if (!file) {
      return;
    }
    event.preventDefault();
    loadImageFile(file, 'clipboard', true);
  });
}

function bindInputEvents() {
  avatarFile.addEventListener('change', () => {
    const file = avatarFile.files && avatarFile.files[0];
    if (!file) {
      return;
    }
    loadImageFile(file, 'file picker');
  });

  cropX.addEventListener('input', () => {
    const range = POSITION_SLIDER_MAX - POSITION_SLIDER_MIN;
    const normalizedX = clamp((Number(cropX.value) - POSITION_SLIDER_MIN) / range, 0, 1);
    const maxX = getMaxOffset(cropState.size).x;
    const nextX = normalizedX * maxX;
    cropState.centerX = nextX + cropState.size / 2;
    clampCropState();
    syncPositionSlidersFromState();
    drawPreview();
  });
  cropY.addEventListener('input', () => {
    const range = POSITION_SLIDER_MAX - POSITION_SLIDER_MIN;
    const normalizedY = clamp((Number(cropY.value) - POSITION_SLIDER_MIN) / range, 0, 1);
    const maxY = getMaxOffset(cropState.size).y;
    const nextY = normalizedY * maxY;
    cropState.centerY = nextY + cropState.size / 2;
    clampCropState();
    syncPositionSlidersFromState();
    drawPreview();
  });
  cropSize.addEventListener('input', () => {
    if (imageNaturalWidth <= 0 || imageNaturalHeight <= 0) {
      return;
    }
    cropState.size = sliderValueToSize(cropSize.value);
    clampCropState();
    syncPositionSlidersFromState();
    drawPreview();
  });
  avatarForm.addEventListener('submit', uploadAvatar);
  resetCropBtn?.addEventListener('click', resetCropToInitial);
  clearBtn.addEventListener('click', clearAvatar);
}

function init() {
  bindInputEvents();
  bindDropZone();
  bindPaste();
}

init();
