const fs = require('node:fs');
const path = require('node:path');

function toIsoString(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  return date.toISOString();
}

function toDurationMs(startedAtMs, finishedAtMs) {
  if (!Number.isFinite(startedAtMs) || !Number.isFinite(finishedAtMs)) {
    return null;
  }
  return Math.max(0, Math.floor(finishedAtMs - startedAtMs));
}

function toErrorMessage(error) {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === 'string') {
    return error;
  }
  return '';
}

function findStepDurationMs(timeline, stepName) {
  const step = timeline.find((item) => item.name === stepName);
  if (!step) {
    return null;
  }
  return toDurationMs(step.startedAtMs, step.finishedAtMs);
}

function normalizeText(value) {
  if (typeof value !== 'string') {
    return '';
  }
  return value.trim();
}

function formatValue(value) {
  if (value === null || value === undefined || value === '') {
    return '-';
  }
  return String(value);
}

function escapeCellText(value) {
  return String(value).replace(/\|/g, '\\|').replace(/\r?\n/g, ' ');
}

function buildStepsTable(steps) {
  if (steps.length === 0) {
    return 'No step details.\n';
  }

  const lines = [
    '| Step | Status | Duration (ms) | Started At (UTC) | Finished At (UTC) |',
    '| --- | --- | ---: | --- | --- |',
  ];

  for (const step of steps) {
    lines.push(
      `| ${escapeCellText(step.name)} | ${escapeCellText(step.status)} | ${formatValue(step.duration_ms)} | ${escapeCellText(formatValue(step.started_at))} | ${escapeCellText(formatValue(step.finished_at))} |`
    );
  }

  return `${lines.join('\n')}\n`;
}

function buildMarkdownEntry(record) {
  const headerTime = formatValue(record.triggered_at);
  const lines = [
    `## Upload ${headerTime}`,
    '',
    `- Status: ${formatValue(record.status)}`,
    `- Triggered At (UTC): ${formatValue(record.triggered_at)}`,
    `- Finished At (UTC): ${formatValue(record.finished_at)}`,
    `- Hook Duration (ms): ${formatValue(record.duration_ms)}`,
    `- App Version: ${formatValue(record.app_version)}`,
    `- Build ID: ${formatValue(record.build_id)}`,
    `- Build Time (UTC): ${formatValue(record.build_time)}`,
    `- Build TS Duration (ms): ${formatValue(record.build_ts_duration_ms)}`,
    `- Dry Run: ${formatValue(record.dry_run)}`,
    `- Error: ${formatValue(record.error_message)}`,
    '',
    '### Steps',
    '',
    buildStepsTable(record.steps).trimEnd(),
    '',
    '---',
    '',
  ];
  return lines.join('\n');
}

module.exports = {
  name: 'record-upload-history',
  async run(ctx) {
    const hookRun = ctx.hookRun;
    if (!hookRun || hookRun.hook !== 'upload') {
      return;
    }

    const historyDirPath = ctx.resolvePath('scripts', 'devtools', 'logs');
    const historyFilePath = path.join(historyDirPath, 'upload-history.md');
    const timeline = Array.isArray(hookRun.timeline) ? hookRun.timeline : [];
    const buildInfo = ctx.buildInfo ?? {};

    const record = {
      hook: 'upload',
      status: hookRun.error === null ? 'success' : 'failed',
      triggered_at: toIsoString(hookRun.startedAtMs),
      finished_at: toIsoString(hookRun.finishedAtMs),
      duration_ms: toDurationMs(hookRun.startedAtMs, hookRun.finishedAtMs),
      app_version: normalizeText(buildInfo.appVersion),
      build_id: normalizeText(buildInfo.id),
      build_time: normalizeText(buildInfo.builtAt),
      build_ts_duration_ms: findStepDurationMs(timeline, 'npm:build:ts'),
      dry_run: ctx.dryRun === true,
      steps: timeline.map((step) => ({
        name: step.name,
        status: step.status,
        started_at: toIsoString(step.startedAtMs),
        finished_at: toIsoString(step.finishedAtMs),
        duration_ms: toDurationMs(step.startedAtMs, step.finishedAtMs),
      })),
      error_message: toErrorMessage(hookRun.error),
    };
    const markdownEntry = buildMarkdownEntry(record);

    if (ctx.dryRun) {
      console.log(`[devtools] (dry-run) upload history markdown:\n${markdownEntry}`);
      return;
    }

    fs.mkdirSync(historyDirPath, { recursive: true });
    fs.appendFileSync(historyFilePath, markdownEntry, 'utf8');
    console.log(`[devtools] Wrote upload history: ${historyFilePath}`);
  },
};
