const hasDataTable = (tableSelector) => {
  if (
    typeof window === 'undefined' ||
    !window.jQuery ||
    !window.jQuery.fn ||
    !window.jQuery.fn.dataTable ||
    typeof window.jQuery.fn.dataTable.isDataTable !== 'function'
  ) {
    return false;
  }
  return window.jQuery.fn.dataTable.isDataTable(tableSelector);
};

const resolveDataTable = (tableSelector) => {
  if (!hasDataTable(tableSelector)) {
    return null;
  }
  return window.jQuery(tableSelector).DataTable();
};

export const mountRowAction = ({ tableSelector = '#dt', actionClassName, isVisible, buildButton, onClick }) => {
  if (
    typeof actionClassName !== 'string' ||
    actionClassName.trim() === '' ||
    typeof isVisible !== 'function' ||
    typeof buildButton !== 'function' ||
    typeof onClick !== 'function'
  ) {
    return;
  }

  const normalizedClassName = actionClassName.trim();
  const cleanupSelector = `.${normalizedClassName}`;

  const render = () => {
    const dataTable = resolveDataTable(tableSelector);
    if (dataTable === null) {
      return;
    }
    dataTable.rows({ page: 'current' }).every(function () {
      const rowData = this.data();
      const rowNode = this.node();
      if (!(rowNode instanceof HTMLTableRowElement)) {
        return;
      }

      const oldButton = rowNode.querySelector(cleanupSelector);
      if (oldButton instanceof HTMLElement) {
        oldButton.remove();
      }

      if (!isVisible(rowData)) {
        return;
      }

      const viewAction = rowNode.querySelector('[data-name="view"]');
      if (!(viewAction instanceof HTMLElement) || !(viewAction.parentElement instanceof HTMLElement)) {
        return;
      }

      const button = buildButton(viewAction, rowData);
      if (!(button instanceof HTMLElement)) {
        return;
      }
      button.classList.add(normalizedClassName);
      button.addEventListener('click', (event) => onClick(rowData, event));
      viewAction.parentElement.appendChild(button);
    });
  };

  if (typeof window === 'undefined' || !window.jQuery) {
    return;
  }
  window.jQuery(tableSelector).on('draw.dt', render);
  render();
};
