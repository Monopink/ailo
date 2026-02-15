# Frontend Validation Checklist

Run frontend checks with configured npm scripts.

## Required Config

- `frontend/wx-minipg/package.json`
- `frontend/wx-minipg/.eslintrc.js`
- `frontend/wx-minipg/tsconfig.json`

## Validation Commands

Run in `frontend/wx-minipg`:

```bash
npm run check
```

## Auto-Fix Sequence

If check fails:

```bash
npm run lint:fix
npm run format
npm run check
```

## Failure Handling

1. TypeScript errors: complete missing/incorrect type definitions.
2. ESLint errors: follow project lint rules, avoid `any` unless justified.
3. Stylelint errors: keep WXSS compliant with project rules.
4. UI audit errors: use theme variables and required theme imports.
5. Do not suppress errors with fallback logic that hides defects.

## Completion Criteria

- `npm run check` passes.
- Modified files have no new lint/style/type violations.
- UI guideline checks pass for modified pages/components.
