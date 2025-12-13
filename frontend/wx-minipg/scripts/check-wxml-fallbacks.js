#!/usr/bin/env node

/**
 * WXML Fallback Value Checker
 *
 * Enforces the rule that WXML templates should not contain fallback values
 * except for system messages, UI states, and whitelisted scenarios.
 *
 * Allowed:
 * - System messages: {{errorMessage || 'Default error'}}
 * - UI states: {{disabled ? 'class--disabled' : ''}}
 * - Boolean conversion: {{!!value}}
 *
 * Disallowed:
 * - User data: {{nickname || 'Default Name'}}
 * - General data with fallbacks
 */

const fs = require('fs');
const path = require('path');

// Whitelist patterns for variable names that are allowed to have fallbacks
const ALLOWED_VARIABLE_PATTERNS = [
  /^(error|status|loading|empty|placeholder|hint|tip|message|notice|alert|warning|info).*$/i,
  /.*(_error|_status|_loading|_empty|_message|_text|_label)$/i,
];

// Data field patterns that should NEVER have fallbacks (user data, business data)
const FORBIDDEN_VARIABLE_PATTERNS = [
  /^(nickname|avatar|name|phone|email|bio|description|title|content|address|real_?name)$/i,
  /^(user|profile|contact|account|member).*$/i,
  /^ai_(name|avatar|nickname|bio|description)$/i,
];

// Patterns to detect fallback values in WXML
const FALLBACK_PATTERNS = [
  // {{variable || 'fallback'}} or {{variable || "fallback"}}
  {
    regex: /\{\{([^}]+?)\s*\|\|\s*['"]([^'"]+)['"]\}\}/g,
    type: 'logical-or',
  },
  // {{variable ? variable : 'fallback'}} (non-class/style ternary)
  {
    regex: /\{\{([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\?\s*\1\s*:\s*['"]([^'"]+)['"]\}\}/g,
    type: 'ternary-self',
  },
  // {{variable ? 'value1' : 'value2'}} (potential fallback, needs context check)
  {
    regex: /\{\{([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\?\s*['"]([^'"]+)['"]\s*:\s*['"]([^'"]+)['"]\}\}/g,
    type: 'ternary-both-strings',
  },
];

// Context patterns that indicate allowed usage (class/style attributes)
const ALLOWED_CONTEXT_PATTERNS = [
  /class\s*=\s*["'][^"']*$/,
  /style\s*=\s*["'][^"']*$/,
  /wx:class\s*=\s*["'][^"']*$/,
];

/**
 * Check if a variable name is allowed to have fallbacks
 */
function isAllowedVariable(variableName) {
  const cleanName = variableName.trim().split(/[.\[\s]/)[0];

  // Check whitelist
  for (const pattern of ALLOWED_VARIABLE_PATTERNS) {
    if (pattern.test(cleanName)) {
      return true;
    }
  }

  return false;
}

/**
 * Check if a variable name is forbidden from having fallbacks
 */
function isForbiddenVariable(variableName) {
  const cleanName = variableName.trim().split(/[.\[\s]/)[0];

  for (const pattern of FORBIDDEN_VARIABLE_PATTERNS) {
    if (pattern.test(cleanName)) {
      return true;
    }
  }

  return false;
}

/**
 * Check if the fallback is in an allowed context (class/style)
 */
function isInAllowedContext(line, matchIndex) {
  const beforeMatch = line.substring(0, matchIndex);

  for (const pattern of ALLOWED_CONTEXT_PATTERNS) {
    if (pattern.test(beforeMatch)) {
      return true;
    }
  }

  return false;
}

/**
 * Check if ternary is for class/style (both values are CSS-like)
 */
function isCssClassTernary(value1, value2) {
  const cssPatterns = [
    /^[a-z-]+(__[a-z-]+)?(--[a-z-]+)?$/i, // BEM
    /^[a-z-]+$/i, // simple class
    /^t-[a-z-]+/i, // TDesign prefix
    /^ui-[a-z-]+/i, // ui prefix
    /^$/, // empty string
  ];

  return cssPatterns.some((p) => p.test(value1) && p.test(value2));
}

/**
 * Detect the type of violation based on pattern and variable name
 */
function detectViolationType(code, variableName) {
  // Check for binding data patterns (phone, email, etc.)
  if (/(phone|email|account|id).*\|\|.*['"]未绑定['"]/i.test(code)) {
    return 'binding-data';
  }

  // Check for avatar/image with default path
  if (/(avatar|image|icon|photo).*\|\|.*['"]\//i.test(code)) {
    return 'default-image';
  }

  // Check for button text with ternary (saving, loading, etc.)
  if (/\?\s*['"][^'"]*\.\.\.['"]\s*:/i.test(code)) {
    return 'button-text';
  }

  // Check for placeholder/selection display
  if (/display.*\|\|.*['"]请/i.test(code)) {
    return 'placeholder';
  }

  // Check for conditional button text
  if (/(isLoggedIn|isLogin|hasAuth).*\?.*:/.test(code)) {
    return 'conditional-text';
  }

  // Check for username/name with placeholder
  if (/(username|nickname|name).*\|\|.*['"]--['"]/i.test(code)) {
    return 'user-name';
  }

  return 'general';
}

/**
 * Generate fix suggestion based on violation type
 */
function generateFixSuggestion(code, variableName, violationType) {
  const suggestions = {
    'user-data': `Move to TS layer:
      // In TS file
      data: {
        display${capitalize(variableName)}: this.data.${variableName} || ''  // Or handle with wx:if in WXML
      }
      // In WXML
      <text wx:if="{{display${capitalize(variableName)}}}">{{display${capitalize(variableName)}}}</text>
      <text wx:else class="placeholder">--</text>`,

    'binding-data': `Move to TS layer:
      // In TS file
      data: {
        ${variableName}Display: this.data.${variableName} || '未绑定'
      }
      // In WXML
      <text>{{${variableName}Display}}</text>`,

    'default-image': `Move to TS layer or use wx:if:
      // Option 1: In TS file
      data: {
        display${capitalize(variableName)}: this.data.${variableName} || '/assets/avatars/default.png'
      }
      // Option 2: In WXML (recommended for images)
      <image wx:if="{{${variableName}}}" src="{{${variableName}}}" />
      <image wx:else src="/assets/avatars/default.png" />`,

    'button-text': `Move to TS layer:
      // In TS file
      data: {
        buttonText: ''
      }
      onLoad() {
        this.updateButtonText();
      }
      updateButtonText() {
        this.setData({
          buttonText: this.data.${variableName} ? '保存中...' : '保存'
        });
      }
      // In WXML
      <button>{{buttonText}}</button>`,

    placeholder: `Move to TS layer:
      // In TS file
      data: {
        ${variableName}: '请选择地区'  // Set initial value
      }
      // In WXML
      <text>{{${variableName}}}</text>`,

    'conditional-text': `This condition suggests invalid state - user should not see this page when condition is false.
      Fix by:
      1. Add route guard in previous page
      2. Or remove the conditional text (single state only)

      // In WXML (if condition is valid)
      <button>添加联系人</button>  // Remove conditional`,

    'user-name': `Move to TS layer or use wx:if:
      // Option 1: In TS file (for display text)
      data: {
        displayName: this.data.${variableName} || '--'
      }
      // Option 2: In WXML (show/hide based on value)
      <text wx:if="{{${variableName}}}">{{${variableName}}}</text>
      <text wx:else class="placeholder">--</text>`,

    general: `Move fallback logic to TS layer:
      // In TS file
      data: {
        display${capitalize(variableName)}: this.calculateDisplay()
      }
      calculateDisplay() {
        // Handle your fallback logic here
        return this.data.${variableName} || 'default value';
      }
      // In WXML
      <text>{{display${capitalize(variableName)}}}</text>`,
  };

  return suggestions[violationType] || suggestions['general'];
}

/**
 * Capitalize first letter of string
 */
function capitalize(str) {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

/**
 * Scan a single WXML file for fallback violations
 */
function scanFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  const lines = content.split('\n');
  const violations = [];

  lines.forEach((line, lineIndex) => {
    for (const { regex, type } of FALLBACK_PATTERNS) {
      let match;
      const regexCopy = new RegExp(regex.source, regex.flags);

      while ((match = regexCopy.exec(line)) !== null) {
        const matchIndex = match.index;
        const fullMatch = match[0];
        const variablePart = match[1];

        // Extract variable name from expression (handle complex expressions)
        const variableMatch = variablePart.match(/([a-zA-Z_$][a-zA-Z0-9_$]*)/);
        const variableName = variableMatch ? variableMatch[1] : variablePart;

        // Skip if in allowed context (class/style)
        if (isInAllowedContext(line, matchIndex)) {
          continue;
        }

        // Special handling for ternary-both-strings (could be class/style)
        if (type === 'ternary-both-strings') {
          const value1 = match[2];
          const value2 = match[3];

          if (isCssClassTernary(value1, value2)) {
            continue;
          }
        }

        // Check if variable is explicitly forbidden
        if (isForbiddenVariable(variableName)) {
          violations.push({
            line: lineIndex + 1,
            column: matchIndex + 1,
            code: fullMatch,
            variable: variableName,
            reason: 'User/business data should not have fallback values',
            severity: 'error',
            fixSuggestion: generateFixSuggestion(fullMatch, variableName, 'user-data'),
          });
          continue;
        }

        // Check if variable is whitelisted
        if (isAllowedVariable(variableName)) {
          continue;
        }

        // Detect violation type based on pattern
        const violationType = detectViolationType(fullMatch, variableName);

        // Not whitelisted and not forbidden - report as warning
        violations.push({
          line: lineIndex + 1,
          column: matchIndex + 1,
          code: fullMatch,
          variable: variableName,
          reason: 'Data should not have fallback values in template. Handle in logic layer (TS)',
          severity: 'error',
          fixSuggestion: generateFixSuggestion(fullMatch, variableName, violationType),
        });
      }
    }
  });

  return violations;
}

/**
 * Recursively find all WXML files
 */
function findWxmlFiles(dir, fileList = []) {
  const files = fs.readdirSync(dir);

  files.forEach((file) => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);

    if (stat.isDirectory()) {
      // Skip node_modules and dist
      if (file !== 'node_modules' && file !== 'dist' && file !== 'miniprogram_npm') {
        findWxmlFiles(filePath, fileList);
      }
    } else if (file.endsWith('.wxml')) {
      fileList.push(filePath);
    }
  });

  return fileList;
}

/**
 * Format violations for console output
 */
function formatViolations(violations, baseDir) {
  let output = '';
  let errorCount = 0;

  Object.entries(violations).forEach(([filePath, fileViolations]) => {
    if (fileViolations.length > 0) {
      const relativePath = path.relative(baseDir, filePath);
      output += `\n${relativePath}\n`;

      fileViolations.forEach((v) => {
        errorCount++;
        const severity = v.severity === 'error' ? '✗' : '⚠';
        output += `  ${severity} ${v.line}:${v.column}  ${v.reason}\n`;
        output += `    ${v.code}\n`;
        output += `    Variable: ${v.variable}\n`;
        if (v.fixSuggestion) {
          output += `\n    💡 Fix:\n`;
          v.fixSuggestion.split('\n').forEach((line) => {
            output += `    ${line}\n`;
          });
        }
        output += '\n';
      });
    }
  });

  return { output, errorCount };
}

/**
 * Main execution
 */
function main() {
  const projectRoot = path.resolve(__dirname, '..');
  const wxmlFiles = findWxmlFiles(projectRoot);

  if (wxmlFiles.length === 0) {
    console.log('No WXML files found.');
    return;
  }

  console.log(`Checking ${wxmlFiles.length} WXML files for fallback values...\n`);

  const violations = {};
  let totalViolations = 0;

  wxmlFiles.forEach((filePath) => {
    const fileViolations = scanFile(filePath);
    if (fileViolations.length > 0) {
      violations[filePath] = fileViolations;
      totalViolations += fileViolations.length;
    }
  });

  if (totalViolations === 0) {
    console.log('✓ No fallback value violations found!\n');
    process.exit(0);
  }

  const { output, errorCount } = formatViolations(violations, projectRoot);
  console.log(output);
  console.log(`\n✗ Found ${errorCount} fallback value violation(s)\n`);
  console.log('Rules:');
  console.log('  - User/business data should NOT have fallback values');
  console.log('  - Handle default values in logic layer (TypeScript)');
  console.log('  - System messages (error*, loading*, etc.) are allowed\n');

  process.exit(1);
}

// Run if executed directly
if (require.main === module) {
  main();
}

module.exports = { scanFile, isAllowedVariable, isForbiddenVariable };
