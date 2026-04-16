const generateBuildInfo = require('./steps/generate-build-info');
const createNpmScriptStep = require('./steps/npm-script');

const HOOK_PIPELINES = {
  compile: [generateBuildInfo, createNpmScriptStep('build:ts')],
  preview: [generateBuildInfo, createNpmScriptStep('build:ts')],
  upload: [generateBuildInfo, createNpmScriptStep('build:ts')],
};

function resolvePipeline(hook) {
  const pipeline = HOOK_PIPELINES[hook];
  if (pipeline) {
    return pipeline;
  }

  const known = Object.keys(HOOK_PIPELINES).join(', ');
  const error = new Error(`Unknown hook "${hook}". Expected one of: ${known}`);
  error.name = 'DevtoolsHookError';
  throw error;
}

async function runHook(hook, ctx) {
  const pipeline = resolvePipeline(hook);
  console.log(`[devtools] Running hook "${hook}" (${pipeline.length} step(s))...`);

  for (const step of pipeline) {
    const stepName = step.name ?? 'unknown-step';
    console.log(`[devtools] → ${stepName}`);
    await step.run(ctx);
  }

  console.log(`[devtools] Hook "${hook}" finished.`);
}

module.exports = { runHook };
