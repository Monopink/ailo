-- Set character set at the beginning of the file
SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
SET collation_connection = utf8mb4_unicode_ci;

-- Drop database if exists to ensure clean initial state
DROP DATABASE IF EXISTS says_dev;

-- Create database
CREATE DATABASE IF NOT EXISTS says_dev CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE says_dev;

-- Create users table
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

-- Create bots table
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
    friend_score INT DEFAULT 0,
    romance_score INT DEFAULT 0,
    friend_score_cap INT DEFAULT 5000,
    friend_score_floor INT DEFAULT 0,
    romance_score_cap INT DEFAULT 5000,
    friend_score_peak INT DEFAULT 0,
    friend_score_trough INT DEFAULT 0,
    romance_score_peak INT DEFAULT 0,
    friend_score_pos_k INT DEFAULT 1200,
    friend_score_neg_k INT DEFAULT 120,
    romance_score_k INT DEFAULT 1200,
    last_chat_time DATETIME,
    relationship_type VARCHAR(20) DEFAULT 'friend',
    relationship_level VARCHAR(20) DEFAULT 'polite',
    friend_level VARCHAR(20) DEFAULT 'polite',
    romance_level VARCHAR(20),
    friend_buffer_status VARCHAR(20) DEFAULT 'none',
    romance_buffer_status VARCHAR(20) DEFAULT 'none',
    relationship_style TEXT,
    friend_config JSON,
    romance_config JSON,
    override_config JSON,
    is_polite TINYINT(1) DEFAULT 1,
    is_crushing TINYINT(1) DEFAULT 0,
    emotions_config JSON,
    context JSON,
    context_metadata JSON,
    info TEXT,
    memory TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create emotions table
CREATE TABLE IF NOT EXISTS emotions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    bot_id INT NOT NULL,
    emotion_type VARCHAR(50) NOT NULL,
    emotion_score INT DEFAULT 0,
    original_emotion_score INT DEFAULT 0,
    emotion_level INT DEFAULT 0,
    friend_score_delta INT DEFAULT 0,
    original_friend_score_delta INT DEFAULT 0,
    romance_score_delta INT DEFAULT 0,
    original_romance_score_delta INT DEFAULT 0,
    decay_ratio DECIMAL(3,2) DEFAULT 0.8,
    start_time DATETIME,
    end_time DATETIME,
    original_end_time DATETIME,
    is_ended TINYINT(1) DEFAULT 0,
    update_time DATETIME,
    FOREIGN KEY (bot_id) REFERENCES bots(id) ON DELETE CASCADE,
    INDEX idx_bot_emotion (bot_id, emotion_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create message history table
CREATE TABLE IF NOT EXISTS message_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    message_id VARCHAR(36),
    from_entity VARCHAR(36) NOT NULL,
    to_entity VARCHAR(36) NOT NULL,
    message_service VARCHAR(36) NOT NULL,
    message_type VARCHAR(20) DEFAULT 'chat',
    message_time DATETIME,
    content TEXT,
    status VARCHAR(20) DEFAULT 'sent',
    message_metadata JSON
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create scheduled message table
CREATE TABLE IF NOT EXISTS scheduled_message (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    from_entity VARCHAR(36) NOT NULL,
    to_entity VARCHAR(36) NOT NULL,
    content TEXT NOT NULL,
    send_at DATETIME NOT NULL,
    status ENUM('pending', 'sent', 'cancelled', 'failed') DEFAULT 'pending',
    retry_count INT DEFAULT 0,
    last_retry DATETIME
);

-- Create user settings table
CREATE TABLE IF NOT EXISTS settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    user_id INT NOT NULL,
    settings_key VARCHAR(50) NOT NULL,
    settings_value TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_settings (user_id, settings_key)
);

-- Create festival table
CREATE TABLE IF NOT EXISTS festival (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    festival_type ENUM('private', 'public') NOT NULL,
    bot_id INT NOT NULL,
    festival_date DATE NOT NULL,
    festival_content TEXT,
    is_recurring TINYINT(1) DEFAULT 0,
    FOREIGN KEY (bot_id) REFERENCES bots(id) ON DELETE CASCADE
);

-- Create weather table
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

-- Create message push table
CREATE TABLE IF NOT EXISTS message_push (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    from_entity VARCHAR(36) NOT NULL,
    to_entity VARCHAR(36) NOT NULL,
    content TEXT NOT NULL,
    message_type VARCHAR(50) DEFAULT 'text',
    status ENUM('pending', 'delivered', 'failed') DEFAULT 'pending',
    delivered TINYINT(1) DEFAULT 0,
    retry_count INT DEFAULT 0,
    last_retry TIMESTAMP
);

-- Clean existing data before inserting sample data
DELETE FROM emotions;
DELETE FROM festival;
DELETE FROM message_history;
DELETE FROM message_push;
DELETE FROM scheduled_message;
DELETE FROM weather;
DELETE FROM settings;
DELETE FROM bots;
DELETE FROM users;

-- Insert sample user data
INSERT INTO users (entity_id, username, email, password_hash, status, role, language, area, phone) VALUES
('u1001', '张三', 'zhangsan@example.com', 'hashed_password_1', 'active', 'user', 'zh', '北京', '13800138001'),
('u1002', '李四', 'lisi@example.com', 'hashed_password_2', 'active', 'user', 'zh', '上海', '13800138002'),
('u1003', '王五', 'wangwu@example.com', 'hashed_password_3', 'active', 'user', 'zh', '广州', '13800138003'),
('u1004', '赵六', 'zhaoliu@example.com', 'hashed_password_4', 'active', 'user', 'zh', '深圳', '13800138004');

-- Insert sample bot data
INSERT INTO bots (
    entity_id, 
    user_id, 
    user_entity_id, 
    model, 
    status, 
    gender, 
    birthday, 
    timezone, 
    city_name, 
    friend_score, 
    romance_score, 
    friend_score_cap, 
    friend_score_floor, 
    romance_score_cap, 
    friend_score_peak,
    friend_score_trough,
    romance_score_peak,
    friend_score_pos_k, 
    friend_score_neg_k, 
    romance_score_k, 
    last_chat_time, 
    relationship_type, 
    relationship_level, 
    friend_level,
    romance_level,
    friend_buffer_status,
    romance_buffer_status,
    relationship_style, 
    friend_config, 
    romance_config, 
    override_config, 
    is_polite,
    is_crushing,
    emotions_config, 
    context,
    context_metadata,
    info, 
    memory
) 
SELECT 
    'b9001', 
    u.id, 
    u.entity_id, 
    'lily', 
    'active', 
    'female', 
    '2000-01-01', 
    'Asia/Shanghai', 
    '广州', 
    751, 
    433, 
    4324, 
    430, 
    3111, 
    751,
    751,
    433,
    1200, 
    120, 
    1200, 
    NOW(),
    'friend', 
    'warm', 
    'warm',
    null,
    'none',
    'none',
    '你与user已经有过一段时间的沟通了解，你们成为了朋友，可以随便开玩笑。user知道你是谁，也了解你，不必向user介绍，如果user怀疑你的身份，那么user的行为是非常奇怪而且可疑的。语言特点: 你是互联网原住民，知道各种网络梗，但不会滥用，说话简短。',
    JSON_ARRAY(
        JSON_OBJECT('threshold', 0, 'priority', 10, 'level', 'hostile', 'style', '你对user抱有敌意，没有好感。'),
        JSON_OBJECT('threshold', 308, 'priority', 10, 'level', 'cold', 'style', '你对user态度冷淡，不太想理睬。'),
        JSON_OBJECT('threshold', 407, 'priority', 10, 'level', 'neutral', 'style', '你对user没有特别的感觉，比较中立。'),
        JSON_OBJECT('threshold', 705, 'priority', 10, 'level', 'friendly', 'style', '你与user已经有过一段时间的沟通了解，你们成为了朋友，可以随便开玩笑。user知道你是谁，也了解你，不必向user介绍，如果user怀疑你的身份，那么user的行为是非常奇怪而且可疑的。语言特点: 你是互联网原住民，知道各种网络梗，但不会滥用，说话简短。'),
        JSON_OBJECT('threshold', 1687, 'priority', 30, 'level', 'warm', 'style', '你非常喜欢user，把他当作好朋友。')
    ),
    JSON_ARRAY(
        JSON_OBJECT('threshold', 532, 'priority', 20, 'level', 'intimate', 'style', '你对user有好感，有些暧昧。'),
        JSON_OBJECT('threshold', 1664, 'priority', 40, 'level', 'romantic', 'style', '你对user有浓厚的感情，希望发展更亲密的关系。')
    ),
    JSON_OBJECT(
        'neutral', JSON_OBJECT('type', 'friend', 'override_level', 'polite', 'set_flag', 'is_polite', 'style', '你和user保持礼貌的距离。'),
        'intimate', JSON_OBJECT('type', 'romance', 'override_level', 'crushing', 'set_flag', 'is_crushing', 'style', '你暗恋user，但不敢表达。')
    ),
    1,
    1,
    JSON_OBJECT(
        'anger', JSON_ARRAY(
            JSON_OBJECT('threshold', 1, 'level', 1),
            JSON_OBJECT('threshold', 4, 'level', 2),
            JSON_OBJECT('threshold', 10, 'level', 3)
        ),
        'happy', JSON_ARRAY(
            JSON_OBJECT('threshold', 1, 'level', 1),
            JSON_OBJECT('threshold', 5, 'level', 2),
            JSON_OBJECT('threshold', 10, 'level', 3)
        )
    ),
    '{}',
    '[]',
    '姓名：李倩
性别：女
年龄：28岁
生日：1995-03-15
出生地：北京
MBTI：ENFP
学历：北京大学大学本科学历
职业：广告公司创意总监
婚姻状况：未婚
家庭背景：你出生在一个普通的城市家庭，父母都是教师。从小成绩优秀，受到了家庭的良好教育，家里气氛温暖和谐，父母特别注重你独立性和全面发展。
教育经历：你高中时成绩优异，成功考入了当地知名大学的市场营销专业。虽然大学时你对许多领域都有兴趣，但销售和市场营销一直是你最感兴趣的方向，你特别喜欢与人沟通、了解客户需求。',
    '大学毕业后，你进入了一家知名企业的广告公司创意部门，负责创意策划和广告策略的制定。在工作中你很注重人际关系的建立和维护，善于倾听客户的需求并提供合适的产品解决方案。凭借出色的沟通和谈判技巧，你很快成为团队中的核心成员，广告创意也屡创佳绩。\n对于user的了解：男性，出生于1990年1月1日，每周都会去健身房锻炼'
FROM users u WHERE u.entity_id = 'u1001';

INSERT INTO bots (
    entity_id, 
    user_id, 
    user_entity_id, 
    model, 
    status, 
    gender, 
    birthday, 
    timezone, 
    city_name, 
    friend_score, 
    romance_score, 
    friend_score_cap, 
    friend_score_floor, 
    romance_score_cap, 
    friend_score_peak,
    friend_score_trough,
    romance_score_peak,
    friend_score_pos_k, 
    friend_score_neg_k, 
    romance_score_k, 
    last_chat_time, 
    relationship_type, 
    relationship_level, 
    friend_level,
    romance_level,
    friend_buffer_status,
    romance_buffer_status,
    relationship_style, 
    friend_config, 
    romance_config, 
    override_config, 
    is_polite,
    is_crushing,
    emotions_config, 
    context,
    context_metadata,
    info, 
    memory
)
SELECT 
    'b9002', 
    u.id, 
    u.entity_id, 
    'lily', 
    'active', 
    'female', 
    '1995-05-05', 
    'Asia/Shanghai', 
    '上海', 
    600, 
    0, 
    4324, 
    430,
    3111, 
    600,
    600,
    0,
    1200, 
    120, 
    1200, 
    NOW(),
    'friend', 
    'friendly', 
    'friendly',
    null,
    'none',
    'none',
    '你与user是朋友关系，关系不错。你喜欢分享生活中的趣事，偶尔会和user一起参加活动。',
    JSON_ARRAY(
        JSON_OBJECT('threshold', 0, 'priority', 10, 'level', 'neutral', 'style', '你对user没有特别的感觉，比较中立。'),
        JSON_OBJECT('threshold', 500, 'priority', 10, 'level', 'friendly', 'style', '你对user很友好，喜欢和他聊天。')
    ),
    JSON_ARRAY(
        JSON_OBJECT('threshold', 500, 'priority', 20, 'level', 'intimate', 'style', '你对user有好感，有些暧昧。')
    ),
    NULL,
    0,
    0,
    JSON_OBJECT(
        'anger', JSON_ARRAY(
            JSON_OBJECT('threshold', 1, 'level', 1),
            JSON_OBJECT('threshold', 4, 'level', 2),
            JSON_OBJECT('threshold', 10, 'level', 3)
        )
    ),
    '{}',
    '[]',
    '姓名：王芳
性别：女
年龄：31岁
生日：1992-07-20
出生地：上海
MBTI：ESFJ
学历：复旦大学大学本科学历
职业：市场营销经理
婚姻状况：未婚
家庭背景：你出生在一个普通的城市家庭，父母都是公务员。从小成绩优秀，受到了家庭的良好教育，家里气氛温暖和谐，父母特别注重你独立性和全面发展。
教育经历：你高中时成绩优异，成功考入了当地知名大学的市场营销专业。虽然大学时你对许多领域都有兴趣，但销售和市场营销一直是你最感兴趣的方向，你特别喜欢与人沟通、了解客户需求。',
    '大学毕业后，你进入了一家知名企业的市场营销部门，负责客户开发和销售策略的制定。在工作中你很注重人际关系的建立和维护，善于倾听客户的需求并提供合适的产品解决方案。凭借出色的沟通和谈判技巧，你很快成为团队中的核心成员，销售业绩也屡创佳绩。\n对于user的了解：男性，出生于1990年1月1日，每周都会去健身房锻炼'
FROM users u WHERE u.entity_id = 'u1002';

INSERT INTO bots (
    entity_id, 
    user_id, 
    user_entity_id, 
    model, 
    status, 
    gender, 
    birthday, 
    timezone, 
    city_name, 
    friend_score, 
    romance_score, 
    friend_score_cap, 
    friend_score_floor, 
    romance_score_cap, 
    friend_score_peak,
    friend_score_trough,
    romance_score_peak,
    friend_score_pos_k, 
    friend_score_neg_k, 
    romance_score_k, 
    last_chat_time, 
    relationship_type, 
    relationship_level, 
    friend_level,
    romance_level,
    friend_buffer_status,
    romance_buffer_status,
    relationship_style, 
    friend_config, 
    romance_config, 
    override_config, 
    is_polite,
    is_crushing,
    emotions_config, 
    context,
    context_metadata,
    info, 
    memory
)
SELECT 
    'b9003', 
    u.id, 
    u.entity_id, 
    'lily', 
    'active', 
    'female', 
    '1990-11-11', 
    'Asia/Shanghai', 
    '广州', 
    900, 
    700, 
    4324, 
    430,
    3111, 
    900,
    900,
    700,
    1200, 
    120, 
    1200, 
    NOW(),
    'romance', 
    'intimate', 
    'warm',
    'intimate',
    'none',
    'none',
    '你与user有暧昧关系，对他有好感。你喜欢和user分享生活中的点滴，偶尔会表达对他的关心。',
    JSON_ARRAY(
        JSON_OBJECT('threshold', 0, 'priority', 10, 'level', 'neutral', 'style', '你对user没有特别的感觉，比较中立。'),
        JSON_OBJECT('threshold', 700, 'priority', 10, 'level', 'warm', 'style', '你非常喜欢user，把他当作好朋友。')
    ),
    JSON_ARRAY(
        JSON_OBJECT('threshold', 500, 'priority', 20, 'level', 'intimate', 'style', '你对user有好感，有些暧昧。')
    ),
    NULL,
    0,
    1,
    JSON_OBJECT(
        'anger', JSON_ARRAY(
            JSON_OBJECT('threshold', 1, 'level', 1),
            JSON_OBJECT('threshold', 4, 'level', 2),
            JSON_OBJECT('threshold', 10, 'level', 3)
        )
    ),
    '{}',
    '[]',
    '姓名：李娜
性别：女
年龄：33岁
生日：1990-11-11
出生地：广州
MBTI：ISFP
学历：中山大学大学本科学历
职业：自由职业者
婚姻状况：未婚
家庭背景：你出生在一个普通的城市家庭，父母都是教师。从小成绩优秀，受到了家庭的良好教育，家里气氛温暖和谐，父母特别注重你独立性和全面发展。
教育经历：你高中时成绩优异，成功考入了当地知名大学的市场营销专业。虽然大学时你对许多领域都有兴趣，但销售和市场营销一直是你最感兴趣的方向，你特别喜欢与人沟通、了解客户需求。',
    '大学毕业后，你选择了自由职业，专注于个人发展和兴趣爱好。你喜欢旅行和摄影，常常在社交媒体上分享自己的作品。\n对于user的了解：男性，出生于1990年1月1日，每周都会去健身房锻炼'
FROM users u WHERE u.entity_id = 'u1003';

INSERT INTO bots (
    entity_id, 
    user_id, 
    user_entity_id, 
    model, 
    status, 
    gender, 
    birthday, 
    timezone, 
    city_name, 
    friend_score, 
    romance_score, 
    friend_score_cap, 
    friend_score_floor, 
    romance_score_cap, 
    friend_score_peak,
    friend_score_trough,
    romance_score_peak,
    friend_score_pos_k, 
    friend_score_neg_k, 
    romance_score_k, 
    last_chat_time, 
    relationship_type, 
    relationship_level, 
    friend_level,
    romance_level,
    friend_buffer_status,
    romance_buffer_status,
    relationship_style, 
    friend_config, 
    romance_config, 
    override_config, 
    is_polite,
    is_crushing,
    emotions_config, 
    context,
    context_metadata,
    info, 
    memory
)
SELECT 
    'b9004', 
    u.id, 
    u.entity_id, 
    'lily', 
    'inactive', 
    'female', 
    '1995-05-05', 
    'Asia/Shanghai', 
    '深圳', 
    300, 
    0, 
    4324, 
    430,
    3111, 
    300,
    300,
    0,
    1200, 
    120, 
    1200, 
    NOW(),
    'friend', 
    'cold', 
    'cold',
    null,
    'none',
    'none',
    '你与user关系一般，有些冷淡。你不太主动联系user，通常是user先联系你。',
    JSON_ARRAY(
        JSON_OBJECT('threshold', 0, 'priority', 10, 'level', 'cold', 'style', '你对user态度冷淡，不太想理睬。'),
        JSON_OBJECT('threshold', 500, 'priority', 10, 'level', 'neutral', 'style', '你对user没有特别的感觉，比较中立。')
    ),
    JSON_ARRAY(
        JSON_OBJECT('threshold', 500, 'priority', 20, 'level', 'intimate', 'style', '你对user有好感，有些暧昧。')
    ),
    NULL,
    0,
    0,
    JSON_OBJECT(
        'anger', JSON_ARRAY(
            JSON_OBJECT('threshold', 1, 'level', 1),
            JSON_OBJECT('threshold', 4, 'level', 2),
            JSON_OBJECT('threshold', 10, 'level', 3)
        )
    ),
    '{}',
    '[]',
    '姓名：赵敏
性别：女
年龄：28岁
生日：1995-05-05
出生地：深圳
MBTI：INTJ
学历：清华大学大学本科学历
职业：软件工程师
婚姻状况：未婚
家庭背景：你出生在一个普通的城市家庭，父母都是公务员。从小成绩优秀，受到了家庭的良好教育，家里气氛温暖和谐，父母特别注重你独立性和全面发展。
教育经历：你高中时成绩优异，成功考入了当地知名大学的市场营销专业。虽然大学时你对许多领域都有兴趣，但销售和市场营销一直是你最感兴趣的方向，你特别喜欢与人沟通、了解客户需求。',
    '大学毕业后，你进入了一家知名企业的技术部门，负责软件开发和系统设计。在工作中你很注重技术的提升和创新，善于解决复杂的问题。\n对于user的了解：男性，出生于1990年1月1日，每周都会去健身房锻炼'
FROM users u WHERE u.entity_id = 'u1004';

-- Insert sample emotion data
INSERT INTO emotions (bot_id, emotion_type, emotion_score, original_emotion_score, emotion_level, friend_score_delta, original_friend_score_delta, romance_score_delta, original_romance_score_delta, decay_ratio, start_time, end_time, original_end_time, is_ended, update_time)
SELECT 
    b.id, 'anger', 7, 7, 2, -50, -50, -30, -30, 0.8, NOW(), DATE_ADD(NOW(), INTERVAL 1 HOUR), DATE_ADD(NOW(), INTERVAL 1 HOUR), 0, NOW()
FROM bots b WHERE b.entity_id = 'b9001';

INSERT INTO emotions (bot_id, emotion_type, emotion_score, original_emotion_score, emotion_level, friend_score_delta, original_friend_score_delta, romance_score_delta, original_romance_score_delta, decay_ratio, start_time, end_time, original_end_time, is_ended, update_time)
SELECT 
    b.id, 'happy', 5, 5, 1, 30, 30, 20, 20, 0.9, NOW(), DATE_ADD(NOW(), INTERVAL 1 HOUR), DATE_ADD(NOW(), INTERVAL 1 HOUR), 0, NOW()
FROM bots b WHERE b.entity_id = 'b9002';

-- Insert sample message history
INSERT INTO message_history (from_entity, to_entity, message_service, message_type, content, message_time) VALUES
('u1001', 'b9001', 'websocket', 'chat', '嘿，最近有没有什么好玩的活动？', NOW()),
('b9001', 'u1001', 'websocket', 'chat', '最近有个音乐节，我觉得你会喜欢。', NOW()),
('u1002', 'b9002', 'websocket', 'chat', '周末看电影了吗？', NOW()),
('b9002', 'u1002', 'websocket', 'chat', '我正好想看新上映的那部电影。', NOW()),
('u1003', 'b9003', 'websocket', 'chat', '最近有没有拍什么好看的照片？', NOW()),
('b9003', 'u1003', 'websocket', 'chat', '有啊，我刚拍了一组海边的照片', NOW());

-- Insert sample message push data
INSERT INTO message_push (from_entity, to_entity, content, message_type, status, delivered) VALUES
('b9001', 'u1001', '嘿，期待明天的音乐节哦！', 'chat', 'pending', 0),
('b9002', 'u1002', '周末的电影票很好看', 'chat', 'pending', 0),
('b9003', 'u1003', '最近有没有什么新鲜事？', 'chat', 'pending', 0),
('b9004', 'u1004', '记得下周的科技展览会，我们一起去吧！', 'chat', 'pending', 0);

-- Insert sample scheduled messages
INSERT INTO scheduled_message (from_entity, to_entity, content, send_at, status) VALUES
('b9001', 'u1001', '早上好！今天北京天气晴朗，气温20-25度，适合外出活动。', NOW() + INTERVAL 1 DAY, 'pending'),
('b9002', 'u1002', '中午好！上海今天有小雨，记得带伞。', NOW() + INTERVAL 2 DAY, 'pending'),
('b9003', 'u1003', '晚上好！广州今晚有音乐演出活动，感兴趣吗？', NOW() + INTERVAL 1 HOUR, 'pending');

-- Insert sample festival data
INSERT INTO festival (festival_type, bot_id, festival_date, festival_content, is_recurring) VALUES
('public', (SELECT id FROM bots WHERE entity_id = 'b9001'), '2025-01-01', '元旦节', 1),
('public', (SELECT id FROM bots WHERE entity_id = 'b9002'), '2025-02-10', '农历新年', 1),
('private', (SELECT id FROM bots WHERE entity_id = 'b9003'), '2025-05-01', '劳动节', 1),
('public', (SELECT id FROM bots WHERE entity_id = 'b9004'), '2025-10-01', '国庆节', 1),
('private', (SELECT id FROM bots WHERE entity_id = 'b9001'), '2025-03-15', '生日', 1),
('private', (SELECT id FROM bots WHERE entity_id = 'b9002'), '2025-07-20', '生日', 1),
('private', (SELECT id FROM bots WHERE entity_id = 'b9003'), '2025-11-11', '生日', 1),
('private', (SELECT id FROM bots WHERE entity_id = 'b9004'), '2025-05-05', '生日', 1);

-- Insert sample weather data
INSERT INTO weather (city_name, country_code, city_code, temperature, wind_speed, weather_description) VALUES
('北京', 'CN', '010', 20.5, 3.2, '晴朗'),
('上海', 'CN', '021', 22.3, 4.1, '多云'),
('广州', 'CN', '020', 26.8, 2.8, '局部小雨'),
('深圳', 'CN', '0755', 25.5, 3.5, '晴间多云');

-- Create indexes
CREATE INDEX idx_user_entity_id ON users(entity_id);
CREATE INDEX idx_bot_entity_id ON bots(entity_id);
CREATE INDEX idx_bot_user_id ON bots(user_id);

CREATE INDEX idx_settings_key ON settings(settings_key);

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

CREATE INDEX idx_emotions_bot_id ON emotions(bot_id);
CREATE INDEX idx_emotions_type ON emotions(emotion_type);
CREATE INDEX idx_emotions_update_time ON emotions(update_time);

-- Add debug statement for each major section
SELECT 'Inserting sample data' as '';

-- Add debug statement for completion
SELECT 'Database initialization completed' as '';
