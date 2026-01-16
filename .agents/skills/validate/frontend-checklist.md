# Frontend Validation Checklist

Detailed frontend validation steps for WeChat MiniProgram.

## Configuration

**Read from**:
- `frontend/wx-minipg/package.json` - Scripts and dependencies
- `frontend/wx-minipg/.eslintrc.js` - ESLint rules
- `frontend/wx-minipg/tsconfig.json` - TypeScript configuration

**Never hardcode**: Paths or configuration values.

## Validation Steps

### Step 1: Run Complete Check

Run all checks at once:

```bash
cd frontend/wx-minipg
npm run check
```

This runs:
1. `npm run type-check` - TypeScript
2. `npm run lint` - ESLint
3. `npm run lint:style` - Stylelint
4. `npm run ui:audit` - UI guidelines

### Step 2: Auto-Fix Attempts

If checks fail, try auto-fix:

```bash
cd frontend/wx-minipg
npm run lint:fix    # Fix ESLint errors
npm run format      # Format with Prettier
```

Then re-run:
```bash
npm run check
```

### Step 3: Handle Specific Errors

#### TypeScript Type Errors

**Check**:
- Types correctly imported
- Page/Component data interfaces defined
- Event handlers have correct types (e.g., `WechatMiniprogram.TouchEvent`)
- Third-party libraries have type definitions in `typings/*.d.ts`

**Example**:
```typescript
// ✅ Good - Proper typing
interface PageData {
  userInfo: {
    nickname: string;
    avatar: string;
  };
}

Page<PageData>({
  data: {
    userInfo: {
      nickname: '',
      avatar: ''
    }
  }
});
```

#### ESLint Errors

**Common errors**:

**no-undef**: Variable not defined
```typescript
// ❌ Bad
console.log(someVar);  // someVar not imported

// ✅ Good
import { someVar } from './utils';
console.log(someVar);
```

**@typescript-eslint/no-explicit-any**: Avoid `any`
```typescript
// ❌ Bad
function process(data: any) { }

// ✅ Good
function process(data: unknown) {
  // Type guard
  if (typeof data === 'object' && data !== null) {
    // Now can use data
  }
}
```

**@typescript-eslint/no-var-requires**: Use ES6 imports
```typescript
// ❌ Bad
const utils = require('./utils');

// ✅ Good
import utils from './utils';
```

#### Stylelint Errors (WXSS)

**unit-no-unknown**: Use `rpx` instead of `px`
```css
/* ❌ Bad */
.container {
  width: 100px;
  padding: 20px;
}

/* ✅ Good */
.container {
  width: 100rpx;
  padding: 20rpx;
  border: 1px solid #ccc;  /* 1px is OK for borders */
}
```

**no-duplicate-selectors**: Remove duplicates
```css
/* ❌ Bad */
.button { color: red; }
.button { background: blue; }

/* ✅ Good */
.button {
  color: red;
  background: blue;
}
```

**color-hex-length**: Use shorthand
```css
/* ❌ Bad */
.text { color: #333333; }

/* ✅ Good */
.text { color: #333; }
```

#### UI Audit Errors

**Missing TDesign theme import**:
```css
/* ✅ Add at top of WXSS file */
@import '/styles/tdesign-theme.wxss';
```

**Hardcoded color values**:
```css
/* ❌ Bad */
.text {
  color: #333;
  background: #fff;
}

/* ✅ Good */
.text {
  color: var(--td-text-color-primary);
  background: var(--td-bg-color-container);
}
```

**Using px units**:
```css
/* ❌ Bad */
.container {
  width: 100px;
}

/* ✅ Good */
.container {
  width: 100rpx;
}
```

## Common Frontend Issues

### Issue: "Cannot find module" or "Module not found"

**Cause**: Missing import or incorrect path

**Solution**:
```typescript
// Check relative path
import { api } from '../../utils/api';  // Verify ../../ is correct

// Check file exists
// frontend/wx-minipg/utils/api.ts should exist
```

### Issue: "Property does not exist on type"

**Cause**: Missing type definition or incorrect interface

**Solution**:
```typescript
// ✅ Define proper interface
interface PageData {
  username: string;
  age: number;
}

Page<PageData>({
  data: {
    username: '',
    age: 0
  },
  onLoad() {
    // Now TypeScript knows about this.data.username
    console.log(this.data.username);
  }
});
```

### Issue: "Forbidden non-null assertion"

**Cause**: Using `!` operator (e.g., `value!`)

**Solution**:
```typescript
// ❌ Bad
const name = user!.name;

// ✅ Good - Option 1: Null check
if (user) {
  const name = user.name;
}

// ✅ Good - Option 2: Optional chaining
const name = user?.name;

// ✅ Good - Option 3: Default value
const name = user?.name ?? 'Guest';
```

### Issue: UI Audit fails - hardcoded colors

**Cause**: Using hex colors directly

**Solution**: Use TDesign CSS variables

**Common mappings**:
- `#333` → `var(--td-text-color-primary)`
- `#666` → `var(--td-text-color-secondary)`
- `#999` → `var(--td-text-color-placeholder)`
- `#fff` → `var(--td-bg-color-container)`
- `#f5f5f5` → `var(--td-bg-color-page)`

### Issue: UI Audit fails - missing theme import

**Cause**: WXSS file doesn't import TDesign theme

**Solution**:
```css
/* Add as first line in WXSS file */
@import '/styles/tdesign-theme.wxss';

.my-component {
  /* Now can use CSS variables */
  color: var(--td-text-color-primary);
}
```

## Reference

- Frontend rules: `frontend/wx-minipg/AGENTS.md`
- UI guidelines: `docs/spec/client/mini-program/UI-GUIDELINES.md`
- Type system: `frontend/wx-minipg/AGENTS.md` lines 197-205
- Code checking: `frontend/wx-minipg/AGENTS.md` lines 323-353
