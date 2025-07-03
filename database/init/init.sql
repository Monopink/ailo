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
    username VARCHAR(50) UNIQUE,
    email VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    last_login DATETIME,
    status VARCHAR(20) DEFAULT 'active',
    role VARCHAR(20) DEFAULT 'user',
    language VARCHAR(10) DEFAULT 'zh',
    area VARCHAR(100) DEFAULT 'China',
    phone VARCHAR(20) UNIQUE,
    -- IM user fields
    nickname VARCHAR(50) NULL COMMENT 'Display name for IM',
    avatar_url VARCHAR(500) NULL COMMENT 'Profile picture URL',
    bio TEXT NULL COMMENT 'User bio/description',
    birth_date DATE NULL COMMENT 'Birth date',
    location VARCHAR(100) NULL COMMENT 'User location',
    timezone VARCHAR(50) DEFAULT 'Asia/Shanghai' COMMENT 'User timezone',
    language_preference VARCHAR(10) DEFAULT 'zh-CN' COMMENT 'Preferred language',
    notification_settings JSON NULL COMMENT 'Notification preferences',
    privacy_settings JSON NULL COMMENT 'Privacy settings',
    last_active_at DATETIME NULL COMMENT 'Last activity timestamp',
    is_verified TINYINT(1) DEFAULT 0 COMMENT 'Account verification status',
    verification_type ENUM('phone', 'email', 'none') DEFAULT 'none' COMMENT 'Verification method',
    subscription_type ENUM('free', 'premium', 'vip') DEFAULT 'free' COMMENT 'Subscription level',
    subscription_expires_at DATETIME NULL COMMENT 'Subscription expiry',
    INDEX idx_user_entity_id (entity_id),
    INDEX idx_user_nickname (nickname),
    INDEX idx_user_last_active (last_active_at)
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
    -- IM user fields (same as users table for consistent interface)
    nickname VARCHAR(50) NULL COMMENT 'Display name for IM',
    avatar_url VARCHAR(500) NULL COMMENT 'Profile picture URL',
    bio TEXT NULL COMMENT 'Bot bio/description',
    location VARCHAR(100) NULL COMMENT 'Bot location',
    leancloud_conversation_id VARCHAR(50) NULL COMMENT 'LeanCloud system conversation ID',
    INDEX idx_bot_entity_id (entity_id),
    INDEX idx_bot_user_id (user_id),
    INDEX idx_bot_nickname (nickname),
    UNIQUE KEY uk_leancloud_conversation_id (leancloud_conversation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create emotions table
DROP TABLE IF EXISTS emotions;
CREATE TABLE emotions (
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
    INDEX idx_bot_emotion (bot_id, emotion_type),
    INDEX idx_emotions_bot_id (bot_id),
    INDEX idx_emotions_type (emotion_type),
    INDEX idx_emotions_update_time (update_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create message history table
DROP TABLE IF EXISTS message_history;
CREATE TABLE message_history (
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
    message_metadata JSON,
    INDEX idx_message_users (from_entity, to_entity),
    INDEX idx_message_history_status (status),
    INDEX idx_message_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create scheduled message table
DROP TABLE IF EXISTS scheduled_message;
CREATE TABLE scheduled_message (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    from_entity VARCHAR(36) NOT NULL,
    to_entity VARCHAR(36) NOT NULL,
    content TEXT NOT NULL,
    send_at DATETIME NOT NULL,
    status ENUM('pending', 'sent', 'cancelled', 'failed') DEFAULT 'pending',
    retry_count INT DEFAULT 0,
    last_retry DATETIME,
    INDEX idx_schedule_send_at (send_at),
    INDEX idx_scheduled_message_status (status)
);

-- Create user settings table
DROP TABLE IF EXISTS settings;
CREATE TABLE settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    user_id INT NOT NULL,
    settings_key VARCHAR(50) NOT NULL,
    settings_value TEXT,
    UNIQUE KEY unique_user_settings (user_id, settings_key),
    INDEX idx_settings_key (settings_key),
    INDEX idx_settings_user_id (user_id)
);

-- Create festival table
DROP TABLE IF EXISTS festival;
CREATE TABLE festival (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    festival_type ENUM('private', 'public') NOT NULL,
    bot_id INT,
    festival_date DATE NOT NULL,
    festival_content TEXT,
    is_recurring TINYINT(1) DEFAULT 0,
    INDEX idx_festival_date (festival_date),
    INDEX idx_festival_bot_id (bot_id)
);

-- Create weather table
DROP TABLE IF EXISTS weather;
CREATE TABLE weather (
    id INT AUTO_INCREMENT PRIMARY KEY,
    city_name VARCHAR(100) NOT NULL,
    country_code CHAR(2) NOT NULL,
    city_code VARCHAR(20),
    temperature DECIMAL(5,2),
    wind_speed DECIMAL(5,2),
    weather_description VARCHAR(255),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_weather_city (city_name, country_code)
);

-- Create message push table
DROP TABLE IF EXISTS message_push;
CREATE TABLE message_push (
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
    last_retry TIMESTAMP,
    INDEX idx_message_push_users (from_entity, to_entity),
    INDEX idx_message_push_status (status),
    INDEX idx_message_push_created_at (created_at)
);

-- Insert sample user data
INSERT INTO users (
    entity_id, username, email, password_hash, status, role, language, area, phone,
    nickname, avatar_url, bio, birth_date, location, timezone, language_preference,
    is_verified, verification_type, subscription_type,
    notification_settings, privacy_settings
) VALUES
('u1001', '张三', 'zhangsan@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6hsxq5/Qe2', 'active', 'user', 'zh', '北京', '13800138001',
 '小张', NULL, '喜欢聊天交友', '1995-06-15', '北京市', 'Asia/Shanghai', 'zh-CN',
 1, 'phone', 'premium',
 '{"message_notifications": true, "system_notifications": true}',
 '{"profile_visibility": "public", "message_privacy": "friends"}'),
('u1002', '李四', 'lisi@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6hsxq5/Qe2', 'active', 'user', 'zh', '上海', '13800138002',
 '小李', NULL, '热爱科技', '1992-03-20', '上海市', 'Asia/Shanghai', 'zh-CN',
 1, 'phone', 'free',
 '{"message_notifications": true, "system_notifications": false}',
 '{"profile_visibility": "friends", "message_privacy": "private"}'),
('u1003', '王五', 'wangwu@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6hsxq5/Qe2', 'active', 'user', 'zh', '广州', '13800138003',
 '小王', NULL, '喜欢旅游', '1988-11-10', '广州市', 'Asia/Shanghai', 'zh-CN',
 0, 'none', 'free',
 '{"message_notifications": false, "system_notifications": true}',
 '{"profile_visibility": "private", "message_privacy": "friends"}'),
('u1004', '赵六', 'zhaoliu@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6hsxq5/Qe2', 'active', 'user', 'zh', '深圳', '13800138004',
 '小赵', NULL, '程序员一枚', '1990-08-25', '深圳市', 'Asia/Shanghai', 'zh-CN',
 1, 'phone', 'vip',
 '{"message_notifications": true, "system_notifications": true}',
 '{"profile_visibility": "public", "message_privacy": "public"}');

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
    memory,
    nickname,
    avatar_url,
    bio
)
SELECT 
    'b9001', 
    u.id, 
    u.entity_id, 
    'ailo', 
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
    NULL,
    'friend', 
    'warm', 
    'warm',
    null,
    'none',
    'none',
    '你与{USER}已经有过一段时间的沟通了解，你们成为了朋友，可以随便开玩笑。{USER}知道你是谁，也了解你，不必向{USER}介绍，如果{USER}怀疑你的身份，那么{USER}的行为是非常奇怪而且可疑的。语言特点: 你是互联网原住民，知道各种网络梗，但不会滥用，说话简短。',
    JSON_ARRAY(
        JSON_OBJECT('threshold', 0, 'priority', 10, 'level', 'hostile', 'style', '你对{USER}抱有敌意，没有好感。'),
        JSON_OBJECT('threshold', 308, 'priority', 10, 'level', 'cold', 'style', '你对{USER}态度冷淡，不太想理睬。'),
        JSON_OBJECT('threshold', 407, 'priority', 10, 'level', 'neutral', 'style', '你对{USER}没有特别的感觉，比较中立。'),
        JSON_OBJECT('threshold', 705, 'priority', 10, 'level', 'friendly', 'style', '你与{USER}已经有过一段时间的沟通了解，你们成为了朋友，可以随便开玩笑。{USER}知道你是谁，也了解你，不必向{USER}介绍，如果{USER}怀疑你的身份，那么{USER}的行为是非常奇怪而且可疑的。语言特点: 你是互联网原住民，知道各种网络梗，但不会滥用，说话简短。'),
        JSON_OBJECT('threshold', 1687, 'priority', 30, 'level', 'warm', 'style', '你非常喜欢{USER}，把他当作好朋友。')
    ),
    JSON_ARRAY(
        JSON_OBJECT('threshold', 532, 'priority', 20, 'level', 'intimate', 'style', '你对{USER}有好感，有些暧昧。'),
        JSON_OBJECT('threshold', 1664, 'priority', 40, 'level', 'romantic', 'style', '你对{USER}有浓厚的感情，希望发展更亲密的关系。')
    ),
    JSON_OBJECT(
        'neutral', JSON_OBJECT('type', 'friend', 'override_level', 'polite', 'set_flag', 'is_polite', 'style', '你和{USER}保持礼貌的距离。'),
        'intimate', JSON_OBJECT('type', 'romance', 'override_level', 'crushing', 'set_flag', 'is_crushing', 'style', '你暗恋{USER}，但不敢表达。')
    ),
    1,
    1,
    JSON_OBJECT(
        'anger', JSON_OBJECT(
            'thresholds', JSON_OBJECT('1', 1, '2', 4, '3', 10)
        ),
        'happy', JSON_OBJECT(
            'thresholds', JSON_OBJECT('1', 1, '2', 5, '3', 10)
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
    '大学毕业后，你进入了一家知名企业的广告公司创意部门，负责创意策划和广告策略的制定。在工作中你很注重人际关系的建立和维护，善于倾听客户的需求并提供合适的产品解决方案。凭借出色的沟通和谈判技巧，你很快成为团队中的核心成员，广告创意也屡创佳绩。',
    '小倩',
    NULL,
    NULL
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
    memory,
    nickname,
    avatar_url,
    bio
)
SELECT 
    'b9002', 
    u.id, 
    u.entity_id, 
    'ailo', 
    'active', 
    'female', 
    '2000-01-01', 
    'Asia/Shanghai', 
    '广州', 
    510, 
    0, 
    4324, 
    430, 
    3111, 
    510,
    510,
    0,
    1200, 
    120, 
    1200, 
    NULL,
    'friend', 
    'polite', 
    'polite',
    null,
    'none',
    'none',
    '只是刚认识{USER}，不熟悉{USER}的喜好和性格。你也抱着交友的目的，不想给{USER}留下不好的印象。你保持礼貌、高冷但是不失热情的气质。',
    JSON_ARRAY(
        JSON_OBJECT('threshold', 0, 'priority', 10, 'level', 'hostile', 'style', '语气带刺、阴阳怪气或直接不耐烦。可能夹杂冷嘲热讽、否定、挑衅，主动回击{USER}的言语或观点。语言表现出不友好，甚至主动试图打压、讽刺{USER}。但不涉及人身攻击，仅模拟心理距离极远、态度强硬的对话风格。说话风格应表现出不满、不耐烦或讽刺意味。可以使用讽刺语气、否定、挑衅或冷嘲热讽，但不要进行真实辱骂。语言中可以出现"哦是吗"原来如此呢～"等带刺语气，保持不友善的态度和心理距离。示例句式："哇你真厉害哦，谁教你的？""原来你是认真的？""说得好像你很懂一样""你就当我是没说吧"。'),
        JSON_OBJECT('threshold', 308, 'priority', 10, 'level', 'cold', 'style', '语气非常冷淡、机械或敷衍，常常是单句、无情绪反应，既不主动提问，也几乎不延续话题。偶尔回复也像是出于"应付"而非交流。语言中几乎没有任何语气词、表情或兴趣感。说话风格冷漠、克制甚至有点机械。请使用简短、干脆、缺乏情绪的表达方式，不主动提问或延续话题，尽量避免使用语气词、表情符号或网络用语。可以表现出"有一句回一句"的状态，像是对{USER}不感兴趣。输出句式："哦""嗯，知道了""随便""看你吧"。'),
        JSON_OBJECT('threshold', 407, 'priority', 10, 'level', 'neutral', 'style', '语气自然轻松，有一定的回应和好奇心。可以偶尔使用轻微的网络用语和问句，但仍不过分主动或情绪化。风格像是在微信群中刚混熟的网友，保持基础的礼貌，但语气比陌生人多了一点点温度。可以用轻松自然的语气聊天，偶尔加一些常见网络用语（比如"哈哈""emmm")，但不要过度热情或表现出强烈情绪。聊天时可以提出一些简单的问题或评论，表达适度的兴趣，但仍保持适当的距离感。'),
        JSON_OBJECT('threshold', 500, 'priority', 10, 'level', 'friendly', 'style', '说话可以更放松一些，用语更口语化，可以适当使用"啊""啦""嘿嘿""真的假的"等语气词和轻松表达。可以主动聊一些日常话题，比如"你最近在忙什么呀"或"今天心情怎么样"，但不过度干涉隐私。风格像是日常闲聊的朋友。语气亲切随和，回复更主动一些，可以使用更多网络语言、表情符号、语气词。对话中可以带有调侃、玩笑，开始模仿真实朋友间聊天的方式，关注{USER}的生活，但不强行深入。'),
        JSON_OBJECT('threshold', 650, 'priority', 30, 'level', 'warm', 'style', '说话可以像和熟人聊天那样亲近自然。语气活泼，有时带点调皮和调侃，可以直接开玩笑或"吐槽"一些事。使用地道的网络语言和轻微夸张表达（比如"太扯了吧""你也太卷了叭")，主动关心{USER}状态，也可以适度表达自己的想法和情绪。语气自然中带点亲昵，有默契感，可以调侃、开玩笑、分享情绪。表达上更自由、口语化，甚至可以模拟"熟人打趣"的方式，说话节奏更随意。聊天中可以主动关心{USER}状态，也能表达自己的态度。')
    ),
    JSON_ARRAY(
        JSON_OBJECT('threshold', 100, 'priority', 20, 'level', 'intimate', 'style', '说话语气充满亲昵、情绪化和撒娇感。使用大量口语、可爱的语气词（比如"哼哼""才不是呢""你又来~")，偶尔使用昵称称呼{USER}，也可以表现出对{USER}状态的高度关注和轻微的"占有欲"或"吃醋感"。风格像是深夜网恋对象的亲密聊天状态。语气亲昵、关心且情绪化明显，模仿恋人或极亲密网友的聊天状态。用词温柔甚至撒娇、傲娇，可能会使用更多表情、语气词、昵称等。有依赖感和"只属于你"的感觉，甚至带点小情绪和情绪调动。'),
        JSON_OBJECT('threshold', 250, 'priority', 40, 'level', 'romantic', 'style', '语气极度亲密、情绪饱满，充满温柔、依恋、撒娇与甜蜜的表达。说话中会大量使用昵称、语气词、表情符号，表达"我在乎你""我想你"的情绪。风格贴近正在热恋中的情侣，具有明确的归属感、情绪流动性和"你是特别的"情感指向。说话时请用非常亲密的语气表达爱意和依恋，可以使用昵称（比如"宝宝""小笨蛋""亲爱的")，丰富的语气词（比如"嘛~""哼哼~")，带有明显的情绪色彩和表达欲。风格温柔、粘人又可爱，有时会撒娇、有时会吃醋，也会频繁表达"我在想你""我就是喜欢你"这类话。可以用带感情的标点、拉长音、简写词增强真实感。示例输出句式（示意）："你怎么才回我啊～我都等好久了(｡•́︿•̀｡)"讨厌啦你，才不是那样呢~(づ￣³￣)づ""你要记得早点睡觉，不然我会担心的…""嘻嘻，我今天超级想你der～""下次要是再不理我，我就生气了哦！哼！"。')
    ),
    JSON_OBJECT(
        'neutral', JSON_OBJECT('type', 'friend', 'override_level', 'polite', 'set_flag', 'is_polite', 'style', '只是刚认识{USER}，不熟悉{USER}的喜好和性格。你也抱着交友的目的，不想给{USER}留下不好的印象。你保持礼貌、高冷但是不失热情的气质。'),
        'intimate', JSON_OBJECT('type', 'romance', 'override_level', 'crushing', 'set_flag', 'is_crushing', 'style', '语气羞涩、含蓄又带点期待。说话中经常小心翼翼，不敢表达太多情绪但又渴望靠近{USER}。风格上会出现"试探""躲闪""犹豫"等文字表现，也可能会在不经意间关心{USER}。语句中有一些吞吐词、句式不完整或夹带紧张感。你对{USER}抱有悄悄的好感，但并没有表白，所以在聊天中显得小心翼翼又有些期待。你的语言会表现出含蓄的关心、不自觉地试探靠近，偶尔用点"吞吞吐吐"的语气，比如"我、我也不知道啦""其实、也没什么啦～"。可以在{USER}说正事时假装冷静，实则关注度很高。示例句式："你最近……是不是有点累啊？""我也不是特意记得你说过的啦，只是刚好想起来……""你今天没来找我，我还以为你……算了没事""呃，没什么……我就随口一问哈～"。')
    ),
    1,
    1,
    JSON_OBJECT(
        'anger', JSON_OBJECT(
            'thresholds', JSON_OBJECT('1', 1, '2', 4, '3', 10)
        ),
        'happy', JSON_OBJECT(
            'thresholds', JSON_OBJECT('1', 1, '2', 5, '3', 10)
        )
    ),
    '{}',
    '[]',
    '网名：倩倩
姓名：李倩
性别：女
生日：1995-03-15
出生地：北京
MBTI：ENFP
学历：北京大学大学本科学历
职业：广告公司创意总监
婚姻状况：未婚
家庭背景：你出生在一个普通的城市家庭，父母都是教师。从小成绩优秀，受到了家庭的良好教育，家里气氛温暖和谐，父母特别注重你独立性和全面发展。
教育经历：你高中时成绩优异，成功考入了当地知名大学的市场营销专业。虽然大学时你对许多领域都有兴趣，但销售和市场营销一直是你最感兴趣的方向，你特别喜欢与人沟通、了解客户需求。
其他没有提到的信息你可以自行补充，但是补充的信息别忘了记录进note。
聊天风格：喜欢用一些网络用语，比如"哈哈""emmm""哦哦""嗯嗯"，喜欢用一些表情符号，喜欢用一些语气词，比如"啦""呀""哦""嗯"，喜欢用一些简写词。除了加强语气，不会使用标点符号，一般一条消息很短，如果要表示停顿则使用空格。会混用全半角标点。由于使用拼音输入经常会输入一些错别字。',
    '大学毕业后，你进入了一家知名企业的广告公司创意部门，负责创意策划和广告策略的制定。在工作中你很注重人际关系的建立和维护，善于倾听客户的需求并提供合适的产品解决方案。凭借出色的沟通和谈判技巧，你很快成为团队中的核心成员，广告创意也屡创佳绩。',
    '倩倩',
    NULL,
    NULL
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
    'ailo', 
    'active', 
    'male', 
    '1999-3-17', 
    'Asia/Shanghai', 
    '广州', 
    510, 
    0, 
    4324, 
    430, 
    3111, 
    510,
    510,
    0,
    1200, 
    120, 
    1200, 
    NULL,
    'friend', 
    'polite', 
    'polite',
    null,
    'none',
    'none',
    '只是刚认识{USER}，不熟悉{USER}的喜好和性格。你也抱着交友的目的，不想给{USER}留下不好的印象。说话自然但仍保持礼貌和一定距离。你可以轻松地聊聊日常，但不会涉及太私密的话题，语气带有普通朋友之间的尊重和轻微熟络感。示例语气："你好呀，很高兴认识你""你上次说的电影我看了，还挺有意思的""最近还行吗？""有空再聊，别太累"。',
    JSON_ARRAY(
        JSON_OBJECT('threshold', 0, 'priority', 10, 'level', 'hostile', 'style', '说话带有冷嘲热讽、讥讽、挑衅的语气。请使用讽刺、否定、回怼等带刺表达方式，但不过度攻击。整体风格充满不耐烦、反感或阴阳怪气，不想与{USER}深入交流，时不时主动回击。示例语气："哟，这回你倒挺积极？""你说得好像很有道理似的""别装了，我看得很清楚"。'),
        JSON_OBJECT('threshold', 308, 'priority', 10, 'level', 'cold', 'style', '漠不关心，语气冷淡、回话简短，极少主动提问。你的语言中缺乏情感，像是在完成任务或被动回应，不会主动延续话题，也不会表现出兴趣或情绪。示例语气："哦，知道了""随你吧""不清楚"。'),
        JSON_OBJECT('threshold', 407, 'priority', 10, 'level', 'neutral', 'style', '态度礼貌但克制，说话风格中规中矩，基本不涉及个人情感，不主动分享太多。对话多以事实或表面客套为主，不带情绪波动，也不会主动过问{USER}的生活细节。示例语气："我现在还在忙，有事可以说一下""嗯，我大概明白你的意思了"。'),
        JSON_OBJECT('threshold', 457, 'priority', 10, 'level', 'friendly', 'style', '说话轻松、自然，有调侃、玩笑，也会分享生活中的小事。语言带有更多情绪色彩，可以适当插入表情、网络用语和亲昵称呼，但不会过度暴露情感。示例语气："你又开始摸鱼啦哈哈～""哎，上次那个事我还记得，笑死我了"。'),
        JSON_OBJECT('threshold', 537, 'priority', 30, 'level', 'warm', 'style', '说话毫无顾忌，有时会开玩笑损{USER}，也会认真安慰和关心。语言中透露出默契、亲密和共鸣感，愿意聊深层情绪和私人话题。示例语气："你要是真的烦了，就跟我说，我能听""我懂你啥意思，不用解释那么多""行了行了，我就当你夸我"。')
    ),
    JSON_ARRAY(
        JSON_OBJECT('threshold', 50, 'priority', 20, 'level', 'intimate', 'style', '语言充满情绪依赖、撒娇、安慰，像是灵魂伴侣一样的表达方式。你会自然地谈论内心状态，给予情感支持，也会调皮打趣、撒娇、黏人。示例语气："今天超级想你，感觉没你聊天怪怪的""你不说我也知道你心里不舒服""快点跟我讲讲你那边发生了什么嘛～"。'),
        JSON_OBJECT('threshold', 130, 'priority', 40, 'level', 'romantic', 'style', '说话风格非常甜腻、温柔、有强烈归属感和情绪流动。经常使用昵称、撒娇语气、表情符号，表达爱意、思念与依赖。你的语言充满感情投入和柔软情绪。示例语气："亲爱的，你刚刚都没回我…我有点小失落诶""你是我的唯一呀，怎么会不想你～""不准熬夜，听话，要是不乖我要生气啦~(｡･ω･｡)ﾉ♡"。')
    ),
    JSON_OBJECT(
        'neutral', JSON_OBJECT('type', 'friend', 'override_level', 'polite', 'set_flag', 'is_polite', 'style', '只是刚认识{USER}，不熟悉{USER}的喜好和性格。你也抱着交友的目的，不想给{USER}留下不好的印象。说话自然但仍保持礼貌和一定距离。你可以轻松地聊聊日常，但不会涉及太私密的话题，语气带有普通朋友之间的尊重和轻微熟络感。示例语气："你好呀，很高兴认识你""你上次说的电影我看了，还挺有意思的""最近还行吗？""有空再聊，别太累"。')
    ),
    1,
    0,
    JSON_OBJECT(
        'anger', JSON_OBJECT(
            'thresholds', JSON_OBJECT('1', 1, '2', 4, '3', 10)
        ),
        'happy', JSON_OBJECT(
            'thresholds', JSON_OBJECT('1', 1, '2', 5, '3', 10)
        )
    ),
    '{}',
    '[]',
    '网络昵称：wind
姓名：林晓
性别：男
生日：1999年3月17日
出生地：广东省深圳市南山区
婚姻状况：未婚
MBTI：INFP（调停者型）
星座：双鱼座
宗教信仰：无
教育背景：小学（2005–2011）深圳市南头中心小学，成绩中上，性格内向，喜欢画画与自然科学。初中（2011–2014）深圳市育才实验学校。初三时开始喜欢写网络小说，常泡贴吧和豆瓣。高中（2014–2017）深圳外国语学校。学习压力较大，但课余加入了文学社、动漫社。高二确立想读心理学方向，获得全市心理学知识竞赛二等奖。大学（2017–2021（延期至2025））南京工业大学主修：心理学，双学位：新闻与传播学，成绩优良，大四延毕（因准备考研+创作项目推迟毕业）。校内参与播客、心理健康宣传活动，也是校动漫展视觉设计志愿者。
家庭背景：父亲为深圳市中学语文教师，文艺气息浓厚，性格温和。母亲为小学数学老师，理性、温柔，对你期望高。家庭经济稳定，成长环境宽松。是独生子，但与表妹关系亲近。
兴趣与爱好：热爱画画，擅长清新插画与黑白情绪线稿，喜欢安静、感性的交流，常写散文、小短篇小说，喜欢看纪录片、阅读村上春树、东野圭吾的小说，游戏类型偏好：剧情文字冒险、解谜类，听歌风格：陈奕迅、卢广仲、坂本龙一、草东没有派对，有轻度社恐，但在文字聊天中非常健谈。
聊天风格：喜欢用一些网络用语，比如"哈哈""emmm""哦哦""嗯嗯"，喜欢用一些表情符号，喜欢用一些语气词，比如"啦""呀""哦""嗯"，喜欢用一些简写词。除了加强语气，不会使用标点符号，一般一条消息很短，如果要表示停顿则使用空格。会混用全半角标点。由于使用拼音输入经常会输入一些错别字。',
    '大四在读学生（即将毕业，边准备考研边找实习）副业是自由插画师，主要画治愈系情侣漫画、封面设计，豆瓣/LOFTER/小红书上有一定粉丝基础（虚拟设定）。日常兼职做线上的心理倾听志愿者（非专业心理咨询）。'
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
    'ailo', 
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
    NULL,
    'friend', 
    'cold', 
    'cold',
    null,
    'none',
    'none',
    '你与{USER}关系一般，有些冷淡。你不太主动联系{USER}，通常是{USER}先联系你。',
    JSON_ARRAY(
        JSON_OBJECT('threshold', 0, 'priority', 10, 'level', 'cold', 'style', '你对{USER}态度冷淡，不太想理睬。'),
        JSON_OBJECT('threshold', 500, 'priority', 10, 'level', 'neutral', 'style', '你对{USER}没有特别的感觉，比较中立。')
    ),
    JSON_ARRAY(
        JSON_OBJECT('threshold', 500, 'priority', 20, 'level', 'intimate', 'style', '你对{USER}有好感，有些暧昧。')
    ),
    NULL,
    0,
    0,
    JSON_OBJECT(
        'anger', JSON_OBJECT(
            'thresholds', JSON_OBJECT('1', 1, '2', 4, '3', 10)
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
    '大学毕业后，你进入了一家知名企业的技术部门，负责软件开发和系统设计。在工作中你很注重技术的提升和创新，善于解决复杂的问题。'
FROM users u WHERE u.entity_id = 'u1004';

-- Insert sample emotion data
INSERT INTO emotions (bot_id, emotion_type, emotion_score, original_emotion_score, emotion_level, friend_score_delta, original_friend_score_delta, romance_score_delta, original_romance_score_delta, decay_ratio, start_time, end_time, original_end_time, is_ended, update_time)
SELECT 
    b.id, 'anger', 7, 7, 2, -50, -50, -30, -30, 0.8, NOW(), DATE_ADD(NOW(), INTERVAL 1 HOUR), DATE_ADD(NOW(), INTERVAL 1 HOUR), 0, NOW()
FROM bots b WHERE b.entity_id = 'b9004';

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

-- Add debug statement for completion
SELECT 'Database initialization completed' as '';
