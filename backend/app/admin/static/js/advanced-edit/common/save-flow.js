export async function withButtonLoading(submitButton, loadingHtml, task) {
  const originalHtml = submitButton.innerHTML;
  submitButton.disabled = true;
  submitButton.innerHTML = loadingHtml;
  try {
    return await task();
  } finally {
    submitButton.disabled = false;
    submitButton.innerHTML = originalHtml;
  }
}

export async function postJson(url, method, payload) {
  const response = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  let data = null;
  try {
    data = await response.json();
  } catch (error) {
    data = null;
  }
  return {
    ok: response.ok,
    data,
  };
}
