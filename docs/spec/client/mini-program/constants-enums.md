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
