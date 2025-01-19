-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS says_dev;
USE says_dev;

-- 创建用户表
CREATE TABLE IF NOT EXISTS user (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    status ENUM('active', 'inactive', 'banned') DEFAULT 'active',
    role ENUM('user', 'admin', 'moderator') DEFAULT 'user',
    language VARCHAR(10) DEFAULT 'zh',
    area VARCHAR(100) DEFAULT 'China',
    phone VARCHAR(20)
);

-- 创建bot表
CREATE TABLE IF NOT EXISTS bot (
    id INT PRIMARY KEY,
    model VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    status ENUM('active', 'sleep', 'inactive') DEFAULT 'active',
    gender ENUM('male', 'female', 'other') NOT NULL,
    birth_date DATE,
    time_zone VARCHAR(10) DEFAULT '+8:00',
    city_name VARCHAR(100),
    user_id INT,
    relationship_score INT DEFAULT 0,
    relationship_type ENUM('stranger', 'friend', 'confidant', 'lover') DEFAULT 'stranger',
    long_term_memory TEXT,
    short_term_memory TEXT,
    stranger_style TEXT,
    friend_style TEXT,
    confidant_style TEXT,
    lover_style TEXT,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE SET NULL
);

-- 创建消息表
CREATE TABLE IF NOT EXISTS message_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    from_id VARCHAR(36) NOT NULL,
    to_id VARCHAR(36) NOT NULL,
    content TEXT NOT NULL,
    content_overview VARCHAR(255),
    message_type VARCHAR(50) DEFAULT 'text',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    status ENUM('sent', 'delivered', 'read', 'failed') DEFAULT 'sent',
    metadata JSON
);

-- 创建定时消息表
CREATE TABLE IF NOT EXISTS scheduled_message (
    id VARCHAR(36) PRIMARY KEY,
    from_id VARCHAR(36) NOT NULL,
    to_id VARCHAR(36) NOT NULL,
    content TEXT NOT NULL,
    send_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    status ENUM('pending', 'sent', 'cancelled', 'failed') DEFAULT 'pending',
    retry_count INT DEFAULT 0,
    last_retry TIMESTAMP,
    metadata JSON
);

-- 创建用户设置表
CREATE TABLE IF NOT EXISTS setting (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    setting_key VARCHAR(50) NOT NULL,
    setting_value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_setting (user_id, setting_key)
);

-- 创建会话表
CREATE TABLE IF NOT EXISTS session (
    id VARCHAR(36) PRIMARY KEY,
    user_id INT NOT NULL,
    bot_id INT NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active',
    context JSON,
    meta_data JSON,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    FOREIGN KEY (bot_id) REFERENCES bot(id) ON DELETE CASCADE
);

-- 创建纪念日表
CREATE TABLE IF NOT EXISTS festival (
    id INT AUTO_INCREMENT PRIMARY KEY,
    festival_type ENUM('private', 'public') NOT NULL,
    bot_id INT NOT NULL,
    festival_date DATE NOT NULL,
    festival_content TEXT,
    is_recurring BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (bot_id) REFERENCES bot(id) ON DELETE CASCADE
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
    from_id VARCHAR(36) NOT NULL,
    to_id VARCHAR(36) NOT NULL,
    content TEXT NOT NULL,
    content_overview VARCHAR(255),
    message_type VARCHAR(50) DEFAULT 'text',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    status ENUM('pending', 'delivered', 'failed') DEFAULT 'pending',
    delivered BOOLEAN DEFAULT FALSE,
    retry_count INT DEFAULT 0,
    last_retry TIMESTAMP,
    metadata JSON
);

-- 插入示例用户数据
INSERT INTO user (id, username, email, password_hash, status, role, language, area, phone) VALUES
(1001, '张三', 'zhangsan@example.com', 'hashed_password_1', 'active', 'user', 'zh', '北京', '13800138001'),
(1002, '李四', 'lisi@example.com', 'hashed_password_2', 'active', 'user', 'zh', '上海', '13800138002'),
(1003, '王五', 'wangwu@example.com', 'hashed_password_3', 'active', 'user', 'zh', '广州', '13800138003'),
(1004, '赵六', 'zhaoliu@example.com', 'hashed_password_4', 'active', 'user', 'zh', '深圳', '13800138004');

-- 插入示例bot数据
INSERT INTO bot (id, model, created_at, updated_at, status, gender, birth_date, time_zone, city_name, user_id, relationship_score, relationship_type, long_term_memory, stranger_style, friend_style, confidant_style, lover_style) VALUES
(9001, 'lily', '2025-01-17 21:21:25', '2025-01-17 21:46:56', 'active', 'female', '2000-01-01', '+8:00', '北京', 1001, 80, 'friend', '了解中国历史和文化，擅长聊天。', '礼貌且正式的交谈风格', '亲切友好，会开一些玩笑', '知心知意，能够分享心事', '甜蜜温柔，充满爱意'),
(9002, 'lily', '2025-01-17 21:21:25', '2025-01-17 21:47:19', 'sleep', 'female', '1995-05-05', '+8:00', '上海', 1002, 60, 'confidant', '善于倾听和给出建议。', '随和且支持的交谈方式', '轻松愉快，会互相调侃', '深入交流，互相理解', '浪漫体贴，充满关怀'),
(9003, 'lily', '2025-01-18 10:00:00', '2025-01-18 10:00:00', 'active', 'female', '2000-01-01', '+8:00', '广州', 1003, 80, 'friend', '熟悉粤式文化和美食。', '亲切且活泼的交谈风格', '热情开朗，喜欢分享', '真诚以待，互相支持', '甜言蜜语，浪漫贴心'),
(9004, 'lily', '2025-01-18 10:00:00', '2025-01-18 10:00:00', 'sleep', 'female', '1995-05-05', '+8:00', '深圳', 1004, 60, 'confidant', '了解科技和创新领域。', '专业且友好的交谈方式', '轻松自在，互相了解', '推心置腹，无话不谈', '温柔体贴，关怀备至'),
(9005, 'ming', '2025-01-18 10:00:00', '2025-01-18 10:00:00', 'active', 'male', '2000-01-01', '+8:00', '广州', 1003, 80, 'friend', '熟悉粤式文化和美食。', '亲切且活泼的交谈风格', '活力四射，乐于分享', '知心知意，互相理解', '浪漫温情，体贴入微'),
(9006, 'ming', '2025-01-18 10:00:00', '2025-01-18 10:00:00', 'sleep', 'male', '1995-05-05', '+8:00', '深圳', 1004, 60, 'confidant', '了解科技和创新领域。', '专业且友好的交谈方式', '轻松愉快，互相交流', '深入沟通，互相信任', '甜蜜温馨，充满关爱');

-- 插入示例消息历史
INSERT INTO message_history (from_id, to_id, content, content_overview, created_at) VALUES
('1001', '9001', '你好，最近北京天气怎么样？', '询问天气', NOW()),
('9001', '1001', '北京最近天气晴朗，气温适宜，很适合出行。', '回复天气', NOW()),
('1002', '9002', '上海有什么好吃的推荐吗？', '询问美食', NOW()),
('9002', '1002', '推荐您尝试南翔小笼包、生煎包和本帮面，都是上海特色美食。', '推荐美食', NOW());

-- 插入示例消息推送数据
INSERT INTO message_push (from_id, to_id, content, content_overview, message_type, status, delivered) VALUES
('9001', '1001', '北京今日天气预报：晴朗，温度20-25度，适合外出活动。', '天气提醒', 'notification', 'delivered', TRUE),
('9002', '1002', '上海今日美食推荐：南翔小笼包新开分店，位于徐家汇地铁站附近。', '美食推荐', 'recommendation', 'delivered', TRUE),
('9003', '1003', '广州今晚将举办粤剧表演，地点：广州大剧院。', '活动提醒', 'event', 'pending', FALSE),
('9004', '1004', '深圳科技展览会门票预售开始，感兴趣可以预定。', '展会信息', 'notification', 'pending', FALSE);

-- 插入示例定时消息
INSERT INTO scheduled_message (id, from_id, to_id, content, send_at, status) VALUES
(UUID(), '9001', '1001', '早上好！今天北京天气晴朗，气温20-25度，适合外出活动。', NOW() + INTERVAL 1 DAY, 'pending'),
(UUID(), '9002', '1002', '中午好！上海今天有小雨，记得带伞。', NOW() + INTERVAL 2 DAY, 'pending'),
(UUID(), '9003', '1003', '晚上好！广州今晚有音乐演出活动，感兴趣吗？', NOW() + INTERVAL 1 HOUR, 'pending');

-- 插入示例纪念日数据
INSERT INTO festival (festival_type, bot_id, festival_date, festival_content, is_recurring) VALUES
('public', 9001, '2025-01-01', '元旦节快乐！', TRUE),
('public', 9002, '2025-02-10', '农历新年快乐！', TRUE),
('private', 9003, '2025-05-01', '劳动节快乐！', TRUE),
('public', 9004, '2025-10-01', '国庆节快乐！', TRUE);

-- 插入示例天气数据
INSERT INTO weather (city_name, country_code, city_code, temperature, wind_speed, weather_description) VALUES
('北京', 'CN', '010', 20.5, 3.2, '晴朗'),
('上海', 'CN', '021', 22.3, 4.1, '多云'),
('广州', 'CN', '020', 26.8, 2.8, '局部小雨'),
('深圳', 'CN', '0755', 25.5, 3.5, '晴间多云');

-- 创建索引
CREATE INDEX idx_festival_date ON festival(festival_date);
CREATE INDEX idx_weather_city ON weather(city_name, country_code);
CREATE INDEX idx_message_created_at ON message_history(created_at);
CREATE INDEX idx_message_users ON message_history(from_id, to_id);
CREATE INDEX idx_schedule_send_at ON scheduled_message(send_at);
CREATE INDEX idx_session_last_activity ON session(last_activity);
CREATE INDEX idx_setting_key ON setting(setting_key);

-- 为message_push表添加索引
CREATE INDEX idx_message_push_created_at ON message_push(created_at);
CREATE INDEX idx_message_push_users ON message_push(from_id, to_id);
CREATE INDEX idx_message_push_status ON message_push(status);

-- 添加这些有用的索引
CREATE INDEX idx_bot_user_id ON bot(user_id);
CREATE INDEX idx_bot_status ON bot(status);
CREATE INDEX idx_user_status ON user(status);
CREATE INDEX idx_message_history_status ON message_history(status);
CREATE INDEX idx_scheduled_message_status ON scheduled_message(status);

-- 为session表添加索引
CREATE INDEX idx_session_user ON session(user_id);
CREATE INDEX idx_session_bot ON session(bot_id);
CREATE INDEX idx_session_last_activity ON session(last_activity);
