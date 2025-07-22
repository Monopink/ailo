# 数据库表结构

## 核心表设计

### users (账号服务专用)

用户账号基础信息表

```sql
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    created_at DATETIME,
    updated_at DATETIME,
    entity_id VARCHAR(20) UNIQUE NOT NULL,
    phone VARCHAR(20) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    username VARCHAR(50),
    email VARCHAR(100),
    status VARCHAR(20) DEFAULT 'active',
    role VARCHAR(20) DEFAULT 'user',
    is_verified BOOLEAN DEFAULT FALSE,
    subscription_type VARCHAR(20) DEFAULT 'free',
    last_login DATETIME,
    language VARCHAR(10) DEFAULT 'zh',
    area VARCHAR(100) DEFAULT 'China'
);
```

### bots (消息服务专用)

AI机器人配置信息表

```sql
CREATE TABLE bots (
    id INT PRIMARY KEY AUTO_INCREMENT,
    created_at DATETIME,
    updated_at DATETIME,
    entity_id VARCHAR(20) UNIQUE NOT NULL,
    user_entity_id VARCHAR(20),
    model VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    gender VARCHAR(10) NOT NULL,
    birthday DATETIME,
    timezone VARCHAR(50) DEFAULT 'Asia/Shanghai',
    city_name VARCHAR(100),
    friend_score INT DEFAULT 0,
    romance_score INT DEFAULT 0,
    friend_score_cap INT DEFAULT 5000,
    friend_score_floor INT DEFAULT 0,
    romance_score_cap INT DEFAULT 5000,
    friend_config JSON,
    romance_config JSON,
    override_config JSON,
    emotions_config JSON,
    is_polite TINYINT(1) DEFAULT 1,
    is_crushing TINYINT(1) DEFAULT 0,
    info TEXT,
    memory TEXT
);
```

### social_profiles (联系人服务专用)

统一社交档案数据表

```sql
CREATE TABLE social_profiles (
    id INT PRIMARY KEY AUTO_INCREMENT,
    created_at DATETIME,
    updated_at DATETIME,
    entity_id VARCHAR(20) UNIQUE NOT NULL,
    nickname VARCHAR(50),
    bio TEXT,
    avatar_url VARCHAR(500),
    birth_date DATE,
    location VARCHAR(100),
    gender VARCHAR(10),
    interests JSON,
    preferences JSON
);
```

### contacts (联系人服务专用)

用户联系人关系表

```sql
CREATE TABLE contacts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    created_at DATETIME,
    updated_at DATETIME,
    user_entity_id VARCHAR(20) NOT NULL,
    contact_entity_id VARCHAR(20) NOT NULL,
    contact_type INT NOT NULL,
    added_at DATETIME,
    status VARCHAR(20) DEFAULT 'active',
    last_interaction DATETIME,
    UNIQUE KEY unique_contact (user_entity_id, contact_entity_id)
);
```

### conversation_mappings (联系人服务专用)

LeanCloud对话ID映射表

```sql
CREATE TABLE conversation_mappings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    created_at DATETIME,
    updated_at DATETIME,
    entity_id VARCHAR(20) NOT NULL,
    conversation_id VARCHAR(100) NOT NULL,
    conversation_type VARCHAR(20) DEFAULT 'system',
    status VARCHAR(20) DEFAULT 'active',
    UNIQUE KEY unique_mapping (entity_id, conversation_type)
);
```

### message_history (消息服务专用)

消息历史记录表

```sql
CREATE TABLE message_history (
    id INT PRIMARY KEY AUTO_INCREMENT,
    created_at DATETIME,
    updated_at DATETIME,
    message_id_client VARCHAR(255),
    from_entity VARCHAR(36) NOT NULL,
    to_entity VARCHAR(36) NOT NULL,
    content TEXT NOT NULL,
    message_type VARCHAR(20) DEFAULT 'chat',
    message_service VARCHAR(36) NOT NULL,
    message_time DATETIME,
    status VARCHAR(20) DEFAULT 'sent',
    message_metadata JSON
);
```

### emotions (消息服务专用)

情感状态跟踪表

```sql
CREATE TABLE emotions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    created_at DATETIME,
    updated_at DATETIME,
    bot_entity_id VARCHAR(20) NOT NULL,
    user_entity_id VARCHAR(20) NOT NULL,
    emotion_type VARCHAR(50) NOT NULL,
    score INT DEFAULT 0,
    context TEXT,
    UNIQUE KEY unique_emotion (bot_entity_id, user_entity_id, emotion_type)
);
```

### template_mappings (联系人服务专用)

联系人模板映射表

```sql
CREATE TABLE template_mappings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    created_at DATETIME,
    updated_at DATETIME,
    template_id VARCHAR(50) NOT NULL,
    entity_id VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    UNIQUE KEY unique_template_mapping (template_id, entity_id)
);
```

### bot_templates (联系人服务专用)

机器人模板配置表

```sql
CREATE TABLE bot_templates (
    id INT PRIMARY KEY AUTO_INCREMENT,
    created_at DATETIME,
    updated_at DATETIME,
    template_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    category VARCHAR(50),
    config JSON,
    status VARCHAR(20) DEFAULT 'active'
);
```

## 设计原则

### 无外键约束

- 避免数据库层面的服务耦合
- 使用应用层逻辑管理数据关系
- 便于服务独立部署和扩展

### Entity ID 系统

- 所有表使用 entity_id 作为业务主键
- 格式：`qqid_{type}{number}`
- 全局唯一，字符串类型
- 不暴露数据库自增ID

### JSON 配置字段

- 机器人配置使用JSON存储，提供灵活性
- 情感系统配置支持动态调整
- 用户偏好和兴趣使用JSON格式
