const fs = require('node:fs');
const path = require('node:path');

const GENERATED_FILE_PATH = ['utils', 'config.local.generated.ts'];
const LOCAL_SOURCE_PATH = ['utils', 'config.local.ts'];
const LOCAL_TEMPLATE_PATH = ['utils', 'config.local.template.ts'];

function readTextIfExists(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf8');
  } catch {
    return '';
  }
}

function writeIfChanged(filePath, content, dryRun) {
  const current = readTextIfExists(filePath);
  if (current === content) {
    return false;
  }
  if (!dryRun) {
    fs.writeFileSync(filePath, content, 'utf8');
  }
  return true;
}

function extractLocalConfigObjectLiteral(source) {
  const anchorPattern =
    /export\s+const\s+LOCAL_CONFIG_OVERRIDE(?:\s*:\s*LocalConfigOverride)?\s*=\s*/m;
  const anchorMatch = anchorPattern.exec(source);
  if (!anchorMatch || anchorMatch.index === undefined) {
    throw new Error(
      '[devtools] Invalid local config file: expected `export const LOCAL_CONFIG_OVERRIDE = {...};`'
    );
  }

  const startIndex = anchorMatch.index + anchorMatch[0].length;
  const braceStart = source.indexOf('{', startIndex);
  if (braceStart < 0) {
    throw new Error('[devtools] Invalid local config file: object literal start not found');
  }

  let depth = 0;
  for (let index = braceStart; index < source.length; index += 1) {
    const char = source[index];
    if (char === '{') {
      depth += 1;
      continue;
    }
    if (char === '}') {
      depth -= 1;
      if (depth === 0) {
        return source.slice(braceStart, index + 1).trim();
      }
    }
  }

  throw new Error('[devtools] Invalid local config file: object literal is not balanced');
}

function buildGeneratedSourceFromObjectLiteral(objectLiteralSource) {
  return `import type { LocalConfigOverride } from './config';\n\nexport const LOCAL_CONFIG_OVERRIDE: LocalConfigOverride = ${objectLiteralSource};\n\nexport default LOCAL_CONFIG_OVERRIDE;\n`;
}

function buildEmptyGeneratedSource() {
  return `import type { LocalConfigOverride } from './config';\n\nexport const LOCAL_CONFIG_OVERRIDE: LocalConfigOverride = {};\n\nexport default LOCAL_CONFIG_OVERRIDE;\n`;
}

module.exports = {
  name: 'generate-local-config-override',
  async run(ctx) {
    const generatedFilePath = ctx.resolvePath(...GENERATED_FILE_PATH);
    const localSourcePath = ctx.resolvePath(...LOCAL_SOURCE_PATH);
    const localTemplatePath = ctx.resolvePath(...LOCAL_TEMPLATE_PATH);

    const localSource = readTextIfExists(localSourcePath);
    let generatedSource = '';
    const shouldUseLocalSource = ctx.hook === 'compile';

    if (shouldUseLocalSource && localSource.trim() !== '') {
      const objectLiteral = extractLocalConfigObjectLiteral(localSource);
      generatedSource = buildGeneratedSourceFromObjectLiteral(objectLiteral);
    } else {
      generatedSource = buildEmptyGeneratedSource();
      const templateExists = readTextIfExists(localTemplatePath).trim() !== '';
      if (!templateExists) {
        console.warn('[devtools] Missing utils/config.local.template.ts template file');
      }
    }

    const changed = writeIfChanged(generatedFilePath, generatedSource, ctx.dryRun);
    if (changed) {
      console.log(`[devtools] Updated ${generatedFilePath}`);
    }
  },
};
