{
  "root": true,
  "parser": "@typescript-eslint/parser",
  "parserOptions": {
    "ecmaVersion": 2020,
    "sourceType": "module"
  },
  "plugins": ["@typescript-eslint"],
  "extends": ["eslint:recommended", "plugin:@typescript-eslint/recommended", "prettier"],
  "overrides": [
    {
      "files": ["*.ts"],
      "parserOptions": {
        "project": "./tsconfig.json"
      },
      "extends": ["plugin:@typescript-eslint/recommended-requiring-type-checking"]
    }
  ],
  "rules": {
    "@typescript-eslint/no-explicit-any": "error",
    "@typescript-eslint/explicit-function-return-type": [
      "warn",
      {
        "allowExpressions": true,
        "allowTypedFunctionExpressions": true
      }
    ],
    "@typescript-eslint/no-unused-vars": [
      "error",
      {
        "argsIgnorePattern": "^_",
        "varsIgnorePattern": "^_"
      }
    ],
    "@typescript-eslint/naming-convention": [
      "error",
      {
        "selector": "variable",
        "format": ["camelCase", "UPPER_CASE", "PascalCase"],
        "leadingUnderscore": "allow"
      },
      {
        "selector": "function",
        "format": ["camelCase", "PascalCase"]
      },
      {
        "selector": "typeLike",
        "format": ["PascalCase"]
      },
      {
        "selector": "parameter",
        "format": ["camelCase"],
        "leadingUnderscore": "allow"
      }
    ],
    "no-console": ["warn", { "allow": ["warn", "error"] }],
    "prefer-const": "error",
    "no-var": "error",
    "eqeqeq": ["error", "always"],
    "curly": ["error", "all"]
  },
  "env": {
    "es6": true,
    "node": true
  },
  "globals": {
    "wx": "readonly",
    "App": "readonly",
    "Page": "readonly",
    "Component": "readonly",
    "getApp": "readonly",
    "getCurrentPages": "readonly",
    "Behavior": "readonly",
    "requirePlugin": "readonly"
  },
  "ignorePatterns": [
    "node_modules/",
    "miniprogram_npm/",
    "libs/",
    "test/",
    "minitest/",
    "*.config.js"
  ]
}
