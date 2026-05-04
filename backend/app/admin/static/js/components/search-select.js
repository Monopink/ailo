function parseJsonResponse(response) {
  return response.json().catch(() => ({}));
}

function normalizeItems(data) {
  if (!data || !Array.isArray(data.items)) {
    return [];
  }
  return data.items
    .map((item) => {
      const id = item && item.id != null ? String(item.id) : '';
      const text = item && item.text != null ? String(item.text) : '';
      if (id === '' || text === '') {
        return null;
      }
      return {
        id,
        text,
        meta: item.meta && typeof item.meta === 'object' ? item.meta : {},
      };
    })
    .filter((item) => item !== null);
}

function destroySearchSelect(element) {
  if (!element || typeof window.jQuery === 'undefined') {
    return;
  }
  const $ = window.jQuery;
  const $element = $(element);
  if (typeof $element.select2 !== 'function') {
    return;
  }
  if ($element.data('select2')) {
    $element.off('.adminSearchSelect');
    $element.select2('destroy');
  }
}

function initSearchSelect({
  element,
  searchUrl,
  items = null,
  placeholder = '',
  minimumInputLength = 1,
  limit = 20,
  dropdownParent = null,
  allowClear = true,
  language = {},
  onSelect = null,
  onClear = null,
}) {
  if (!element || typeof window.jQuery === 'undefined') {
    return null;
  }
  const $ = window.jQuery;
  const $element = $(element);
  if (typeof $element.select2 !== 'function') {
    return null;
  }

  destroySearchSelect(element);

  const normalizedItems = Array.isArray(items) ? normalizeItems({ items }) : null;
  const select2Options = {
    width: '100%',
    placeholder,
    allowClear,
    minimumInputLength: searchUrl ? minimumInputLength : 0,
    dropdownParent: dropdownParent ? $(dropdownParent) : undefined,
    language: {
      inputTooShort: () => language.inputTooShort || '',
      noResults: () => language.noResults || '',
      searching: () => language.searching || '',
      errorLoading: () => language.errorLoading || '',
    },
  };

  if (searchUrl) {
    select2Options.ajax = {
      transport: function (params, success, failure) {
        const term = String((params.data && params.data.term) || '').trim();
        const page = Number.parseInt(String((params.data && params.data.page) || '1'), 10) || 1;
        if (minimumInputLength > 0 && term.length < minimumInputLength) {
          success({ items: [], has_more: false });
          return null;
        }
        const url = `${searchUrl}?q=${encodeURIComponent(term)}&limit=${limit}&page=${page}`;
        fetch(url, { credentials: 'same-origin' })
          .then(async (response) => {
            const data = await parseJsonResponse(response);
            if (!response.ok) {
              const detail = typeof data.detail === 'string' ? data.detail : 'Search request failed';
              throw new Error(detail);
            }
            return data;
          })
          .then((data) => success(data))
          .catch((error) => failure(error));
        return null;
      },
      processResults: function (data) {
        const normalized = normalizeItems(data);
        const hasMore = !!(data && data.has_more);
        return {
          results: normalized,
          pagination: { more: hasMore },
        };
      },
    };
  } else if (normalizedItems !== null) {
    select2Options.data = normalizedItems;
  }

  $element.select2(select2Options);

  if (typeof onSelect === 'function') {
    $element.on('select2:select.adminSearchSelect', (event) => {
      onSelect(event.params?.data || null);
    });
  }
  if (typeof onClear === 'function') {
    $element.on('select2:clear.adminSearchSelect', () => {
      onClear();
    });
  }

  return $element;
}

window.ailoSearchSelect = {
  initSearchSelect,
  destroySearchSelect,
};
