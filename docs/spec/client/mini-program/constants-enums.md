# 枚举与常量管理规范

## 核心约束

<critical-rules>
- 所有枚举必须集中管理在 `utils/constants/` 目录下，按业务领域分类
- 所有枚举值必须与后端完全一致，添加注释说明对应关系
- 禁止在页面/组件中定义本地枚举常量
- 使用 `as const` 确保类型安全
- 枚举值变更必须同步更新后端文档链接
</critical-rules>

## 目录结构

```
utils/constants/
├── index.ts           # 统一导出入口
├── user.ts            # 用户相关枚举 (GENDER, USER_TYPE, USER_STATUS)
├── message.ts         # 消息相关枚举 (MESSAGE_STATUS, MESSAGE_TYPE)
└── [domain].ts        # 其他业务领域枚举
```

## 标准枚举定义模式

每个枚举文件应包含以下三部分：

### 1. 枚举值定义

```typescript
// utils/constants/user.ts

/**
 * 用户性别枚举
 * 对应后端: docs/data-dict/user.md#gender
 */
export const GENDER = {
  MALE: 'male',
  FEMALE: 'female',
  OTHER: 'other',
} as const;
```

### 2. 类型定义

```typescript
/**
 * 性别类型
 */
export type Gender = typeof GENDER[keyof typeof GENDER];
```

### 3. UI 选项（可选）

```typescript
/**
 * 性别选项（用于选择器）
 */
export const GENDER_OPTIONS = [
  { label: '男', value: GENDER.MALE },
  { label: '女', value: GENDER.FEMALE },
  { label: '其他', value: GENDER.OTHER },
] as const;

/**
 * 性别显示文本映射
 */
export const GENDER_LABELS: Record<Gender, string> = {
  [GENDER.MALE]: '男',
  [GENDER.FEMALE]: '女',
  [GENDER.OTHER]: '其他',
};
```

## 完整示例

参考 [utils/constants/user.ts](../../../frontend/wx-minipg/utils/constants/user.ts) 了解完整的实现模式。

## 使用规范

### 导入方式

```typescript
// 推荐：从统一入口导入
import { GENDER, Gender, GENDER_OPTIONS } from '../../utils/constants';

// 或：从具体文件导入
import { GENDER, Gender } from '../../utils/constants/user';
```

### 在页面中使用

```typescript
// pages/profile/profile.ts
import { GENDER, GENDER_OPTIONS } from '../../utils/constants';

Page({
  data: {
    genderOptions: GENDER_OPTIONS,
    currentGender: GENDER.MALE,
  },

  onGenderChange(e: WechatMiniprogram.PickerChange) {
    const gender = GENDER_OPTIONS[e.detail.value].value;
    this.setData({ currentGender: gender });
  },
});
```

### 在 WXML 中使用

```xml
<!-- pages/profile/profile.wxml -->
<picker
  mode="selector"
  range="{{genderOptions}}"
  range-key="label"
  value="{{currentGenderIndex}}"
  bindchange="onGenderChange"
>
  <view>{{currentGenderLabel}}</view>
</picker>
```

## 后端同步规则

1. **新增枚举值**：
   - 先确认后端已添加
   - 更新前端枚举定义
   - 更新文档链接注释

2. **修改枚举值**：
   - 确认后端已修改
   - 同步更新前端
   - 检查所有使用处

3. **删除枚举值**：
   - 确认后端已废弃
   - 搜索所有引用
   - 逐一替换或删除

## 常见错误

### ❌ 错误：在页面中定义本地枚举

```typescript
// pages/profile/profile.ts
Page({
  data: {
    GENDER_MALE: 'male',  // ❌ 不要这样做
    GENDER_FEMALE: 'female',
  },
});
```

### ✅ 正确：使用集中管理的枚举

```typescript
// pages/profile/profile.ts
import { GENDER } from '../../utils/constants';

Page({
  data: {
    gender: GENDER.MALE,  // ✅ 正确
  },
});
```

### ❌ 错误：硬编码枚举值

```typescript
if (user.gender === 'male') {  // ❌ 不要硬编码
  // ...
}
```

### ✅ 正确：使用枚举常量

```typescript
import { GENDER } from '../../utils/constants';

if (user.gender === GENDER.MALE) {  // ✅ 正确
  // ...
}
```

## 类型安全检查

使用 TypeScript 的类型系统确保枚举使用正确：

```typescript
import { GENDER, Gender } from '../../utils/constants';

function updateGender(gender: Gender) {
  // TypeScript 会检查 gender 必须是有效的枚举值
  console.log(gender);
}

updateGender(GENDER.MALE);  // ✅ 正确
updateGender('invalid');     // ❌ 编译错误
```
