# AI 实例 qiao_id / 资料缺失问题跟踪

## 背景
- 在小程序发现页添加 AI 后，创建出的实例 `qiao_id` 与 persona 不一致，导致资料缺失（例：`qiao_6AzL8FNL4l2ClR3Z` 查无 profile）。
- 规格要求实例继承 persona 的 `qiao_id`，Profile 通过 `owner_qiao_id=persona.qiao_id`（owner_type=2）提供展示数据。

## 发现的问题
1) **实例 qiao_id 生成错误（主因）**
   - `backend/app/services/ai/instance_creation.py:create_instance_from_persona` 未传入 qiao_id。
   - `backend/app/schemas/ai/instance.py:AIInstanceCreate` 无 qiao_id 字段。
   - `AIInstance` 继承 `QiaoIDMixin`，自动生成新 qiao_id → 与 persona qiao_id 不一致 → Profile 查询失败。
2) **Profile 查询缺少防御**
   - `services/ai/queries/profile_queries.get_instance_profile` 假定 instance_qiao_id 能命中 profile，查不到时仅 warning；profile owner_qiao_id 已 UNIQUE，按 qiao_id 唯一查即可。
3) **手动实例 Profile 责任不清**
   - 规格：手动创建实例拥有独立 profile（owner_type=3）。代码 `create_instance_with_relations` 目前硬编码 owner_type=2，语义不符。
4) **规则补充**
   - 严格禁止任何向后兼容。
   - 移除或替换内容要彻底干净，不保留“已废弃/不再使用”类残留文档或注释。

## 影响
- 所有通过联系人请求创建的 AI 实例都会生成错误的 qiao_id，导致资料缺失（头像、昵称、性别、简介等）。
- 由于查询沉默失败，问题不易被监控捕获。

## 修复方案（代码）
1) **强制实例继承 persona qiao_id（必要）**
   - `AIInstanceCreate` 增加必填 `qiao_id: str (<=32)`。
   - `create_instance_from_persona` 构造时传入 `qiao_id=persona.qiao_id`；创建后断言一致，不一致直接报错。
   - `CRUDAIInstance.create` 校验 qiao_id 必填且长度合法，禁止回退默认生成。
2) **查询防御与可观测性**
   - `get_instance_profile` / `get_instance_context` 未命中 profile 时输出 error 日志，携带 `instance_qiao_id`；可选：查不到时直接 500/告警。
   - 查询按 `owner_qiao_id = instance_qiao_id` 唯一匹配，owner_type 限定 {2,3}，不符告警（捕捉写入模式错误）。
3) **手动实例 profile**
   - 手动实例固定独立资料：`create_instance_with_relations` 写入 owner_type=3，不提供继承 persona 资料的开关。

## 数据修复方案（一次性）
步骤需写权限，建议事务/脚本执行：
1) 找出 `ai_instances` 中 `qiao_id != creation_metadata->>'persona_qiao_id'` 的行。
2) 将这些行的 `qiao_id` 回写为 `creation_metadata->>'persona_qiao_id'`。
3) 同步更新引用 instance_qiao_id 的表（至少）：
   - `contacts.contact_qiao_id`
   - `ai_conversation_state`
   - `ai_message_buffer`
   - `ai_conversation_items` / `ai_conversation_items_archive`
   - `ai_instance_memories`
   - `user_violation_logs`
   - 其他使用 `instance_qiao_id` 的消息/统计表（需全局 grep/确认）。
4) 修复后抽查：按实例 qiao_id 查询 profile，确认命中；必要时重建相关缓存/索引。

### 参考 SQL（请在事务中执行，并先备份）
```sql
-- 1) 找出并回写 ai_instances.qiao_id
WITH mismatched AS (
    SELECT id, qiao_id AS old_qiao_id, creation_metadata->>'persona_qiao_id' AS persona_qiao_id
    FROM ai_instances
    WHERE qiao_id IS NOT NULL
      AND creation_metadata ? 'persona_qiao_id'
      AND qiao_id <> creation_metadata->>'persona_qiao_id'
)
UPDATE ai_instances ai
SET qiao_id = m.persona_qiao_id
FROM mismatched m
WHERE ai.id = m.id;

-- 2) 同步引用表（示例，依次执行）
UPDATE contacts c
SET contact_qiao_id = m.persona_qiao_id
FROM mismatched m
WHERE c.contact_qiao_id = m.old_qiao_id;

UPDATE ai_conversation_state s
SET instance_qiao_id = m.persona_qiao_id
FROM mismatched m
WHERE s.instance_qiao_id = m.old_qiao_id;

UPDATE ai_message_buffer b
SET instance_qiao_id = m.persona_qiao_id
FROM mismatched m
WHERE b.instance_qiao_id = m.old_qiao_id;

UPDATE ai_conversation_items i
SET instance_qiao_id = m.persona_qiao_id
FROM mismatched m
WHERE i.instance_qiao_id = m.old_qiao_id;

UPDATE ai_conversation_items_archive a
SET instance_qiao_id = m.persona_qiao_id
FROM mismatched m
WHERE a.instance_qiao_id = m.old_qiao_id;

UPDATE ai_instance_memories im
SET instance_qiao_id = m.persona_qiao_id
FROM mismatched m
WHERE im.instance_qiao_id = m.old_qiao_id;

UPDATE user_violation_logs u
SET instance_qiao_id = m.persona_qiao_id
FROM mismatched m
WHERE u.instance_qiao_id = m.old_qiao_id;
```

## 验证清单
- 新增/修改的实例创建路径：实例 qiao_id == persona qiao_id。
- Profile 查询：按 qiao_id 唯一命中 profile，资料正常返回；owner_type 不在 {2,3} 时有告警。
- 日志：未命中 profile 时输出 error，带 instance_qiao_id。
- 现有错误数据经修复后，联系人页面资料正常展示。
