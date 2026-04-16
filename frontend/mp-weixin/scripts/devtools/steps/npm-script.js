const { spawn } = require('node:child_process');

function runCommand(command, args, options) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      ...options,
      stdio: 'inherit',
      shell: process.platform === 'win32',
    });

    child.on('error', reject);
    child.on('close', (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`${command} ${args.join(' ')} exited with code ${code}`));
    });
  });
}

module.exports = function createNpmScriptStep(scriptName) {
  return {
    name: `npm:${scriptName}`,
    async run(ctx) {
      if (ctx.dryRun) {
        console.log(`[devtools] (dry-run) npm run ${scriptName}`);
        return;
      }
      await runCommand('npm', ['run', scriptName], { cwd: ctx.rootDir });
    },
  };
};
