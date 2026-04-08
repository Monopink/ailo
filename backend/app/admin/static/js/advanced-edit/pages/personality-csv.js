export const personalityCsvMethods = {
  csvEscape(value) {
    const str = value === null || value === undefined ? '' : String(value);
    if (/[",\n\r]/.test(str)) {
      return `"${str.replaceAll('"', '""')}"`;
    }
    return str;
  },

  buildPlaceholdersCsv() {
    const header = ['placeholder_key', 'display_name', 'description', 'example_value', 'is_required'];
    const lines = [header.join(',')];
    this.state.placeholders.forEach((p) => {
      lines.push(
        [
          this.csvEscape((p.placeholder_key || '').trim()),
          this.csvEscape(p.display_name || ''),
          this.csvEscape(p.description || ''),
          this.csvEscape(p.example_value || ''),
          this.csvEscape(p.is_required ? 'true' : 'false'),
        ].join(',')
      );
    });
    return lines.join('\n');
  },

  async copyPlaceholdersCsvToClipboard() {
    const csv = this.buildPlaceholdersCsv();
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(csv);
      } else {
        const ta = document.createElement('textarea');
        ta.value = csv;
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        document.execCommand('copy');
        ta.remove();
      }
      alert('已复制到剪贴板');
    } catch (e) {
      alert('复制失败: ' + (e?.message || String(e)));
    }
  },

  showPlaceholderCsvImportModal() {
    this.resetPlaceholderCsvImportPreview();
    const textarea = document.getElementById('placeholder-csv-input');
    if (textarea) textarea.value = '';
    this.state.placeholderCsvImportModal.show();
  },

  resetPlaceholderCsvImportPreview() {
    this.state.placeholderCsvImportParsed = null;
    this.state.placeholderCsvImportSummary = null;
    const preview = document.getElementById('placeholder-csv-preview');
    if (preview) preview.innerHTML = '';
    const btn = document.getElementById('btn-confirm-placeholder-csv-import');
    if (btn) btn.disabled = true;
  },

  parseCsvText(text) {
    const rows = [];
    let row = [];
    let field = '';
    let inQuotes = false;

    const pushField = () => {
      row.push(field);
      field = '';
    };
    const pushRow = () => {
      // Skip completely empty lines
      if (row.some((v) => (v || '').trim() !== '')) {
        rows.push(row);
      }
      row = [];
    };

    const input = (text || '').replaceAll('\r\n', '\n').replaceAll('\r', '\n');
    for (let i = 0; i < input.length; i += 1) {
      const c = input[i];
      if (inQuotes) {
        if (c === '"') {
          const next = input[i + 1];
          if (next === '"') {
            field += '"';
            i += 1;
          } else {
            inQuotes = false;
          }
        } else {
          field += c;
        }
        continue;
      }

      if (c === '"') {
        inQuotes = true;
        continue;
      }
      if (c === ',') {
        pushField();
        continue;
      }
      if (c === '\n') {
        pushField();
        pushRow();
        continue;
      }
      field += c;
    }

    if (inQuotes) {
      throw new Error('CSV 解析失败：存在未闭合的引号');
    }
    // last line
    pushField();
    pushRow();

    return rows;
  },

  parsePlaceholderCsvImport() {
    const preview = document.getElementById('placeholder-csv-preview');
    const btn = document.getElementById('btn-confirm-placeholder-csv-import');
    if (btn) btn.disabled = true;
    if (preview) preview.innerHTML = '';

    const input = document.getElementById('placeholder-csv-input')?.value || '';
    if (!input.trim()) {
      if (preview) preview.innerHTML = '<div class="alert alert-warning mb-0">请输入 CSV 内容</div>';
      return;
    }

    let rows;
    try {
      rows = this.parseCsvText(input);
    } catch (e) {
      if (preview)
        preview.innerHTML = `<div class="alert alert-danger mb-0">${this.escapeHtml(e?.message || String(e))}</div>`;
      return;
    }

    if (!Array.isArray(rows) || rows.length < 2) {
      if (preview)
        preview.innerHTML = '<div class="alert alert-warning mb-0">CSV 内容不足：至少需要表头 + 1 行数据</div>';
      return;
    }

    const header = rows[0].map((h) => (h || '').trim());
    const requiredCols = ['placeholder_key', 'display_name', 'description', 'example_value', 'is_required'];
    const colIndex = {};
    requiredCols.forEach((col) => {
      colIndex[col] = header.indexOf(col);
    });
    const missing = requiredCols.filter((col) => colIndex[col] === -1);
    if (missing.length > 0) {
      if (preview)
        preview.innerHTML = `<div class="alert alert-danger mb-0">CSV 表头缺少列：${missing
          .map((c) => `<code>${this.escapeHtml(c)}</code>`)
          .join('、')}</div>`;
      return;
    }

    const parsed = [];
    const seenKeys = new Set();
    const errors = [];
    for (let i = 1; i < rows.length; i += 1) {
      const r = rows[i];
      const key = (r[colIndex.placeholder_key] || '').trim();
      const displayName = (r[colIndex.display_name] || '').trim();
      const description = (r[colIndex.description] || '').trim();
      const exampleValue = (r[colIndex.example_value] || '').trim();
      const requiredRaw = (r[colIndex.is_required] || '').trim().toLowerCase();

      if (!key) {
        errors.push(`第 ${i + 1} 行：placeholder_key 不能为空`);
        continue;
      }
      if (!this.isValidPlaceholderKey(key)) {
        errors.push(`第 ${i + 1} 行：placeholder_key 不合法（${key}）`);
        continue;
      }
      if (seenKeys.has(key)) {
        errors.push(`导入内容存在重复 placeholder_key：${key}`);
        continue;
      }
      seenKeys.add(key);

      let isRequired;
      if (requiredRaw === 'true' || requiredRaw === '1') {
        isRequired = true;
      } else if (requiredRaw === 'false' || requiredRaw === '0') {
        isRequired = false;
      } else {
        errors.push(`第 ${i + 1} 行：is_required 必须为 true/false/1/0（当前：${requiredRaw || '(空)'}）`);
        continue;
      }

      parsed.push({
        placeholder_key: key,
        display_name: displayName,
        description,
        example_value: exampleValue,
        is_required: isRequired,
      });
    }

    if (errors.length > 0) {
      if (preview) {
        preview.innerHTML = `<div class="alert alert-danger"><strong>解析失败</strong><ul class="mb-0">${errors
          .map((e) => `<li>${this.escapeHtml(e)}</li>`)
          .join('')}</ul></div>`;
      }
      return;
    }

    const existingByKey = new Map(
      this.state.placeholders.map((p) => [(p.placeholder_key || '').trim(), p]).filter(([k]) => !!k)
    );
    const overwriteKeys = parsed.filter((p) => existingByKey.has(p.placeholder_key)).map((p) => p.placeholder_key);
    const createCount = parsed.length - overwriteKeys.length;

    const tableRows = parsed.map((p) => {
      const overwrite = existingByKey.has(p.placeholder_key);
      const cls = overwrite ? 'table-warning' : '';
      return `
        <tr class="${cls}">
          <td><code>${this.escapeHtml(p.placeholder_key)}</code></td>
          <td>${this.escapeHtml(p.display_name || '-')}</td>
          <td>${this.escapeHtml(p.description || '-')}</td>
          <td>${this.escapeHtml(p.example_value || '-')}</td>
          <td>${p.is_required ? '<i class="fas fa-check text-success"></i>' : '-'}</td>
          <td>${
            overwrite
              ? '<span class="badge text-bg-warning">覆盖</span>'
              : '<span class="badge text-bg-success">新增</span>'
          }</td>
        </tr>
      `;
    });

    if (preview) {
      const overwriteTip =
        overwriteKeys.length > 0
          ? `<div class="alert alert-warning mb-3">检测到 <strong>${overwriteKeys.length}</strong> 个与当前已存在 Key 重复的条目，导入后将覆盖现有内容。</div>`
          : '';
      preview.innerHTML = `
        ${overwriteTip}
        <div class="alert alert-info mb-3">本次导入：新增 <strong>${createCount}</strong> 条，覆盖 <strong>${
          overwriteKeys.length
        }</strong> 条。</div>
        <div class="table-responsive">
          <table class="table align-middle">
            <thead><tr><th>Key</th><th>Display Name</th><th>Description</th><th>Example Value</th><th>Required</th><th>Action</th></tr></thead>
            <tbody>${tableRows.join('')}</tbody>
          </table>
        </div>
      `;
    }

    this.state.placeholderCsvImportParsed = parsed;
    this.state.placeholderCsvImportSummary = { overwriteKeys, createCount };
    if (btn) btn.disabled = false;
  },

  async confirmPlaceholderCsvImport() {
    const parsed = this.state.placeholderCsvImportParsed;
    const summary = this.state.placeholderCsvImportSummary;
    if (!Array.isArray(parsed) || !summary) {
      return;
    }

    const overwriteKeys = summary.overwriteKeys || [];
    const createCount = summary.createCount || 0;
    const ok = await this.confirmAction({
      title: '确认导入 Placeholder',
      message:
        `确认导入 CSV 内容吗？<br>新增 <strong>${createCount}</strong> 条，覆盖 <strong>${overwriteKeys.length}</strong> 条。` +
        (overwriteKeys.length > 0 ? `<br><span class="text-warning">重复 Key 将被覆盖</span>` : ''),
      confirmText: '导入',
      cancelText: '取消',
      confirmButtonClass: 'btn btn-primary',
    });
    if (!ok) return;

    const byKey = new Map(
      this.state.placeholders.map((p) => [(p.placeholder_key || '').trim(), p]).filter(([k]) => !!k)
    );

    parsed.forEach((row) => {
      const existing = byKey.get(row.placeholder_key);
      if (existing) {
        existing.display_name = row.display_name || '';
        existing.description = row.description || '';
        existing.example_value = row.example_value || '';
        existing.is_required = !!row.is_required;
        return;
      }
      this.state.placeholders.push(
        this.normalizePlaceholderRecord({
          id: null,
          placeholder_key: row.placeholder_key,
          display_name: row.display_name || '',
          description: row.description || '',
          example_value: row.example_value || '',
          is_required: !!row.is_required,
        })
      );
    });

    this.renderCustomPlaceholders();
    this.renderPlaceholdersList();
    this.validatePrompt();
    this.applyPlaceholderKeyValidationStyles();
    this.resetPlaceholderCsvImportPreview();
    this.state.placeholderCsvImportModal.hide();
    alert('导入成功');
  },
};
