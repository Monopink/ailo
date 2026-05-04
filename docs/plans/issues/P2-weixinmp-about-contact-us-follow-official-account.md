# 小程序：关于页「联系我们」改为直达公众号关注（含 runtime observation 上报）

## 目标

- 「关于」页的「联系我们」入口以最短路径引导用户关注公众号。
- 支持低版本微信基础库的降级路径，保证入口可用。
- 将关键节点纳入 `client_runtime_observations`，用于排障与链路可见性。

## 需求与约束

- 主链路：点击「联系我们」后优先调用 `wx.openOfficialAccountProfile({ username })` 打开公众号主页。
  - 基础库门槛：`wx.openOfficialAccountProfile` 自基础库 **3.7.10** 开始支持。
- 降级链路：当主链路不可用或调用失败时，展示公众号二维码（支持长按识别关注）与“复制公众号用户名”按钮。
  - 二维码展示必须使用原生 `image` 组件（支持 `show-menu-by-longpress`）。
- 配置约束：小程序端资源 URL 统一使用 `frontend/mp-weixin/utils/config.ts` 的 `ASSET_CONFIG`，禁止在页面/组件中硬编码 COS/CDN URL。
- 行为上报：保留后端 `event_name` 白名单机制（按需扩容），本次仅新增 2 个事件。
- 本文档为方案文档，仅描述本次改造的范围与实施步骤；持久化规范内容需要同步到项目文档（见“文档改动”）。

## 现状

- 入口位置：`frontend/mp-weixin/pkg/about/about.wxml` 的 `t-cell title="联系我们"`。
- 当前跳转：`frontend/mp-weixin/pkg/about/about.ts` 点击后直接引导关注公众号，且不通过 `app-page` 链路渲染二维码内容。
- 当前渲染方式：`frontend/mp-weixin/pkg/app-page/app-page.wxml` 使用 `rich-text mode="web"` 渲染 `contentRendered`。
- 问题表现：在该实现形态下，二维码无法稳定触发“长按识别并跳转公众号关注”的用户路径。

## 影响范围（文件清单）

### 文档

- `docs/spec/client/base/profile-and-settings.md`（关于页的联系我们实现描述）
- `docs/spec/client/mini-program/prototype.md`（关于页入口实现描述）
- `docs/plans/issues/P2-weixinmp-about-contact-us-follow-official-account.md`（本方案文档）

### 小程序端

- `frontend/mp-weixin/pkg/about/about.ts`（替换「联系我们」点击行为）
- `frontend/mp-weixin/pkg/about/about.wxml`（如采用弹窗方案，可能需要新增弹窗组件引用/布局）
- `frontend/mp-weixin/utils/config.ts`（新增公众号配置与二维码资源路径/URL）
- `frontend/mp-weixin/utils/runtime-segment.ts`（复用 `reportRuntimeObservation()`，一般无需改）

### 后端

- `backend/app/api/v1/client.py`（扩容 `RUNTIME_EVENT_NAME_WHITELIST`）

## 方案设计

### 交互与链路

1) 用户点击「关于」页 -「联系我们」。

2) 主链路：若 `wx.canIUse('wx.openOfficialAccountProfile')` 为 true，则调用：

- `wx.openOfficialAccountProfile({ username: OFFICIAL_ACCOUNT_ORIGINAL_ID })`

3) 降级链路：若主链路不可用或调用失败，展示“关注公众号”弹窗（或独立页面，二选一）。

- 展示二维码：使用原生 `<image show-menu-by-longpress />`，二维码 URL 从 `ASSET_CONFIG` 读取。
- 文案提示：引导用户长按识别关注。
- 辅助动作：提供“复制公众号用户名”按钮，调用 `wx.setClipboardData({ data: OFFICIAL_ACCOUNT_USERNAME })`。

### 配置管理

新增配置项定义（落地在 `frontend/mp-weixin/utils/config.ts`）：

- 新增 `OFFICIAL_ACCOUNT_CONFIG`（非资源配置）：
  - `originalId: string`：公众号原始 ID（仅用于 `wx.openOfficialAccountProfile({ username })`，不在 UI 中展示）
  - `username: string`：公众号用户名（微信号，用于降级弹窗展示与复制）

- 扩展 `ASSET_CONFIG`（资源配置）：
  - 增加 `officialAccountQrCodePath: string`（相对路径，默认值写入 `DEFAULT_ASSET_PATHS`）
  - 增加派生字段 `officialAccountQrCodeUrl: string`
    - `officialAccountQrCodeUrl = buildAssetUrl(ASSET_CONFIG.cosBaseUrl, officialAccountQrCodePath)`

说明：二维码为稳定静态资源时，将其纳入 `ASSET_CONFIG` 可以减少散落硬编码；`originalId` 仅用于跳转能力，不用于用户可见展示；用户可见信息使用 `username`。

## 行为上报（client_runtime_observations）

### 事件与用途

本次新增 2 个事件，用于排障与链路可见性：

1) `official_account_follow_attempt`

- 触发时机：用户点击「联系我们」并准备执行引导动作时（主链路调用前）。
- `event_payload`：
  - `method`: `'open_profile'`
  - `can_i_use_open_profile`: boolean

2) `official_account_follow_fallback_shown`

- 触发时机：主链路不可用或调用失败后，展示“关注公众号”降级弹窗/页面时。
- `event_payload`：
  - `reason`: `'can_i_use_false' | 'api_fail'`
  - `fail_err_msg`: string（客户端截断 + 服务端二次截断后存储）

### 后端白名单扩容

- 在 `backend/app/api/v1/client.py` 的 `RUNTIME_EVENT_NAME_WHITELIST` 中加入上述两个事件名：
  - `official_account_follow_attempt`
  - `official_account_follow_fallback_shown`
- 保持白名单策略，不接受任意 `event_name`。

### 客户端调用方式

- 复用现有封装：`frontend/mp-weixin/utils/runtime-segment.ts` 的 `reportRuntimeObservation()`。
- `page_path`：填当前页面路径（关于页或降级页面路径）。
- `entry_source`：固定值，建议使用 `about_contact_us`。
- `event_payload` 约束：
  - 仅包含布尔/短文本等标量字段，避免写入可识别的用户输入内容。
  - `fail_err_msg` 由客户端进行长度截断（例如 200 字符以内），服务端仍会进行 NFKC normalize + 控制字符清理 + 全局截断。

## 实施步骤（按顺序执行）

1) 文档调整（项目文档）
- 更新 `docs/spec/client/base/profile-and-settings.md` 与 `docs/spec/client/mini-program/prototype.md` 中“联系我们（公众号）”的实现描述：
  - 主链路为 `wx.openOfficialAccountProfile`
  - 降级链路为二维码长按识别 + 复制公众号用户名

2) 小程序侧实现
- 修改 `frontend/mp-weixin/pkg/about/about.ts`：
  - 将 `navigateToContactUs()` 改为“尝试打开公众号主页，否则展示降级 UI”。
  - 调用 `reportRuntimeObservation()` 上报 `official_account_follow_attempt` 与 `official_account_follow_fallback_shown`。
- UI 落地二选一：
  - 弹窗方案：复用 TDesign `t-dialog` 形态（参考 `frontend/mp-weixin/pages/login/login.wxml`）。
  - 页面方案：新增 `frontend/mp-weixin/pkg/contact-us/contact-us` 页面承载二维码与复制按钮。

UI 选型（本次推荐）：
- 优先选择“弹窗方案”（`t-dialog`）以减少页面跳转，缩短关注路径。
  - 弹窗内容：二维码图片（支持长按识别）+ 复制公众号用户名按钮 + 简短说明。
  - 仅在主链路不可用或调用失败时展示。

3) 配置补齐
- 在 `frontend/mp-weixin/utils/config.ts` 增加公众号配置（非 ASSET）与二维码路径（ASSET）：
  - 公众号配置：新配置对象（例如 `OFFICIAL_ACCOUNT_CONFIG.originalId` + `OFFICIAL_ACCOUNT_CONFIG.displayName`）
  - 二维码路径：纳入 `ASSET_CONFIG` 派生 URL

4) 后端白名单扩容
- 修改 `backend/app/api/v1/client.py`：追加两个事件名到白名单集合。

## 验收标准

- 在支持 `wx.openOfficialAccountProfile` 的基础库版本下：
  - 点击「联系我们」可以直接打开公众号主页。
  - `client_runtime_observations` 可看到 `official_account_follow_attempt` 事件（event_payload.method=open_profile）。
- 在不支持或调用失败场景下：
  - 会展示二维码与“复制公众号用户名”按钮。
  - 二维码支持长按菜单（含识别关注能力受基础库版本约束）。
  - `client_runtime_observations` 可看到 `official_account_follow_fallback_shown` 事件，包含截断后的 `fail_err_msg`。
 - 配置约束满足：
   - 小程序端不出现硬编码的 COS/CDN 资源 URL，二维码图片 URL 通过 `ASSET_CONFIG` 派生。
   - 新增 runtime observation 事件已加入后端白名单，接口返回 `accepted=true` 时会落库。

## 验证步骤

- 小程序真机/开发者工具验证：
  - 新版本基础库：验证主链路打开公众号主页。
  - 低版本/强制模拟 fail：验证降级 UI 与复制能力。
  - 二维码识别能力验证：基础库版本 >= 2.18.0 时，长按菜单应包含对“公众号二维码”的识别入口（以实际客户端表现为准）。
- 后端验证：
  - 使用管理端或数据库查询确认 `client_runtime_observations` 写入新增事件。
  - 检查新增事件的 `entry_source`、`page_path`、`event_payload` 字段符合约束（无用户输入、`fail_err_msg` 已截断）。
