# 统计数据系统技术文档

## 概述

本文档定义系统统计数据的计算规则、概念定义和实施范围，确保统计数据的一致性和可追溯性。

## 统计表结构

### 维度和粒度

系统设计了3个维度 × 3个粒度 = 9张统计表：

| 维度 | 日统计 | 周统计 | 月统计 |
|------|--------|--------|--------|
| **用户** | `stats_user_daily` | `stats_user_weekly` | `stats_user_monthly` |
| **消息** | `stats_message_daily` | `stats_message_weekly` | `stats_message_monthly` |
| **AI** | `stats_ai_daily` | `stats_ai_weekly` | `stats_ai_monthly` |

### 表设计原则

- **不可变性**: 统计表继承自 `ImmutableAutoIncrementModel`，一旦生成不可修改
- **唯一性**: `stat_date` 字段有 `UNIQUE` 约束，保证同一日期只有一条记录
- **只读性**: 管理后台中统计表视图禁止增删改操作

## 核心概念定义

### 1. 时间范围定义

#### Daily（日统计）
- **统计日期**: 自然日，使用 UTC 时区
- **时间范围**: `[YYYY-MM-DD 00:00:00, YYYY-MM-DD 23:59:59]` (UTC)
- **stat_date 值**: 统计日期当天，如 `2025-01-15`
- **计算时机**: 每天 UTC 01:00 统计前一天的数据

**示例**:
- `stat_date = 2025-01-15` 表示统计 2025-01-15 00:00:00 至 2025-01-15 23:59:59 (UTC) 的数据

#### Weekly（周统计）
- **统计日期**: 自然周的周一日期（ISO 8601标准）
- **时间范围**: `[周一 00:00:00, 周日 23:59:59]` (UTC)
- **stat_date 值**: 该周的周一日期，如 `2025-01-13`（周一）
- **计算时机**: 每周一 UTC 02:00 统计上一周的数据

**示例**:
- `stat_date = 2025-01-13` 表示统计 2025-01-13 至 2025-01-19 这一周的数据
- 跨年周归属于包含更多天数的年份（ISO 8601 标准）

#### Monthly（月统计）
- **统计日期**: 自然月的第一天
- **时间范围**: `[YYYY-MM-01 00:00:00, YYYY-MM-最后一天 23:59:59]` (UTC)
- **stat_date 值**: 该月的第一天，如 `2025-01-01`
- **计算时机**: 每月1日 UTC 03:00 统计上一月的数据

**示例**:
- `stat_date = 2025-01-01` 表示统计 2025-01-01 至 2025-01-31 整月的数据

### 2. "活跃"定义

#### 活跃用户 (active_users)

用户在统计期间内满足以下**任一条件**即视为活跃：

1. **登录行为**: 在 `login_records` 表中有登录记录（`result = 1` 成功登录）
2. **消息行为**: 在 `message_history` 表中作为发送方发送过消息

**计算公式**:
```sql
SELECT COUNT(DISTINCT user_id)
FROM (
    -- 登录用户
    SELECT user_id FROM login_records
    WHERE login_time >= :start_time
      AND login_time < :end_time
      AND result = 1
    UNION
    -- 发送消息用户
    SELECT from_id as user_id FROM message_history
    WHERE created_at >= :start_time
      AND created_at < :end_time
      AND from_type = 1  -- EntityType.USER
) active_users;
```

**注意事项**:
- 仅统计成功登录（`result = 1`），失败登录不计入
- 接收消息不算活跃，只有发送消息才算
- 使用 `DISTINCT` 去重，同一用户在统计期间内多次活跃只计一次

#### 活跃对话 (active_conversations)

对话在统计期间内有消息往来即视为活跃。

**计算公式**:
```sql
SELECT COUNT(DISTINCT conversation_id)
FROM message_history
WHERE created_at >= :start_time
  AND created_at < :end_time;
```

**注意事项**:
- 不区分发送方和接收方
- 单向消息也算活跃对话（无需双向互动）

#### 活跃AI实例 (active_ai_instances)

AI 实例在统计期间内产生过对话（作为消息接收方）即视为活跃。

**计算公式**:
```sql
SELECT COUNT(DISTINCT to_id)
FROM message_history
WHERE created_at >= :start_time
  AND created_at < :end_time
  AND to_type = 2;  -- EntityType.AI
```

**注意事项**:
- 仅统计作为接收方的 AI 实例
- AI 实例主动发送消息不单独统计（因为必然先收到用户消息）

### 3. 累计指标 vs 增量指标

#### 累计指标（Cumulative Metrics）

**定义**: 从系统上线至统计日期的累计总数

**字段**:
- `total_users`: 总用户数（截至 stat_date 的所有注册用户）
- `ai_instances`: AI 实例总数（截至 stat_date 的所有活跃实例）

**计算方式**:
```sql
-- 总用户数
SELECT COUNT(*) FROM users
WHERE created_at <= :stat_date_end;

-- AI实例总数
SELECT COUNT(*) FROM ai_instances
WHERE created_at <= :stat_date_end
  AND status = 1;  -- 仅统计活跃状态
```

#### 增量指标（Incremental Metrics）

**定义**: 仅统计期间内的新增数据

**字段**:
- `new_users`: 新增用户数（该统计期间内注册的用户）
- `total_messages`: 总消息数（该统计期间内发送的消息）
- `ai_requests_count`: AI 请求总数（该统计期间内的 LLM 请求）

**计算方式**:
```sql
-- 新增用户数
SELECT COUNT(*) FROM users
WHERE created_at >= :start_time
  AND created_at < :end_time;

-- 总消息数
SELECT COUNT(*) FROM message_history
WHERE created_at >= :start_time
  AND created_at < :end_time;

-- AI请求总数
SELECT COUNT(*) FROM ai_request_logs
WHERE created_at >= :start_time
  AND created_at < :end_time;
```

### 4. 人均指标计算

#### 人均消息数 (avg_messages_per_user)

**定义**: 统计期间内的总消息数除以活跃用户数

**计算公式**:
```python
avg_messages_per_user = (
    total_messages / active_users if active_users > 0 else 0
)
```

**精度**: 保留2位小数（DECIMAL(10,2)）

**注意事项**:
- 分母为0时返回0（避免除零错误）
- 使用活跃用户数而非总用户数作为分母
- 四舍五入到小数点后2位

#### 人均AI请求数 (avg_ai_requests_per_user)

**定义**: 统计期间内的 AI 请求总数除以活跃用户数

**计算公式**:
```python
avg_ai_requests_per_user = (
    ai_requests_count / active_users if active_users > 0 else 0
)
```

**精度**: 保留2位小数（DECIMAL(10,2)）

**注意事项**:
- 统计所有 LLM 请求，包括成功和失败的请求
- 使用活跃用户数作为分母（与消息统计保持一致）

## 实施状态

### 当前状态 (MVP阶段)

**已完成**:
- ✅ 数据库表结构设计
- ✅ SQLAlchemy 模型定义
- ✅ 管理后台只读视图
- ✅ CRUD 操作接口（仅查询）

**未实施**:
- ❌ 定时任务系统
- ❌ 统计计算逻辑
- ❌ 数据回填功能
- ❌ 统计任务监控

**当前限制**:
- 所有统计表为空表，无数据写入
- 管理后台可以查看表结构但无数据展示

### 实施计划

#### 阶段1: 定时任务基础设施 (MVP 后期)

**目标**: 建立统计数据自动生成能力

**技术方案**: APScheduler (轻量级方案)

**实施内容**:
1. 引入 APScheduler 依赖
2. 创建 `app/tasks/statistics.py` 模块
3. 实现基础统计计算函数
4. 在 FastAPI 启动时注册定时任务

**优先级**:
- P0: 用户统计（核心运营指标）
- P1: 消息统计（产品核心功能）
- P1: AI 统计（技术运营关键）

#### 阶段2: 数据质量保障

**实施内容**:
1. 统计前数据有效性检查
2. 计算后结果合理性校验
3. 异常值自动告警机制
4. 手动触发和历史回填功能

#### 阶段3: 分布式任务系统（生产环境）

**技术方案**: 分布式任务队列 + 共享持久化存储（按生产基础设施选型）

**实施内容**:
1. 支持多副本部署
2. 任务持久化和重试
3. 分布式锁防止重复计算
4. 实时统计能力（共享缓存或物化视图）

## 预留字段

### 订阅相关字段

以下字段已在表结构中定义，但暂未实施：

- `subscriptions`: 总订阅用户数
- `new_subscriptions`: 新订阅用户数
- `canceled_subscriptions`: 退订用户数

**实施条件**:
- 需先建立订阅系统（`subscriptions` 表）
- 需先建立订单系统（`orders` 表）
- 需先建立支付系统（`payments` 表）

**预期时间**: 有付费用户需求后实施

## 数据质量保障

### 1. 数据一致性检查

**原则**: 统计数据必须与源数据表保持一致

**检查项**:
```sql
-- 检查1: 总用户数应等于 users 表累计数
SELECT
    (SELECT total_users FROM stats_user_daily WHERE stat_date = :date) AS stats_total,
    (SELECT COUNT(*) FROM users WHERE created_at <= :date_end) AS actual_total;

-- 检查2: 新增用户数应等于 users 表当日注册数
SELECT
    (SELECT new_users FROM stats_user_daily WHERE stat_date = :date) AS stats_new,
    (SELECT COUNT(*) FROM users
     WHERE created_at >= :date_start AND created_at < :date_end) AS actual_new;
```

### 2. 合理性校验

**校验规则**:
- 总用户数应单调递增（不会减少）
- 新增用户数 >= 0
- 活跃用户数 <= 总用户数
- 人均消息数应在合理范围内（如 0-1000）

### 3. 异常告警

**告警条件**:
- 统计计算失败
- 数据一致性检查失败
- 指标异常波动（如新增用户数突增10倍）

**告警方式**:
- 系统日志记录
- 管理员邮件通知（生产环境）

## 查询性能优化

### 索引策略

**已有索引**:
- `stat_date`: UNIQUE 索引（自动创建）

**查询优化**:
- 按日期范围查询: 使用 `stat_date BETWEEN :start AND :end`
- 最新数据查询: 使用 `ORDER BY stat_date DESC LIMIT N`

### 分区策略（未来）

当数据量增长到一定规模后（如每张表超过100万行），考虑：
- 按年份分区（Partition by year）
- 或迁移到时序数据库（TimescaleDB/ClickHouse）

## 附录

### A. 数据源表映射

| 统计指标 | 数据源表 | 关键字段 |
|---------|---------|---------|
| total_users | users | created_at |
| new_users | users | created_at |
| active_users | login_records, message_history | login_time, created_at |
| total_messages | message_history | created_at |
| active_conversations | message_history | conversation_id |
| ai_instances | ai_instances | created_at, status |
| active_ai_instances | message_history | to_id, to_type |
| ai_requests_count | ai_request_logs | created_at |

### B. 时区处理

**原则**: 所有时间戳统一使用 UTC 时区

**数据库存储**: `TIMESTAMP WITH TIME ZONE` 类型，存储 UTC 时间

**统计计算**: 使用 UTC 时间范围进行过滤

**前端展示**: 根据用户时区进行转换（由前端处理）

### C. 历史数据回填

**场景**: 统计系统上线后需要回填历史数据

**实施方式**:
```python
async def backfill_statistics(start_date: date, end_date: date):
    """回填指定日期范围的统计数据"""
    current_date = start_date
    while current_date <= end_date:
        # 检查是否已存在
        existing = await get_stats_by_date(current_date)
        if existing:
            logger.info(f"Stats for {current_date} already exists, skipping")
        else:
            # 计算并插入
            await calculate_and_save_daily_stats(current_date)
        current_date += timedelta(days=1)
```

**注意事项**:
- 回填前需检查源数据完整性
- 按时间顺序回填（从早到晚）
- 回填过程中监控数据库性能
- 回填后进行数据一致性检查
