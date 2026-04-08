export const V1_ALGORITHM = 2;

export function getSpecsForAlgorithm(specsByAlgorithm, algorithm) {
  return specsByAlgorithm[String(algorithm)] || [];
}

export function collectAlgorithmParams(specs, dimensionKey, dataSource) {
  const params = {};
  const missing = [];
  specs.forEach((spec) => {
    const fieldName = `${spec.name}_${dimensionKey}`;
    const raw = dataSource.get(fieldName);
    if (raw === null || raw.toString().trim() === '') {
      missing.push(spec.label);
      return;
    }
    const numeric = spec.input_type === 'integer' ? parseInt(raw, 10) : parseFloat(raw);
    if (Number.isNaN(numeric)) {
      missing.push(spec.label);
      return;
    }
    params[spec.name] = numeric;
  });
  return { params, missing };
}

export function bindAlgorithmParamsVisibility(options) {
  const { selectSelector, resolveParamsContainer, isActiveAlgorithm } = options;
  document.querySelectorAll(selectSelector).forEach((select) => {
    const paramsDiv = resolveParamsContainer(select);
    if (!paramsDiv) {
      return;
    }
    const toggleParams = () => {
      if (isActiveAlgorithm(select.value)) {
        paramsDiv.style.display = 'block';
        paramsDiv.querySelectorAll('input[data-required="true"]').forEach((input) => {
          input.required = true;
        });
      } else {
        paramsDiv.style.display = 'none';
        paramsDiv.querySelectorAll('input[required]').forEach((input) => {
          input.dataset.required = 'true';
          input.required = false;
        });
      }
    };
    toggleParams();
    select.addEventListener('change', toggleParams);
  });
}
