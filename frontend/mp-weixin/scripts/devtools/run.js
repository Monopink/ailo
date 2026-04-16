const path = require('node:path');

const { runHook } = require('./runner');

function parseArgs(argv) {
  const positional = [];
  const flags = new Set();

  for (const arg of argv) {
    if (arg.startsWith('--')) {
      flags.add(arg);
      continue;
    }
    positional.push(arg);
  }

  return { positional, flags };
}

function printHelp() {
  console.log('Usage: node ./scripts/devtools/run.js <compile|preview|upload> [--dry-run]');
}

async function main() {
  const { positional, flags } = parseArgs(process.argv.slice(2));
  const hook = positional[0] ?? 'compile';

  if (hook === '-h' || hook === '--help') {
    printHelp();
    return;
  }

  const rootDir = process.cwd();
  const ctx = {
    rootDir,
    dryRun: flags.has('--dry-run'),
    resolvePath: (...segments) => path.join(rootDir, ...segments),
  };

  await runHook(hook, ctx);
}

main().catch((error) => {
  console.error('[devtools] Hook runner failed:', error);
  process.exit(1);
});
