const fs = require('node:fs');
const path = require('node:path');

const ROOT = process.cwd();
const STALE_THRESHOLD_MS = 1000;
const EXCLUDED_DIRS = new Set([
  'node_modules',
  'miniprogram_npm',
  'deleted',
  'test',
  'minitest',
  '.git',
  'dist',
]);

function walkFiles(dirPath, files = []) {
  const entries = fs.readdirSync(dirPath, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name.startsWith('.')) {
      continue;
    }
    if (entry.isDirectory()) {
      if (EXCLUDED_DIRS.has(entry.name)) {
        continue;
      }
      walkFiles(path.join(dirPath, entry.name), files);
      continue;
    }
    if (entry.isFile()) {
      files.push(path.join(dirPath, entry.name));
    }
  }
  return files;
}

function toDisplayPath(filePath) {
  return path.relative(ROOT, filePath).split(path.sep).join('/');
}

function main() {
  const allFiles = walkFiles(ROOT);
  const tsFiles = allFiles.filter((filePath) => filePath.endsWith('.ts') && !filePath.endsWith('.d.ts'));

  const problems = [];

  for (const tsPath of tsFiles) {
    const jsPath = tsPath.slice(0, -3) + '.js';
    const tsStat = fs.statSync(tsPath);

    if (!fs.existsSync(jsPath)) {
      problems.push({
        type: 'missing',
        tsPath,
        jsPath,
        deltaMs: Number.NaN,
      });
      continue;
    }

    const jsStat = fs.statSync(jsPath);
    const deltaMs = tsStat.mtimeMs - jsStat.mtimeMs;
    if (deltaMs > STALE_THRESHOLD_MS) {
      problems.push({
        type: 'stale',
        tsPath,
        jsPath,
        deltaMs,
      });
    }
  }

  if (problems.length === 0) {
    console.log(
      `Runtime JS sync check passed: ${tsFiles.length} TS files have up-to-date JS counterparts.`
    );
    return;
  }

  const staleCount = problems.filter((item) => item.type === 'stale').length;
  const missingCount = problems.filter((item) => item.type === 'missing').length;
  console.error(
    `Runtime JS sync check failed: ${problems.length} issue(s) found (${staleCount} stale, ${missingCount} missing).`
  );

  const sorted = problems
    .slice()
    .sort((a, b) => {
      const aDelta = Number.isFinite(a.deltaMs) ? a.deltaMs : Number.POSITIVE_INFINITY;
      const bDelta = Number.isFinite(b.deltaMs) ? b.deltaMs : Number.POSITIVE_INFINITY;
      return bDelta - aDelta;
    })
    .slice(0, 30);

  for (const problem of sorted) {
    if (problem.type === 'missing') {
      console.error(`[missing] ${toDisplayPath(problem.tsPath)} -> ${toDisplayPath(problem.jsPath)}`);
      continue;
    }
    const deltaSeconds = (problem.deltaMs / 1000).toFixed(1);
    console.error(`[stale +${deltaSeconds}s] ${toDisplayPath(problem.tsPath)}`);
  }

  process.exit(1);
}

main();
