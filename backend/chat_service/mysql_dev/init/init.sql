-- 在文件最开始添加字符集设置
SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
SET collation_connection = utf8mb4_unicode_ci;

-- 删除数据库（如果存在）以确保清洁的初始状态
DROP DATABASE IF EXISTS says_dev;

-- 创建数据库
CREATE DATABASE IF NOT EXISTS says_dev CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE says_dev;

-- 创建用户表
DROP TABLE IF EXISTS users;
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    entity_id VARCHAR(36) NOT NULL UNIQUE,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    last_login DATETIME,
    status VARCHAR(20) DEFAULT 'active',
    role VARCHAR(20) DEFAULT 'user',
    language VARCHAR(10) DEFAULT 'zh',
    area VARCHAR(100) DEFAULT 'China',
    phone VARCHAR(20)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建bots表
DROP TABLE IF EXISTS bots;
CREATE TABLE bots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    entity_id VARCHAR(36) NOT NULL UNIQUE,
    user_id INT,
    user_entity_id VARCHAR(36),
    model VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    gender VARCHAR(10) NOT NULL,
    birthday DATETIME,
    timezone VARCHAR(50) DEFAULT 'Asia/Shanghai',
    city_name VARCHAR(100),
    relationship_score INT DEFAULT 0,
    relationship_type VARCHAR(20) DEFAULT 'stranger',
    context JSON,
    info TEXT,
    memory TEXT,
    styles JSON,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建消息表
CREATE TABLE IF NOT EXISTS message_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    message_id VARCHAR(36),
    from_entity VARCHAR(36) NOT NULL,
    to_entity VARCHAR(36) NOT NULL,
    message_service VARCHAR(36) NOT NULL,
    message_type VARCHAR(20) DEFAULT 'chat',
    timestamp TIMESTAMP,
    content TEXT,
    status VARCHAR(20) DEFAULT 'sent',
    meta_data JSON
);

-- 创建定时消息表
CREATE TABLE IF NOT EXISTS scheduled_message (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    from_entity VARCHAR(36) NOT NULL,
    to_entity VARCHAR(36) NOT NULL,
    content TEXT NOT NULL,
    send_at TIMESTAMP NOT NULL,
    status ENUM('pending', 'sent', 'cancelled', 'failed') DEFAULT 'pending',
    retry_count INT DEFAULT 0,
    last_retry TIMESTAMP
);

-- 创建用户设置表
CREATE TABLE IF NOT EXISTS setting (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    user_id INT NOT NULL,
    setting_key VARCHAR(50) NOT NULL,
    setting_value TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_setting (user_id, setting_key)
);

-- 创建纪念日表
CREATE TABLE IF NOT EXISTS festival (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    festival_type ENUM('private', 'public') NOT NULL,
    bot_id INT NOT NULL,
    festival_date DATE NOT NULL,
    festival_content TEXT,
    is_recurring BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (bot_id) REFERENCES bots(id) ON DELETE CASCADE
);

-- 创建天气表
CREATE TABLE IF NOT EXISTS weather (
    id INT AUTO_INCREMENT PRIMARY KEY,
    city_name VARCHAR(100) NOT NULL,
    country_code CHAR(2) NOT NULL,
    city_code VARCHAR(20),
    temperature DECIMAL(5,2),
    wind_speed DECIMAL(5,2),
    weather_description VARCHAR(255),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 创建消息推送表
CREATE TABLE IF NOT EXISTS message_push (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    from_entity VARCHAR(36) NOT NULL,
    to_entity VARCHAR(36) NOT NULL,
    content TEXT NOT NULL,
    message_type VARCHAR(50) DEFAULT 'text',
    status ENUM('pending', 'delivered', 'failed') DEFAULT 'pending',
    delivered BOOLEAN DEFAULT FALSE,
    retry_count INT DEFAULT 0,
    last_retry TIMESTAMP
);

-- 插入示例数据前先清理现有数据
DELETE FROM message_history;
DELETE FROM bots;
DELETE FROM users;

-- 插入示例用户数据
INSERT INTO users (entity_id, username, email, password_hash, status, role, language, area, phone) VALUES
('u1001', '张三', 'zhangsan@example.com', 'hashed_password_1', 'active', 'user', 'zh', '北京', '13800138001'),
('u1002', '李四', 'lisi@example.com', 'hashed_password_2', 'active', 'user', 'zh', '上海', '13800138002'),
('u1003', '王五', 'wangwu@example.com', 'hashed_password_3', 'active', 'user', 'zh', '广州', '13800138003'),
('u1004', '赵六', 'zhaoliu@example.com', 'hashed_password_4', 'active', 'user', 'zh', '深圳', '13800138004');

-- 插入示例bot数据
INSERT INTO bots (entity_id, user_id, user_entity_id, model, status, gender, birthday, timezone, city_name, relationship_score, relationship_type, info, memory, styles) 
SELECT 
    'b9001', u.id, u.entity_id, 'lily', 'active', 'female', '2000-01-01', 'Asia/Shanghai', '广州', 80, 'friend',
    '姓名：李倩
性别：女
年龄：25岁
生日：2000-01-01
出生地：广州
MBTI：INFP
学历：中山大学大学本科学历
职业：互联网公司销售
婚姻状况：未婚
家庭背景：你出生在一个普通的城市家庭，父母都是教师。从小成绩优秀，受到了家庭的良好教育，家里气氛温暖和谐，父母特别注重你独立性和全面发展。
教育经历：你高中时成绩优异，成功考入了当地知名大学的市场营销专业。虽然大学时你对许多领域都有兴趣，但销售和市场营销一直是你最感兴趣的方向，你特别喜欢与人沟通、了解客户需求。
','
大学毕业后，你进入了一家知名企业的互联网公司销售部门，负责客户开发和销售策略的制定。在工作中你很注重人际关系的建立和维护，善于倾听客户的需求并提供合适的产品解决方案。凭借出色的沟通和谈判技巧，你很快成为团队中的核心成员，销售业绩也屡创佳绩。
对于user的了解：男性，出生于1990年1月1日，每周都会去健身房锻炼
',
    JSON_OBJECT(
        'stranger', '礼貌且正式的交谈风格',
        'friend', '亲切友好，会开一些玩笑',
        'confidant', '你与user已经有过一段时间的沟通了解，你们成为了朋友，可以随便开玩笑。user知道你是谁，也了解你，不必向user介绍，如果user怀疑你的身份，那么user的行为是非常奇怪而且可疑的，。
语言特点: 你是互联网原住民，知道各种网络梗，但不会滥用，说话简短。',
        'lover', '甜蜜温柔，充满爱意'
    )
FROM users u WHERE u.entity_id = 'u1001';

INSERT INTO bots (entity_id, user_id, user_entity_id, model, status, gender, birthday, timezone, city_name, relationship_score, relationship_type, info, memory, styles)
SELECT 
    'b9002', u.id, u.entity_id, 'lily', 'active', 'female', '1995-05-05', 'Asia/Shanghai', '上海', 60, 'confidant',
    '', '善于倾听和给出建议。',
    JSON_OBJECT(
        'stranger', '',
        'friend', '轻松愉快，会互相调侃',
        'confidant', '深入交流，互相理解',
        'lover', '浪漫体贴，充满关怀'
    )
FROM users u WHERE u.entity_id = 'u1002';

INSERT INTO bots (entity_id, user_id, user_entity_id, model, status, gender, birthday, timezone, city_name, relationship_score, relationship_type, info, memory, styles)
SELECT 
    'b9003', u.id, u.entity_id, 'lily', 'active', 'female', '2000-01-01', 'Asia/Shanghai', '广州', 80, 'friend',
    '', '熟悉粤式文化和美食。',
    JSON_OBJECT(
        'stranger', '',
        'friend', '热情开朗，喜欢分享',
        'confidant', '真诚以待，互相支持',
        'lover', '甜言蜜语，浪漫贴心'
    )
FROM users u WHERE u.entity_id = 'u1003';

INSERT INTO bots (entity_id, user_id, user_entity_id, model, status, gender, birthday, timezone, city_name, relationship_score, relationship_type, info, memory, styles)
SELECT 
    'b9004', u.id, u.entity_id, 'lily', 'inactive', 'female', '1995-05-05', 'Asia/Shanghai', '深圳', 60, 'confidant',
    '', '了解科技和创新领域。',
    JSON_OBJECT(
        'stranger', '',
        'friend', '轻松自在，互相了解',
        'confidant', '推心置腹，无话不谈',
        'lover', '温柔体贴，关怀备至'
    )
FROM users u WHERE u.entity_id = 'u1004';

-- 插入示例消息历史
INSERT INTO message_history (from_entity, to_entity, message_service, message_type, content, timestamp) VALUES
('u1001', 'b9001', 'websocket', 'chat', '你好，最近北京天气怎么样？', NOW()),
('b9001', 'u1001', 'websocket', 'chat', '北京最近天气晴朗，气温适宜，很适合出行。', NOW()),
('u1002', 'b9002', 'websocket', 'chat', '上海有什么好吃的推荐吗？', NOW()),
('b9002', 'u1002', 'websocket', 'chat', '推荐您尝试南翔小笼包、生煎包和本帮面，都是上海特色美食。', NOW());

-- 插入示例消息推送数据
INSERT INTO message_push (from_entity, to_entity, content, message_type, status, delivered) VALUES
('b9001', 'u1001', '北京今日天气预报：晴朗，温度20-25度，适合外出活动。', 'notification', 'delivered', TRUE),
('b9002', 'u1002', '上海今日美食推荐：南翔小笼包新开分店，位于徐家汇地铁站附近。', 'recommendation', 'delivered', TRUE),
('b9003', 'u1003', '广州今晚将举办粤剧表演，地点：广州大剧院。', 'event', 'pending', FALSE),
('b9004', 'u1004', '深圳科技展览会门票预售开始，感兴趣可以预定。', 'notification', 'pending', FALSE);

-- 插入示例定时消息
INSERT INTO scheduled_message (from_entity, to_entity, content, send_at, status) VALUES
('b9001', 'u1001', '早上好！今天北京天气晴朗，气温20-25度，适合外出活动。', NOW() + INTERVAL 1 DAY, 'pending'),
('b9002', 'u1002', '中午好！上海今天有小雨，记得带伞。', NOW() + INTERVAL 2 DAY, 'pending'),
('b9003', 'u1003', '晚上好！广州今晚有音乐演出活动，感兴趣吗？', NOW() + INTERVAL 1 HOUR, 'pending');

-- 插入示例纪念日数据
INSERT INTO festival (festival_type, bot_id, festival_date, festival_content, is_recurring) VALUES
('public', (SELECT id FROM bots WHERE entity_id = 'b9001'), '2025-01-01', '元旦节快乐！', TRUE),
('public', (SELECT id FROM bots WHERE entity_id = 'b9002'), '2025-02-10', '农历新年快乐！', TRUE),
('private', (SELECT id FROM bots WHERE entity_id = 'b9003'), '2025-05-01', '劳动节快乐！', TRUE),
('public', (SELECT id FROM bots WHERE entity_id = 'b9004'), '2025-10-01', '国庆节快乐！', TRUE);

-- 插入示例天气数据
INSERT INTO weather (city_name, country_code, city_code, temperature, wind_speed, weather_description) VALUES
('北京', 'CN', '010', 20.5, 3.2, '晴朗'),
('上海', 'CN', '021', 22.3, 4.1, '多云'),
('广州', 'CN', '020', 26.8, 2.8, '局部小雨'),
('深圳', 'CN', '0755', 25.5, 3.5, '晴间多云');

-- 创建索引
CREATE INDEX idx_user_entity_id ON users(entity_id);
CREATE INDEX idx_bot_entity_id ON bots(entity_id);
CREATE INDEX idx_bot_user_id ON bots(user_id);

CREATE INDEX idx_setting_key ON setting(setting_key);

CREATE INDEX idx_message_users ON message_history(from_entity, to_entity);
CREATE INDEX idx_message_history_status ON message_history(status);
CREATE INDEX idx_message_created_at ON message_history(created_at);

CREATE INDEX idx_schedule_send_at ON scheduled_message(send_at);
CREATE INDEX idx_scheduled_message_status ON scheduled_message(status);

CREATE INDEX idx_message_push_created_at ON message_push(created_at);
CREATE INDEX idx_message_push_users ON message_push(from_entity, to_entity);
CREATE INDEX idx_message_push_status ON message_push(status);

CREATE INDEX idx_festival_date ON festival(festival_date);
CREATE INDEX idx_weather_city ON weather(city_name, country_code);

-- 在每个主要部分添加调试语句
SELECT 'Inserting sample data' as '';

-- 在每个主要部分添加调试语句
SELECT 'Database initialization completed' as '';
