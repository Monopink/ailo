#!/usr/bin/env node

/**
 * Lightweight UI audit to enforce migration rules on shared UI assets.
 */
const fs = require('fs');
const path = require('path');

const projectRoot = __dirname;

const WXSS_TARGETS = [
  path.join(projectRoot, 'app.wxss'),
  path.join(projectRoot, 'components', 'page-layout'),
  path.join(projectRoot, 'components', 'ui'),
  path.join(projectRoot, 'pages', 'index'),
  path.join(projectRoot, 'pages', 'chat'),
  path.join(projectRoot, 'pages', 'contact-info'),
  path.join(projectRoot, 'pages', 'stranger-info'),
  path.join(projectRoot, 'pages', 'profile-detail'),
  path.join(projectRoot, 'pages', 'account-security'),
];

const WXML_TARGETS = [
  path.join(projectRoot, 'pages', 'index'),
  path.join(projectRoot, 'pages', 'chat'),
  path.join(projectRoot, 'pages', 'contact-info'),
  path.join(projectRoot, 'pages', 'stranger-info'),
  path.join(projectRoot, 'pages', 'profile-detail'),
  path.join(projectRoot, 'pages', 'account-security'),
];

const errors = [];

const collectFiles = (entryPath, extension) => {
  const files = [];
  if (!fs.existsSync(entryPath)) {
    return files;
  }
  const stat = fs.statSync(entryPath);
  if (stat.isFile()) {
    if (entryPath.endsWith(extension)) {
      files.push(entryPath);
    }
    return files;
  }

  const stack = [entryPath];
  while (stack.length > 0) {
    const dir = stack.pop();
    const children = fs.readdirSync(dir, { withFileTypes: true });
    for (const child of children) {
      const childPath = path.join(dir, child.name);
      if (child.isDirectory()) {
        stack.push(childPath);
      } else if (childPath.endsWith(extension)) {
        files.push(childPath);
      }
    }
  }
  return files;
};

const relativePath = (filePath) => path.relative(projectRoot, filePath).replace(/\\/g, '/');

const checkWxssFile = (filePath) => {
  const content = fs.readFileSync(filePath, 'utf8');
  const relPath = relativePath(filePath);

  // Check hard-coded colors
  if (/#(?:[0-9a-fA-F]{3,8})\b/.test(content)) {
    errors.push(`[WXSS] ${relPath}: contains hard-coded color value.`);
  }

  // Check px units
  const pxRegex = /(\d+(?:\.\d+)?)px\b/g;
  let match;
  while ((match = pxRegex.exec(content)) !== null) {
    const value = Number(match[1]);
    if (value !== 1 && value !== 0) {
      errors.push(
        `[WXSS] ${relPath}: found disallowed px unit "${match[0]}" (only 1px borders allowed).`,
      );
    }
  }

  // Check forbidden page-level BEM classes (only for info pages)
  if (filePath.includes(path.join('pages', path.sep))) {
    const fileName = path.basename(filePath, '.wxss');
    const infoPages = ['contact-info', 'stranger-info', 'profile-detail', 'account-security'];

    // Only check info pages for forbidden patterns
    if (infoPages.includes(fileName)) {
      const forbiddenPatterns = [
        {
          pattern: /\.\w+-\w+__hero\b/g,
          message: 'page-level __hero class detected',
          suggestion: 'Use ui-card component + .info-hero layout class from design-tokens.wxss',
        },
        {
          pattern: /\.\w+-\w+__bio\b/g,
          message: 'page-level __bio class detected',
          suggestion: 'Use ui-card component with text content',
        },
        {
          pattern: /\.\w+-\w+__group\b/g,
          message: 'page-level __group class detected',
          suggestion: 'Use ui-card component',
        },
        {
          pattern: /\.\w+-\w+__actions\b/g,
          message: 'page-level __actions class detected',
          suggestion: 'Use .page-actions or .page-actions--fixed layout class from design-tokens.wxss',
        },
        {
          pattern: /\.\w+-\w+__hero-info\b/g,
          message: 'page-level __hero-info class detected',
          suggestion: 'Use .info-hero__content layout class from design-tokens.wxss',
        },
        {
          pattern: /\.\w+-\w+__hero-name\b/g,
          message: 'page-level __hero-name class detected',
          suggestion: 'Use .info-hero__name layout class from design-tokens.wxss',
        },
        {
          pattern: /\.(contact-info|stranger-info|profile-detail|account-security)__tags\b/g,
          message: 'page-level __tags class detected',
          suggestion: 'Use .tags-container layout class from design-tokens.wxss',
        },
      ];

      forbiddenPatterns.forEach(({ pattern, message, suggestion }) => {
        if (pattern.test(content)) {
          errors.push(`[WXSS] ${relPath}: ${message}. ${suggestion}`);
        }
      });
    }
  }
};

const checkWxmlFile = (filePath) => {
  const content = fs.readFileSync(filePath, 'utf8');
  const relPath = relativePath(filePath);
  const fileName = path.basename(filePath, '.wxml');

  // Check page-layout wrapper
  if (!content.includes('<page-layout')) {
    errors.push(`[WXML] ${relPath}: missing <page-layout> wrapper.`);
  }

  // Check raw button usage
  if (/<button\b/i.test(content)) {
    errors.push(`[WXML] ${relPath}: raw <button> detected, use <ui-button> instead.`);
  }

  // Check required components for info pages
  const infoPages = ['contact-info', 'stranger-info', 'profile-detail'];
  if (infoPages.includes(fileName)) {
    if (!content.includes('<ui-card')) {
      errors.push(
        `[WXML] ${relPath}: info page must use <ui-card> component for sections. See docs/spec/mini-program/UI-GUIDELINES.md`,
      );
    }

    // Check avatar usage (except profile-detail which uses ui-cell for avatar)
    if (fileName !== 'profile-detail' && !content.includes('<ui-avatar')) {
      errors.push(
        `[WXML] ${relPath}: must use <ui-avatar> component instead of custom avatar implementation.`,
      );
    }

    // Check cell usage for list items
    if (!content.includes('<ui-cell')) {
      errors.push(
        `[WXML] ${relPath}: must use <ui-cell> component for list items instead of custom implementation.`,
      );
    }
  }
};

const run = () => {
  const wxssFiles = WXSS_TARGETS.flatMap((target) => collectFiles(target, '.wxss'));
  wxssFiles.forEach(checkWxssFile);

  const wxmlFiles = WXML_TARGETS.flatMap((target) => collectFiles(target, '.wxml'));
  wxmlFiles.forEach(checkWxmlFile);

  if (errors.length > 0) {
    console.error('UI audit failed:\n');
    for (const error of errors) {
      console.error(`- ${error}`);
    }
    process.exit(1);
  }

  console.log('UI audit passed for shared UI assets.');
};

run();
