module.exports = {
  root: true,
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 2020,
    sourceType: 'module',
  },
  plugins: ['@typescript-eslint'],
  extends: ['eslint:recommended', 'plugin:@typescript-eslint/recommended', 'prettier'],
  overrides: [
    {
      files: ['*.mjs', '*.cjs'],
      rules: {
        // Disable TypeScript-specific rules for plain JavaScript files
        '@typescript-eslint/explicit-function-return-type': 'off',
        '@typescript-eslint/no-var-requires': 'off',
      },
    },
    {
      files: ['*.ts'],
      parserOptions: {
        project: './tsconfig.json',
        tsconfigRootDir: __dirname,
      },
      extends: ['plugin:@typescript-eslint/recommended-requiring-type-checking'],
      rules: {
        // TypeScript safety rules requiring type information
        '@typescript-eslint/no-floating-promises': [
          'error',
          {
            ignoreVoid: true,
            ignoreIIFE: true,
          },
        ],
        '@typescript-eslint/no-misused-promises': [
          'error',
          {
            checksConditionals: true,
            checksVoidReturn: true,
          },
        ],
        '@typescript-eslint/no-unnecessary-type-assertion': 'error',
        '@typescript-eslint/prefer-nullish-coalescing': 'error',
        '@typescript-eslint/prefer-optional-chain': 'error',
        '@typescript-eslint/no-unnecessary-condition': [
          'error',
          {
            allowConstantLoopConditions: true,
          },
        ],
        '@typescript-eslint/strict-boolean-expressions': [
          'error',
          {
            allowString: false,
            allowNumber: false,
            allowNullableObject: false,
            allowNullableBoolean: true,
            allowNullableString: false,
            allowNullableNumber: false,
            allowAny: false,
          },
        ],
      },
    },
    {
      files: ['*.wxml'],
      plugins: ['wxml'],
      processor: 'wxml/wxml',
      parser: '@wxml/parser',
      rules: {
        // Enable WXML syntax checking
        'wxml/report-wxml-syntax-error': 'error',
        // Disable all TypeScript rules for WXML files
        '@typescript-eslint/no-explicit-any': 'off',
        '@typescript-eslint/explicit-function-return-type': 'off',
        '@typescript-eslint/no-unused-vars': 'off',
        '@typescript-eslint/naming-convention': 'off',
      },
    },
  ],
  rules: {
    '@typescript-eslint/no-explicit-any': 'error',
    '@typescript-eslint/explicit-function-return-type': [
      'error',
      {
        allowExpressions: true,
        allowTypedFunctionExpressions: true,
        allowHigherOrderFunctions: true,
      },
    ],
    '@typescript-eslint/no-unused-vars': [
      'error',
      {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
      },
    ],
    '@typescript-eslint/naming-convention': [
      'error',
      {
        selector: 'variable',
        format: ['camelCase', 'UPPER_CASE', 'PascalCase'],
        leadingUnderscore: 'allow',
      },
      {
        selector: 'function',
        format: ['camelCase', 'PascalCase'],
      },
      {
        selector: 'typeLike',
        format: ['PascalCase'],
      },
      {
        selector: 'parameter',
        format: ['camelCase'],
        leadingUnderscore: 'allow',
      },
    ],
    'no-console': ['error', { allow: ['warn', 'error'] }],
    'prefer-const': 'error',
    'no-var': 'error',
    eqeqeq: ['error', 'always'],
    curly: ['error', 'all'],

    // Code quality rules (not requiring type information)
    complexity: ['error', { max: 15 }],
    'max-depth': ['error', { max: 4 }],
    'max-lines-per-function': [
      'error',
      {
        max: 100,
        skipBlankLines: true,
        skipComments: true,
        IIFEs: true,
      },
    ],
    'max-params': ['error', { max: 5 }],
    'no-await-in-loop': 'error',
    'require-atomic-updates': 'error',
  },
  env: {
    es6: true,
    node: true,
  },
  globals: {
    wx: 'readonly',
    App: 'readonly',
    Page: 'readonly',
    Component: 'readonly',
    getApp: 'readonly',
    getCurrentPages: 'readonly',
    Behavior: 'readonly',
    requirePlugin: 'readonly',
  },
  ignorePatterns: [
    'node_modules/',
    'miniprogram_npm/',
    'libs/',
    'test/',
    'minitest/',
    '**/*.generated.d.ts',
    '*.config.js',
    '**/*.js', // Ignore all compiled JS files from TypeScript
    '!.eslintrc.js', // But keep ESLint config
  ],
};
