const fs = require('node:fs');
const { execFileSync } = require('node:child_process');

function tryReadGitShortSha(rootDir) {
  try {
    const output = execFileSync('git', ['rev-parse', '--short', 'HEAD'], {
      cwd: rootDir,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    });
    return typeof output === 'string' ? output.trim() : '';
  } catch {
    return '';
  }
}

function buildBuildInfoSource({ id, builtAt }) {
  return `export const BUILD_INFO = {\n  id: '${id}',\n  builtAt: '${builtAt}',\n};\n`;
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
    const content = buildBuildInfoSource({ id, builtAt });

    const changed = writeIfChanged(generatedTsPath, content, ctx.dryRun);
    if (changed) {
      console.log(`[devtools] Updated ${generatedTsPath}`);
    }
  },
};
