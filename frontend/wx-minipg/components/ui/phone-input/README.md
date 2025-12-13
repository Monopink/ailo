# Phone Input Component

手机号输入组件，固定中国大陆区号 (+86)。

## 功能特性

- 固定国家代码 +86（中国大陆）
- 自动验证手机号长度（11位）
- 返回完整手机号（包含国家代码）
- 响应式高度统一（88rpx）

## 使用示例

### 基本用法

```xml
<phone-input
  value="{{phone}}"
  bindchange="handlePhoneChange" />
```

### 禁用状态

```xml
<phone-input
  value="{{phone}}"
  disabled="{{true}}"
  bindchange="handlePhoneChange" />
```

## Properties

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| value | String | '' | 手机号码值（不含国家代码） |
| placeholder | String | '请输入手机号' | 占位符文本 |
| disabled | Boolean | false | 是否禁用 |

## Events

### bindchange
手机号变化时触发

```typescript
event.detail = {
  value: string;        // 手机号（不含国家代码）
  countryCode: string;  // 国家代码，固定为 '+86'
  fullPhone: string;    // 完整手机号，如 '+8613800138000'
  valid: boolean;       // 是否符合11位手机号长度要求
}
```

### bindfocus / bindblur
输入框获得/失去焦点时触发

## 公开方法

可通过 `selectComponent` 调用：

```typescript
const phoneInput = this.selectComponent('#phoneInput');

// 获取完整手机号（包含国家代码）
const fullPhone = phoneInput.getFullPhone(); // '+8613800138000'

// 验证手机号
const isValid = phoneInput.validate(); // true/false
```

## 样式说明

组件高度统一为 88rpx，与 TDesign Button 保持一致。
左侧区号显示和右侧输入框为独立的两个框，使用 `gap` 分隔。

## 支持的国家/地区

- 🇨🇳 中国大陆 (+86, 11位)
