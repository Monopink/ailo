const fs = require('node:fs');
const path = require('node:path');

const CONFIG_FILE_PATH = path.join(process.cwd(), 'utils', 'config.ts');

const BLOCKED_HOST_PATTERNS = [
  /localhost/i,
  /127\.0\.0\.1/,
  /ailo-dev-1335295169\.cos\.ap-shanghai\.myqcloud\.com/i,
];

function readConfigSource() {
  return fs.readFileSync(CONFIG_FILE_PATH, 'utf8');
}

function extractObjectBlock(source, objectName) {
  const pattern = new RegExp(
    `const\\s+${objectName}\\s*=\\s*\\{([\\s\\S]*?)\\}\\s+as\\s+const;`,
    'm'
  );
  const match = source.match(pattern);
  if (!match || typeof match[1] !== 'string') {
    throw new Error(`Unable to parse object "${objectName}" from utils/config.ts`);
  }
  return match[1];
}

function extractStringField(objectBlock, fieldName, objectName) {
  const pattern = new RegExp(`${fieldName}:\\s*'([^']*)'`, 'm');
  const match = objectBlock.match(pattern);
  if (!match || typeof match[1] !== 'string') {
    throw new Error(`Missing string field "${objectName}.${fieldName}" in utils/config.ts`);
  }
  return match[1].trim();
}

function hasBlockedHost(value) {
  return BLOCKED_HOST_PATTERNS.some((pattern) => pattern.test(value));
}

function ensureFieldAbsent(objectBlock, fieldName, objectName) {
  const pattern = new RegExp(`\\b${fieldName}\\s*:`, 'm');
  if (pattern.test(objectBlock)) {
    throw new Error(
      `Upload config safety check failed: "${objectName}.${fieldName}" must not be defined`
    );
  }
}

function main() {
  const source = readConfigSource();

  const apiBaseUrlsBlock = extractObjectBlock(source, 'API_BASE_URLS');
  const assetCosBaseUrlsBlock = extractObjectBlock(source, 'ASSET_COS_BASE_URLS');
  ensureFieldAbsent(assetCosBaseUrlsBlock, 'develop', 'ASSET_COS_BASE_URLS');

  const checks = [
    {
      key: 'API_BASE_URLS.trial',
      value: extractStringField(apiBaseUrlsBlock, 'trial', 'API_BASE_URLS'),
    },
    {
      key: 'API_BASE_URLS.release',
      value: extractStringField(apiBaseUrlsBlock, 'release', 'API_BASE_URLS'),
    },
    {
      key: 'ASSET_COS_BASE_URLS.trial',
      value: extractStringField(assetCosBaseUrlsBlock, 'trial', 'ASSET_COS_BASE_URLS'),
    },
    {
      key: 'ASSET_COS_BASE_URLS.release',
      value: extractStringField(assetCosBaseUrlsBlock, 'release', 'ASSET_COS_BASE_URLS'),
    },
  ];

  const violations = checks.filter((item) => hasBlockedHost(item.value));
  if (violations.length > 0) {
    const message = violations.map((item) => `${item.key}=${item.value}`).join(', ');
    throw new Error(
      `Upload config safety check failed: non-develop config contains blocked host(s): ${message}`
    );
  }

  console.log('Upload config safety check passed.');
}

try {
  main();
} catch (error) {
  const message = error instanceof Error ? error.message : 'Unknown upload config safety error';
  console.error(message);
  process.exit(1);
}
