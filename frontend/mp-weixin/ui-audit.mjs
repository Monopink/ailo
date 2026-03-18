#!/usr/bin/env node

/**
 * Lightweight UI audit for TDesign migration.
 * Simplified version that only checks essential rules.
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const currentFilename = fileURLToPath(import.meta.url);
const currentDirname = path.dirname(currentFilename);
const projectRoot = currentDirname;

// Check all pages (all have been migrated to TDesign)
const WXSS_TARGETS = [path.join(projectRoot, 'pages')];

const errors = [];

/**
 * Collect files with a specific extension from a directory
 * @param {string} entryPath - The path to search
 * @param {string} extension - The file extension to match
 * @returns {string[]} Array of file paths
 */
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
    if (!dir) {
      continue;
    }
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

/**
 * Get relative path from project root
 * @param {string} filePath - Absolute file path
 * @returns {string} Relative path
 */
const relativePath = (filePath) => path.relative(projectRoot, filePath).replace(/\\/g, '/');

/**
 * Check a WXSS file for TDesign compliance
 * @param {string} filePath - Path to WXSS file
 * @returns {void}
 */
const checkWxssFile = (filePath) => {
  const content = fs.readFileSync(filePath, 'utf8');
  const relPath = relativePath(filePath);

  // Check if WXSS imports TDesign theme
  const hasTDesignImport = /@import\s+['"]\/styles\/tdesign-theme\.wxss['"]\s*;/.test(content);

  if (!hasTDesignImport) {
    errors.push(
      `[WXSS] ${relPath}: missing "@import '/styles/tdesign-theme.wxss'". TDesign pages must import the theme.`,
    );
  }

  // Check px units (except 1px borders and special cases)
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
};

/**
 * Run the UI audit
 * @returns {void}
 */
const run = () => {
  const wxssFiles = [...new Set(WXSS_TARGETS)].flatMap((target) => collectFiles(target, '.wxss'));
  wxssFiles.forEach(checkWxssFile);

  if (errors.length > 0) {
    console.error('UI audit failed:\n');
    for (const error of errors) {
      console.error(`- ${error}`);
    }
    process.exit(1);
  }

  console.warn('UI audit passed for all TDesign pages.');
};

run();
