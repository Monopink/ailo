import { escapeHtml, safeText } from './formatters.js';

export function renderUserIdCell(userId, isUserType) {
  const normalizedId = safeText(userId, '');
  if (!normalizedId) return '-';
  const escapedId = escapeHtml(normalizedId);
  if (!isUserType) return escapedId;
  return `<button class="btn btn-link p-0 align-baseline action-open-user" data-user-id="${escapedId}" type="button">${escapedId}</button>`;
}

export function refreshFilterOptions(state, aiTypeSelect, failureSelect) {
  if (!aiTypeSelect || !failureSelect) return;

  const currentType = aiTypeSelect.value;
  const currentFailure = failureSelect.value;
  aiTypeSelect.innerHTML = '<option value="">全部</option>';
  failureSelect.innerHTML = '<option value="">全部</option>';

  [...state.aiTypeOptions.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .forEach(([id, label]) => {
      aiTypeSelect.insertAdjacentHTML(
        'beforeend',
        `<option value="${escapeHtml(id)}">${escapeHtml(id)} · ${escapeHtml(label)}</option>`
      );
    });

  [...state.failureOptions.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .forEach(([code, label]) => {
      failureSelect.insertAdjacentHTML(
        'beforeend',
        `<option value="${escapeHtml(code)}">${escapeHtml(code)} · ${escapeHtml(label)}</option>`
      );
    });

  if (currentType && !state.aiTypeOptions.has(currentType)) {
    aiTypeSelect.insertAdjacentHTML(
      'beforeend',
      `<option value="${escapeHtml(currentType)}">${escapeHtml(currentType)} · ${escapeHtml(currentType)}</option>`
    );
  }
  if (currentFailure && !state.failureOptions.has(currentFailure)) {
    failureSelect.insertAdjacentHTML(
      'beforeend',
      `<option value="${escapeHtml(currentFailure)}">${escapeHtml(currentFailure)} · ${escapeHtml(
        currentFailure
      )}</option>`
    );
  }

  aiTypeSelect.value = currentType;
  failureSelect.value = currentFailure;
}
