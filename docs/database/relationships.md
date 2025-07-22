# 数据关系说明

## 实体关系概览

### 核心实体

- **User**: 用户账号实体
- **Bot**: AI机器人实体  
- **Contact**: 联系人关系
- **Message**: 消息记录
- **SocialProfile**: 社交档案

### 关系类型

- **一对一**: User ↔ SocialProfile
- **一对多**: User → Contacts, Bot → Messages
- **多对多**: User ↔ Bot (通过Contacts表)

## 详细关系说明

### 用户与社交档案

```
users.entity_id ←→ social_profiles.entity_id
```

- 每个用户对应一个社交档案
- 社交档案存储显示信息（昵称、头像、简介等）
- 用户基础信息与显示信息分离

### 用户与联系人

```
users.entity_id → contacts.user_entity_id
contacts.contact_entity_id ← bots.entity_id | users.entity_id
```

- 用户可以添加其他用户或机器人为联系人
- contact_type 区分联系人类型（1=用户，2=机器人）
- 支持双向联系人关系

### 机器人与消息

```
bots.entity_id → message_history.from_entity
users.entity_id → message_history.to_entity
```

- 机器人可以发送消息给用户
- 用户可以发送消息给机器人
- 消息记录包含完整的对话历史

### 机器人与情感状态

```
bots.entity_id → emotions.bot_entity_id
users.entity_id → emotions.user_entity_id
```

- 每个机器人对每个用户维护独立的情感状态
- 支持多种情感类型（友谊、浪漫等）
- 情感分数影响机器人行为

### LeanCloud对话映射

```
users.entity_id → conversation_mappings.entity_id
bots.entity_id → conversation_mappings.entity_id
```

- 将内部entity_id映射到LeanCloud conversation_id
- 支持系统对话和用户对话
- 统一对话ID管理

## 查询模式

### 联系人列表查询

```sql
-- 获取用户的所有联系人
SELECT c.contact_entity_id, c.contact_type, sp.nickname, sp.avatar_url
FROM contacts c
LEFT JOIN social_profiles sp ON c.contact_entity_id = sp.entity_id
WHERE c.user_entity_id = 'qqid_u1001'
AND c.status = 'active';
```

### 消息历史查询

```sql
-- 获取用户与特定联系人的消息历史
SELECT from_entity, to_entity, content, message_time
FROM message_history
WHERE (from_entity = 'qqid_u1001' AND to_entity = 'qqid_b9001')
   OR (from_entity = 'qqid_b9001' AND to_entity = 'qqid_u1001')
ORDER BY message_time DESC
LIMIT 50;
```

### 情感状态查询

```sql
-- 获取机器人对用户的情感状态
SELECT emotion_type, score
FROM emotions
WHERE bot_entity_id = 'qqid_b9001'
AND user_entity_id = 'qqid_u1001';
```

## 数据完整性

### 应用层约束

- entity_id 全局唯一性检查
- 联系人关系有效性验证
- 消息发送权限检查

### 清理策略

- 软删除：标记status为inactive
- 定期清理：过期数据归档
- 级联更新：通过应用逻辑处理

### 备份恢复

- 按服务分别备份
- 支持增量备份
- 跨服务数据一致性验证
