const generateBuildInfo = require('./steps/generate-build-info');
const createNpmScriptStep = require('./steps/npm-script');
const recordUploadHistory = require('./steps/record-upload-history');

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
  const hookStartedAtMs = Date.now();
  const hookTimeline = [];
  let hookError = null;
  console.log(`[devtools] Running hook "${hook}" (${pipeline.length} step(s))...`);

  try {
    for (const step of pipeline) {
      const stepName = step.name ?? 'unknown-step';
      const startedAtMs = Date.now();
      console.log(`[devtools] → ${stepName}`);
      try {
        await step.run(ctx);
        hookTimeline.push({
          name: stepName,
          status: 'success',
          startedAtMs,
          finishedAtMs: Date.now(),
        });
      } catch (error) {
        hookTimeline.push({
          name: stepName,
          status: 'failed',
          startedAtMs,
          finishedAtMs: Date.now(),
        });
        throw error;
      }
    }
  } catch (error) {
    hookError = error;
  } finally {
    ctx.hookRun = {
      hook,
      startedAtMs: hookStartedAtMs,
      finishedAtMs: Date.now(),
      timeline: hookTimeline,
      error: hookError,
    };

    if (hook === 'upload') {
      try {
        await recordUploadHistory.run(ctx);
      } catch (logError) {
        const message =
          logError instanceof Error ? logError.message : 'Unknown upload history logging error';
        console.warn(`[devtools] Failed to write upload history: ${message}`);
      }
    }
  }

  if (hookError !== null) {
    throw hookError;
  }
  console.log(`[devtools] Hook "${hook}" finished.`);
}

module.exports = { runHook };
