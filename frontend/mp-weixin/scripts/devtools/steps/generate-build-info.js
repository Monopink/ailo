const fs = require('node:fs');
const path = require('node:path');

function readTextIfExists(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf8').trim();
  } catch {
    return '';
  }
}

function resolveGitDirectory(startDir) {
  let currentDir = path.resolve(startDir);
  while (true) {
    const gitPath = path.join(currentDir, '.git');
    if (fs.existsSync(gitPath)) {
      const stats = fs.statSync(gitPath);
      if (stats.isDirectory()) {
        return gitPath;
      }
      if (stats.isFile()) {
        const marker = readTextIfExists(gitPath);
        const match = marker.match(/^gitdir:\s*(.+)$/i);
        if (match && match[1]) {
          return path.resolve(currentDir, match[1].trim());
        }
      }
    }

    const parentDir = path.dirname(currentDir);
    if (parentDir === currentDir) {
      return '';
    }
    currentDir = parentDir;
  }
}

function resolveShaFromPackedRefs(gitDir, refName) {
  const packedRefsPath = path.join(gitDir, 'packed-refs');
  const packedRefs = readTextIfExists(packedRefsPath);
  if (packedRefs === '') {
    return '';
  }
  const refLine = packedRefs
    .split('\n')
    .find((line) => line.endsWith(` ${refName}`) && !line.startsWith('#') && !line.startsWith('^'));
  if (!refLine) {
    return '';
  }
  const [sha] = refLine.split(' ');
  return typeof sha === 'string' ? sha.trim() : '';
}

function toShortSha(fullSha) {
  if (typeof fullSha !== 'string') {
    return '';
  }
  const normalized = fullSha.trim();
  if (normalized.length < 7) {
    return normalized;
  }
  return normalized.slice(0, 7);
}

function tryReadGitShortSha(rootDir) {
  try {
    const gitDir = resolveGitDirectory(rootDir);
    if (gitDir === '') {
      return '';
    }

    const headContent = readTextIfExists(path.join(gitDir, 'HEAD'));
    if (headContent === '') {
      return '';
    }
    if (!headContent.startsWith('ref:')) {
      return toShortSha(headContent);
    }

    const refName = headContent.slice(4).trim();
    const refPath = path.join(gitDir, refName.split('/').join(path.sep));
    const refSha = readTextIfExists(refPath);
    if (refSha !== '') {
      return toShortSha(refSha);
    }

    const packedSha = resolveShaFromPackedRefs(gitDir, refName);
    return toShortSha(packedSha);
  } catch {
    return '';
  }
}

function readPackageVersion(rootDir) {
  try {
    const packageJsonPath = path.join(rootDir, 'package.json');
    const raw = fs.readFileSync(packageJsonPath, 'utf8');
    const parsed = JSON.parse(raw);
    const version = typeof parsed.version === 'string' ? parsed.version.trim() : '';
    return version;
  } catch {
    return '';
  }
}

function buildBuildInfoSource({ id, builtAt, appVersion }) {
  return `export const BUILD_INFO = {\n  id: '${id}',\n  builtAt: '${builtAt}',\n  appVersion: '${appVersion}',\n};\n`;
}

function readFileOrEmpty(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf8');
  } catch {
    return '';
  }
}

function writeIfChanged(filePath, content, dryRun) {
  const current = readFileOrEmpty(filePath);
  if (current === content) {
    return false;
  }
  if (!dryRun) {
    fs.writeFileSync(filePath, content, 'utf8');
  }
  return true;
}

module.exports = {
  name: 'generate-build-info',
  async run(ctx) {
    const generatedTsPath = ctx.resolvePath('utils', 'build-info.generated.ts');
    const id = tryReadGitShortSha(ctx.rootDir);
    const builtAt = new Date().toISOString();
    const appVersion = readPackageVersion(ctx.rootDir);
    ctx.buildInfo = { id, builtAt, appVersion };
    const content = buildBuildInfoSource({ id, builtAt, appVersion });

    const changed = writeIfChanged(generatedTsPath, content, ctx.dryRun);
    if (changed) {
      console.log(`[devtools] Updated ${generatedTsPath}`);
    }
  },
};
