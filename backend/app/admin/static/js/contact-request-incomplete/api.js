export async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = '请求失败';
    try {
      const payload = await response.json();
      const rawDetail = payload?.detail;
      if (typeof rawDetail === 'string') {
        detail = rawDetail;
      } else if (rawDetail && typeof rawDetail === 'object') {
        if (typeof rawDetail.message === 'string' && rawDetail.message) {
          detail = rawDetail.message;
        } else if (typeof rawDetail.code === 'string' && rawDetail.code) {
          detail = rawDetail.code;
        }
      }
    } catch {}
    throw new Error(typeof detail === 'string' ? detail : '请求失败');
  }
  return response.json();
}

export function buildListQuery({ aiTypeId, failureCode, status, updatedFrom, updatedTo, page, pageSize }) {
  const normalizedPage = Number.isFinite(page) && page > 0 ? Math.floor(page) : 1;
  const normalizedPageSize = Number.isFinite(pageSize) && pageSize > 0 ? Math.floor(pageSize) : 20;
  const offset = (normalizedPage - 1) * normalizedPageSize;
  const query = new URLSearchParams({
    limit: String(normalizedPageSize),
    offset: String(offset),
  });
  if (aiTypeId) query.set('ai_type_id', aiTypeId.trim());
  if (failureCode) query.set('failure_code', failureCode.trim());
  if (status) query.set('status', status.trim());
  if (updatedFrom) query.set('updated_from', new Date(updatedFrom).toISOString());
  if (updatedTo) query.set('updated_to', new Date(updatedTo).toISOString());
  return query.toString();
}

export function fetchIncompleteOverview(apiBase) {
  return fetchJson(`${apiBase}/incomplete/overview`);
}

export function fetchIncompleteList(apiBase, queryString) {
  return fetchJson(`${apiBase}/incomplete?${queryString}`);
}

export function fetchRetryPrecheck(apiBase, requestId, body) {
  return fetchJson(`${apiBase}/${encodeURIComponent(requestId)}/retry-precheck`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export function executeRetryRequest(apiBase, requestId, body) {
  return fetchJson(`${apiBase}/${encodeURIComponent(requestId)}/retry`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export function ignoreIncompleteRequest(apiBase, requestId) {
  return fetchJson(`${apiBase}/${encodeURIComponent(requestId)}/ignore`, {
    method: 'POST',
  });
}
