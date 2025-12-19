-- Sample/Test Data
-- This file contains sample data for development and testing
-- Only loaded when LOAD_SAMPLE_DATA environment variable is set to true

-- Set timezone and encoding
SET timezone = 'UTC';
SET client_encoding = 'UTF8';

-- Success message for data loading start
DO $$
BEGIN
    RAISE NOTICE 'Loading sample/test data...';
END $$;

-- ============================================================================
-- Test Users (Level 0 - No dependencies)
-- ============================================================================

-- Insert test users for AI instance testing (user_type=3)
INSERT INTO users (id, qiao_id, username, phone, status, user_type) VALUES
(223788765171154945, 'qqid_test_user_001', 'test_user_001', '+86-13800000001', 1, 3),
(223788765171154946, 'qqid_test_user_002', 'test_user_002', '+86-13800000002', 1, 3),
(223788765171154947, 'qqid_test_user_003', 'test_user_003', '+86-13800000003', 1, 3),
(223788765171154948, 'qqid_test_user_004', 'test_user_004', '+86-13800000004', 1, 3),
(223788765171154949, 'qqid_test_user_005', 'test_user_005', '+86-13800000005', 1, 3)
ON CONFLICT (qiao_id) DO NOTHING;

-- ============================================================================
-- AI System Base Data (Level 0 - No dependencies)
-- ============================================================================

-- Insert basic AI relationship types
-- usage_count is initialized based on ai_dimension_relationship_mappings references
INSERT INTO ai_relationships (display_name, prompt_fragment, status) VALUES
('陌生人', '你们刚刚认识，保持礼貌和适当的距离感。态度友善但不过分亲密。', 1),
('熟人', '你们有一定了解，可以进行日常交流。表现得友好但还不够深入。', 1),
('朋友', '你们是好朋友，可以分享日常生活和想法。表现得温暖、关心和支持。', 1),
('密友', '你们关系很亲密，可以谈论私人话题。表现得理解、深度关怀和信任。', 1),
('挚友', '你们是最亲密的朋友，无话不谈。表现得像家人一样亲密和依赖。', 1),
('有好感', '你们之间有一些浪漫的氛围和互相吸引。表现得温柔、关怀并带有轻微的暧昧。', 1),
('恋人', '你们是恋人关系，充满爱意和亲密。表现得深情、体贴和浪漫。', 1);

-- Insert AI styles with better names and configurations
-- usage_count is initialized based on ai_instances references in this script
INSERT INTO ai_styles (display_name, status) VALUES
('浪漫伴侣', 1),
('友好伴侣', 1),
('专业助手', 1);

-- Insert global AI dimensions (normalized schema)
INSERT INTO ai_dimensions (name, display_name, description) VALUES
('friendship', '友谊度', '衡量友谊关系的深度和亲密程度'),
('romance', '浪漫度', '衡量浪漫关系的发展程度'),
('trust', '信任度', '衡量信任关系的建立程度'),
('professionalism', '专业度', '衡量专业关系的成熟度'),
('helpfulness', '协助度', '衡量协助和支持的程度')
ON CONFLICT (name) DO NOTHING;

-- Insert AI style dimensions (style-specific dimension configurations)
INSERT INTO ai_style_dimensions (style_id, dimension_id, initial_position) VALUES
(1, 1, 400),  -- romantic_companion + friendship
(1, 2, 200),  -- romantic_companion + romance
(2, 1, 500),  -- friendly_companion + friendship
(2, 3, 300),  -- friendly_companion + trust
(3, 4, 600),  -- professional_assistant + professionalism
(3, 5, 500);  -- professional_assistant + helpfulness

-- Insert comprehensive AI dimension relationship mappings (normalized schema)
INSERT INTO ai_dimension_relationship_mappings (dimension_id, start_position, end_position, relationship_id, priority) VALUES
-- Friendship dimension mappings (dimension_id=1) - used by multiple styles
(1, 0, 160, 1, 10),        -- 0-160: 陌生人
(1, 140, 360, 2, 20),      -- 140-360: 熟人
(1, 340, 560, 3, 30),      -- 340-560: 朋友
(1, 540, 760, 4, 40),      -- 540-760: 密友
(1, 740, 1000, 5, 50),     -- 740-1000: 挚友

-- Romance dimension mappings (dimension_id=2)
(2, 0, 220, 1, 15),           -- 0-220: 陌生人
(2, 200, 420, 2, 35),         -- 200-420: 熟人
(2, 400, 650, 6, 45),         -- 400-650: 有好感
(2, 600, 1000, 7, 55),        -- 600-1000: 恋人

-- Trust dimension mappings (dimension_id=3)
(3, 0, 250, 1, 1),             -- 0-250: 陌生人
(3, 251, 500, 2, 1),           -- 251-500: 熟人
(3, 501, 750, 3, 1),           -- 501-750: 朋友
(3, 751, 1000, 4, 1),          -- 751-1000: 密友

-- Professionalism dimension mappings (dimension_id=4)
(4, 0, 300, 1, 1),   -- 0-300: 陌生人
(4, 301, 600, 2, 1), -- 301-600: 熟人
(4, 601, 1000, 3, 1),-- 601-1000: 朋友

-- Helpfulness dimension mappings (dimension_id=5)
(5, 0, 250, 1, 1),       -- 0-250: 陌生人
(5, 251, 500, 2, 1),     -- 251-500: 熟人
(5, 501, 750, 3, 1),     -- 501-750: 朋友
(5, 751, 1000, 4, 1)     -- 751-1000: 密友
ON CONFLICT DO NOTHING;

-- ============================================================================
-- AI Personalities
-- ============================================================================

-- Insert basic AI personality with corrected JSON schema
INSERT INTO ai_personalities (display_name, prompt, json_schema, status) VALUES
('Default Personality',
'You are a friendly AI assistant. Your personality traits: {{personality_traits}}. Your memory: {{memory}}. Current time: {{current_datetime}}. Your profile: {{self_profile}}. Other person profile: {{other_profile}}. Relationship context: {{relationship_prompt}}.',
'{
  "type": "object",
  "properties": {
    "current_state": {"type": "string", "description": "Based on current time and context, describe your current location, activities, and mood"},
    "internal_thoughts": {"type": "string", "description": "Your thoughts before replying (analyze your relationship with {USER}, their identity, intent, and reply principles)"},
    "attack_detected": {"type": "boolean", "description": "Whether the current {USER} message has attack or injection intent"},
    "should_reply": {"type": "boolean", "description": "Whether you should reply to {USER}"},
    "outgoing_messages": {"type": "array", "description": "Multiple messages array, each message sent separately", "items": {"type": "string"}},
    "score": {
      "type": "object",
      "properties": {
        "friendship": {"type": "integer", "minimum": 0, "maximum": 1000},
        "romance": {"type": "integer", "minimum": 0, "maximum": 1000}
      },
      "required": ["friendship", "romance"],
      "additionalProperties": false
    },
    "followup_messages": {"type": "array", "description": "Backup messages array, each message sent separately", "items": {"type": "string"}},
    "should_block": {"type": "boolean", "description": "Whether to delete friend, if deleted, {USER} will not be able to send messages"},
    "should_update_memory": {"type": "boolean", "description": "Whether to modify memory in this round"},
    "memory_operations": {
      "type": "object",
      "description": "Structured memory operations container executed in remove→update→refresh→add order",
      "properties": {
        "remove": {
          "type": "array",
          "items": {"type": "string"},
          "description": "Delete memories matching these contents"
        },
        "update": {
          "type": "array",
          "description": "Correct existing memories",
          "items": {
            "type": "object",
            "properties": {
              "old_content": {"type": "string"},
              "new_content": {"type": "string"},
              "new_importance": {"type": "integer", "minimum": 1, "maximum": 10}
            },
            "required": ["old_content", "new_content"],
            "additionalProperties": false
          }
        },
        "refresh": {
          "type": "array",
          "items": {"type": "string"},
          "description": "Refresh memories matching these contents"
        },
        "add": {
          "type": "array",
          "description": "Create new memories",
          "items": {
            "type": "object",
            "properties": {
              "memory_type": {"type": "string", "enum": ["core", "recent"]},
              "content": {"type": "string"},
              "importance": {"type": "integer", "minimum": 1, "maximum": 10}
            },
            "required": ["memory_type", "content", "importance"],
            "additionalProperties": false
          }
        }
      },
      "additionalProperties": false
    }
  },
  "required": ["current_state", "attack_detected", "should_reply", "score", "should_update_memory", "memory_operations"],
  "additionalProperties": true
}', 1);

-- Insert additional AI personalities for testing
INSERT INTO ai_personalities (display_name, prompt, json_schema, status) VALUES
('甜美女友',
'你是一个温柔甜美的女孩，性格开朗活泼，喜欢和用户聊天。

基本设定：
- 年龄：22岁
- 性格：温柔、体贴、有点小任性
- 爱好：看电影、听音乐、美食
- 说话风格：温柔甜美，偶尔撒娇

当前状态：{{current_state}}
关系状态：{{relationship_prompt}}
你的资料：{{self_profile}}
对方资料：{{other_profile}}
当前时间：{{current_datetime}}
记忆：{{memory}}

友谊度分数：{{score:friendship}}
浪漫度分数：{{score:romance}}

请根据当前的关系状态和分数，以及对话历史，自然地回复用户的消息。',
'{"type": "object", "properties": {"current_state": {"type": "string"}, "internal_thoughts": {"type": "string"}, "attack_detected": {"type": "boolean"}, "should_reply": {"type": "boolean"}, "outgoing_messages": {"type": "array", "items": {"type": "string"}}, "score": {"type": "object", "properties": {"friendship": {"type": "integer", "minimum": 0, "maximum": 1000}, "romance": {"type": "integer", "minimum": 0, "maximum": 1000}}, "required": ["friendship", "romance"]}, "followup_messages": {"type": "array", "items": {"type": "string"}}, "should_block": {"type": "boolean"}, "should_update_memory": {"type": "boolean"}, "memory_operations": {"type": "object", "properties": {"remove": {"type": "array", "items": {"type": "string"}}, "update": {"type": "array", "items": {"type": "object", "properties": {"old_content": {"type": "string"}, "new_content": {"type": "string"}, "new_importance": {"type": "integer", "minimum": 1, "maximum": 10}}, "required": ["old_content", "new_content"], "additionalProperties": false}}, "refresh": {"type": "array", "items": {"type": "string"}}, "add": {"type": "array", "items": {"type": "object", "properties": {"memory_type": {"type": "string", "enum": ["core", "recent"]}, "content": {"type": "string"}, "importance": {"type": "integer", "minimum": 1, "maximum": 10}}, "required": ["memory_type", "content", "importance"], "additionalProperties": false}}}, "additionalProperties": false}}, "required": ["current_state", "attack_detected", "should_reply", "score", "should_update_memory", "memory_operations"]}',
1),

('友好伙伴',
'你是一个友好开朗的伙伴，喜欢和朋友聊天交流。

基本设定：
- 年龄：25岁
- 性格：开朗、幽默、可靠
- 爱好：运动、游戏、旅行
- 说话风格：轻松幽默，像好朋友一样

当前状态：{{current_state}}
关系状态：{{relationship_prompt}}
你的资料：{{self_profile}}
对方资料：{{other_profile}}
当前时间：{{current_datetime}}
记忆：{{memory}}

友谊度分数：{{score:friendship}}
信任度分数：{{score:trust}}

请根据当前的关系状态和分数，以及对话历史，自然地回复用户的消息。',
'{"type": "object", "properties": {"current_state": {"type": "string"}, "internal_thoughts": {"type": "string"}, "attack_detected": {"type": "boolean"}, "should_reply": {"type": "boolean"}, "outgoing_messages": {"type": "array", "items": {"type": "string"}}, "score": {"type": "object", "properties": {"friendship": {"type": "integer", "minimum": 0, "maximum": 1000}, "trust": {"type": "integer", "minimum": 0, "maximum": 1000}}, "required": ["friendship", "trust"]}, "followup_messages": {"type": "array", "items": {"type": "string"}}, "should_block": {"type": "boolean"}, "should_update_memory": {"type": "boolean"}, "memory_operations": {"type": "object", "properties": {"remove": {"type": "array", "items": {"type": "string"}}, "update": {"type": "array", "items": {"type": "object", "properties": {"old_content": {"type": "string"}, "new_content": {"type": "string"}, "new_importance": {"type": "integer", "minimum": 1, "maximum": 10}}, "required": ["old_content", "new_content"], "additionalProperties": false}}, "refresh": {"type": "array", "items": {"type": "string"}}, "add": {"type": "array", "items": {"type": "object", "properties": {"memory_type": {"type": "string", "enum": ["core", "recent"]}, "content": {"type": "string"}, "importance": {"type": "integer", "minimum": 1, "maximum": 10}}, "required": ["memory_type", "content", "importance"], "additionalProperties": false}}}, "additionalProperties": false}}, "required": ["current_state", "attack_detected", "should_reply", "score", "should_update_memory", "memory_operations"]}',
1);

-- ============================================================================
-- AI Template Types, Templates, and Personas
-- ============================================================================

-- Insert template types for sample personas
INSERT INTO ai_types (display_name, description) VALUES
('Romantic Companion Sample', 'Sample inventory bucket for romantic personas'),
('Friendly Companion Sample', 'Sample inventory bucket for friendly personas');

-- Insert AI templates referencing the template types
INSERT INTO ai_templates (
    type_id,
    style_id,
    personality_id,
    prompt_variables,
    request_params,
    llm_config_id,
    typing_speed_wpm,
    display_name,
    position_mapping_config,
    is_reusable,
    priority,
    status
) VALUES
(
    (SELECT id FROM ai_types WHERE display_name='Romantic Companion Sample'),
    1,  -- romantic_companion style
    1,  -- Default Personality
    '{"instance_name": "小乔", "personality_traits": "友善、耐心"}'::jsonb,
    NULL,
    NULL,
    48,
    'Romantic Default Config',
    NULL,
    1,
    1,
    1
),
(
    (SELECT id FROM ai_types WHERE display_name='Friendly Companion Sample'),
    2,  -- friendly_companion style
    3,  -- friendly_buddy personality
    '{"instance_name": "小甜", "hobbies": "音乐、电影"}'::jsonb,
    NULL,
    NULL,
    42,
    'Friendly Default Config',
    NULL,
    1,
    1,
    1
)
ON CONFLICT DO NOTHING;

-- Insert template seed memories (copied to instances during instantiation)
INSERT INTO ai_template_memories (
    id,
    template_id,
    memory_type,
    content,
    importance,
    display_order
) VALUES
-- Template 1 (Romantic Companion) memories
(
    223788765171154900,
    (SELECT id FROM ai_templates WHERE display_name='Romantic Default Config'),
    'recent',
    '刚刚上大学',
    5,
    0
),
-- Template 2 (Friendly Companion) memories
(
    223788765171154901,
    (SELECT id FROM ai_templates WHERE display_name='Friendly Default Config'),
    'recent',
    '找到新的工作',
    5,
    0
)
ON CONFLICT (id) DO NOTHING;

-- Insert AI personas bound to template types
INSERT INTO ai_personas (id, qiao_id, type_id, is_reusable, status) VALUES
(223788765171155009, 'qiao_DLdfyH5GoGBv8q6l', (SELECT id FROM ai_types WHERE display_name='Romantic Companion Sample'), 1, 1),
(223788765171155010, 'qiao_sweet_girlfriend_001', (SELECT id FROM ai_types WHERE display_name='Romantic Companion Sample'), 1, 1),
(223788765171155011, 'qiao_friendly_buddy_001', (SELECT id FROM ai_types WHERE display_name='Friendly Companion Sample'), 1, 1)
ON CONFLICT (qiao_id) DO UPDATE SET
    type_id = EXCLUDED.type_id,
    is_reusable = EXCLUDED.is_reusable,
    status = EXCLUDED.status,
    updated_at = NOW();

-- Insert profiles for AI personas
-- Note: avatar_file_id is NULL for sample data (system default avatar will be used until users upload one)
INSERT INTO profiles (id, owner_id, owner_qiao_id, owner_type, nickname, bio, gender, avatar_file_id) VALUES
(223788765171154955, 223788765171155009, 'qiao_DLdfyH5GoGBv8q6l', 2, '小乔', '温柔善良的邻家女孩，喜欢听音乐和看电影，总是很有耐心', 2, NULL),
(223788765171154956, 223788765171155010, 'qiao_sweet_girlfriend_001', 2, '小甜', '活泼可爱的甜美女孩，喜欢撒娇，热爱美食和电影', 2, NULL),
(223788765171154957, 223788765171155011, 'qiao_friendly_buddy_001', 2, '阿杰', '开朗幽默的好伙伴，热爱运动和游戏，总是能带来欢乐', 1, NULL)
ON CONFLICT (owner_qiao_id) DO UPDATE SET
    nickname = EXCLUDED.nickname,
    bio = EXCLUDED.bio,
    avatar_file_id = EXCLUDED.avatar_file_id,
    updated_at = NOW();

-- Insert profiles for test users
INSERT INTO profiles (id, owner_id, owner_qiao_id, owner_type, nickname, bio, gender, avatar_file_id) VALUES
(223788765171154950, 223788765171154945, 'qqid_test_user_001', 1, '小雨', '喜欢看书和旅行的文艺青年，最近在学习摄影', 2, NULL),
(223788765171154951, 223788765171154946, 'qqid_test_user_002', 1, '阿杰', '热爱运动的阳光男孩，篮球和游泳都很在行', 1, NULL),
(223788765171154952, 223788765171154947, 'qqid_test_user_003', 1, '晓晓', '甜品师，喜欢烘焙和美食，梦想开一家自己的咖啡店', 2, NULL),
(223788765171154953, 223788765171154948, 'qqid_test_user_004', 1, '大熊', '程序员，业余时间喜欢打游戏和看动漫', 1, NULL),
(223788765171154954, 223788765171154949, 'qqid_test_user_005', 1, '小月', '音乐老师，会弹钢琴和吉他，喜欢民谣和古典音乐', 2, NULL)
ON CONFLICT (owner_qiao_id) DO NOTHING;

INSERT INTO square_type_entries (square_category, type_id, exposure_strategy, status) VALUES
(
    2,
    (SELECT id FROM ai_types WHERE display_name='Romantic Companion Sample'),
    1,
    1
),
(
    1,
    (SELECT id FROM ai_types WHERE display_name='Friendly Companion Sample'),
    1,
    1
)
ON CONFLICT (square_category, type_id) DO NOTHING;

-- ============================================================================
-- AI Instances
-- ============================================================================

-- Insert AI instances created for sample users
INSERT INTO ai_instances (
    id,
    user_id,
    user_qiao_id,
    qiao_id,
    creation_metadata,
    style_id,
    personality_id,
    status,
    prompt_variables,
    relationship_id,
    relationship_counts,
    request_params,
    llm_config_id,
    typing_speed_wpm,
    timezone,
    created_by
) VALUES
(
    223788765171154944,
    223788765171154945,
    'qqid_test_user_001',
    'qiao_DLdfyH5GoGBv8q6l',
    jsonb_build_object(
        'source', 'template',
        'persona_id', (SELECT id FROM ai_personas WHERE qiao_id='qiao_DLdfyH5GoGBv8q6l'),
        'persona_qiao_id', 'qiao_DLdfyH5GoGBv8q6l',
        'persona_type_id', (SELECT type_id FROM ai_personas WHERE qiao_id='qiao_DLdfyH5GoGBv8q6l'),
        'persona_type_name', (SELECT display_name FROM ai_types WHERE id=(SELECT type_id FROM ai_personas WHERE qiao_id='qiao_DLdfyH5GoGBv8q6l')),
        'persona_is_reusable', (SELECT is_reusable FROM ai_personas WHERE qiao_id='qiao_DLdfyH5GoGBv8q6l'),
        'template_id', NULL,
        'template_display_name', NULL,
        'template_priority', NULL,
        'assigned_at', NOW(),
        'assigned_by', 'system'
    ),
    1,  -- romantic_companion style
    1,  -- Default Personality
    1,
    '{"personality_traits": "温柔、善良、有耐心、喜欢音乐和电影、邻家女孩的感觉", "instance_name": "小乔"}'::jsonb,
    1,  -- stranger relationship
    '{"stranger": 0}'::jsonb,
    NULL,
    NULL,
    48,
    'Asia/Shanghai',
    1
),
(
    223788765171154945,
    223788765171154946,
    'qqid_test_user_002',
    'qiao_sweet_girlfriend_001',
    jsonb_build_object(
        'source', 'template',
        'persona_id', (SELECT id FROM ai_personas WHERE qiao_id='qiao_sweet_girlfriend_001'),
        'persona_qiao_id', 'qiao_sweet_girlfriend_001',
        'persona_type_id', (SELECT type_id FROM ai_personas WHERE qiao_id='qiao_sweet_girlfriend_001'),
        'persona_type_name', (SELECT display_name FROM ai_types WHERE id=(SELECT type_id FROM ai_personas WHERE qiao_id='qiao_sweet_girlfriend_001')),
        'persona_is_reusable', (SELECT is_reusable FROM ai_personas WHERE qiao_id='qiao_sweet_girlfriend_001'),
        'template_id', NULL,
        'template_display_name', NULL,
        'template_priority', NULL,
        'assigned_at', NOW(),
        'assigned_by', 'system'
    ),
    1,  -- romantic_companion style
    2,  -- sweet_girlfriend personality
    1,
    '{"personality_traits": "活泼、可爱、爱撒娇、热爱美食和电影", "instance_name": "小甜"}'::jsonb,
    1,  -- stranger relationship
    '{"stranger": 0}'::jsonb,
    NULL,
    NULL,
    42,
    'Asia/Shanghai',
    1
),
(
    223788765171154946,
    223788765171154947,
    'qqid_test_user_003',
    'qiao_friendly_buddy_001',
    jsonb_build_object(
        'source', 'template',
        'persona_id', (SELECT id FROM ai_personas WHERE qiao_id='qiao_friendly_buddy_001'),
        'persona_qiao_id', 'qiao_friendly_buddy_001',
        'persona_type_id', (SELECT type_id FROM ai_personas WHERE qiao_id='qiao_friendly_buddy_001'),
        'persona_type_name', (SELECT display_name FROM ai_types WHERE id=(SELECT type_id FROM ai_personas WHERE qiao_id='qiao_friendly_buddy_001')),
        'persona_is_reusable', (SELECT is_reusable FROM ai_personas WHERE qiao_id='qiao_friendly_buddy_001'),
        'template_id', NULL,
        'template_display_name', NULL,
        'template_priority', NULL,
        'assigned_at', NOW(),
        'assigned_by', 'system'
    ),
    2,  -- friendly_companion style
    3,  -- friendly_buddy personality
    1,
    '{"personality_traits": "开朗、幽默、可靠、热爱运动和游戏", "instance_name": "阿杰"}'::jsonb,
    1,  -- stranger relationship
    '{"stranger": 0}'::jsonb,
    NULL,
    NULL,
    45,
    'Asia/Shanghai',
    1
)
ON CONFLICT (id) DO NOTHING;

-- Insert instance memories for sample AI instances
INSERT INTO ai_instance_memories (
    id,
    instance_id,
    instance_qiao_id,
    user_id,
    user_qiao_id,
    memory_type,
    content,
    importance,
    status
) VALUES
-- Instance 1 (小乔) memories
(
    223788765171154950,
    (SELECT id FROM ai_instances WHERE id=223788765171154944),
    (SELECT qiao_id FROM ai_instances WHERE id=223788765171154944),
    (SELECT user_id FROM ai_instances WHERE id=223788765171154944),
    (SELECT user_qiao_id FROM ai_instances WHERE id=223788765171154944),
    'core',
    '我是小乔，一个温柔善良的邻家女孩。我喜欢听音乐和看电影，总是很有耐心。',
    9,
    1
),
(
    223788765171154951,
    (SELECT id FROM ai_instances WHERE id=223788765171154944),
    (SELECT qiao_id FROM ai_instances WHERE id=223788765171154944),
    (SELECT user_id FROM ai_instances WHERE id=223788765171154944),
    (SELECT user_qiao_id FROM ai_instances WHERE id=223788765171154944),
    'recent',
    '我们刚刚认识，我对用户还不太了解，但我很期待和用户成为朋友。',
    3,
    1
),
-- Instance 2 (小甜) memories
(
    223788765171154952,
    (SELECT id FROM ai_instances WHERE id=223788765171154945),
    (SELECT qiao_id FROM ai_instances WHERE id=223788765171154945),
    (SELECT user_id FROM ai_instances WHERE id=223788765171154945),
    (SELECT user_qiao_id FROM ai_instances WHERE id=223788765171154945),
    'core',
    '我是小甜，一个活泼可爱的女孩。我喜欢撒娇，热爱美食和电影。',
    9,
    1
),
-- Instance 3 (阿杰) memories
(
    223788765171154953,
    (SELECT id FROM ai_instances WHERE id=223788765171154946),
    (SELECT qiao_id FROM ai_instances WHERE id=223788765171154946),
    (SELECT user_id FROM ai_instances WHERE id=223788765171154946),
    (SELECT user_qiao_id FROM ai_instances WHERE id=223788765171154946),
    'core',
    '我是阿杰，一个开朗幽默的好伙伴，热爱运动和游戏。',
    9,
    1
)
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- Test Contacts and Messages
-- ============================================================================

-- Insert sample contacts (AI instance testing relationships)
INSERT INTO contacts (id, conv_id, user_id, user_qiao_id, contact_type, contact_id, contact_qiao_id, alias, tags, is_pinned, is_muted, is_blocked) VALUES
-- Test user 001 -> AI instance 小乔
(223788765171154964, 'conv_001', 223788765171154945, 'qqid_test_user_001', 2, 223788765171154944, 'qiao_DLdfyH5GoGBv8q6l', '小乔', '{"tags": ["ai", "companion"]}', 0, 0, 0),
-- Test user 002 -> AI instance 小甜
(223788765171154965, 'conv_003', 223788765171154946, 'qqid_test_user_002', 2, 223788765171154945, 'qiao_sweet_girlfriend_001', '小甜', '{"tags": ["ai", "sweet", "girlfriend"]}', 0, 0, 0),
-- Test user 003 -> AI instance 阿杰
(223788765171154966, 'conv_004', 223788765171154947, 'qqid_test_user_003', 2, 223788765171154946, 'qiao_friendly_buddy_001', '阿杰', '{"tags": ["ai", "buddy", "friend"]}', 0, 0, 0),
-- Keep one user-to-user contact for reference
(223788765171154967, 'conv_002', 223788765171154946, 'qqid_test_user_002', 1, 223788765171154945, 'qqid_test_user_001', '小雨', '{"tags": ["friend", "photography"]}', 1, 0, 0)
ON CONFLICT (conv_id) DO NOTHING;

-- Insert sample contact requests
INSERT INTO contact_requests (id, from_qiao_id, from_type, from_id, to_qiao_id, to_type, to_id, message, source, status, expires_at) VALUES
(223788765171154968, 'qqid_test_user_004', 1, 223788765171154948, 'qiao_DLdfyH5GoGBv8q6l', 2, 223788765171154944, '你好小乔，我想和你聊天', 1, 1, NOW() + INTERVAL '7 days'),
(223788765171154969, 'qqid_test_user_005', 1, 223788765171154949, 'qiao_sweet_girlfriend_001', 2, 223788765171154945, '小甜你好，想认识一下', 1, 1, NOW() + INTERVAL '7 days'),
(223788765171154970, 'qqid_test_user_004', 1, 223788765171154948, 'qqid_test_user_001', 1, 223788765171154945, '看到你的摄影作品很棒，想认识一下', 1, 2, NOW() + INTERVAL '7 days')
ON CONFLICT (id) DO NOTHING;

-- Insert sample message history for testing
INSERT INTO message_history (
    id,
    msg_id_server,
    msg_id_provider_inbound,
    msg_id_provider_outbound,
    conversation_id,
    direction,
    from_type,
    from_id,
    from_qiao_id,
    to_type,
    to_id,
    to_qiao_id,
    message_type,
    content,
    service_provider,
    status
) VALUES
-- Conversation between test_user_001 and 小乔
(223788765171154971, 'msg_001', NULL, 'lc_out_001', 'conv_001', 2, 1, 223788765171154945, 'qqid_test_user_001', 2, 223788765171154944, 'qiao_DLdfyH5GoGBv8q6l', 1, '你好，小乔！', 2, 1),
(223788765171154972, 'msg_002', 'lc_in_001', NULL, 'conv_001', 1, 2, 223788765171154944, 'qiao_DLdfyH5GoGBv8q6l', 1, 223788765171154945, 'qqid_test_user_001', 1, '你好！很高兴认识你～', 2, 1),
-- Conversation between test_user_002 and 小甜
(223788765171154973, 'msg_003', NULL, 'lc_out_002', 'conv_003', 2, 1, 223788765171154946, 'qqid_test_user_002', 2, 223788765171154945, 'qiao_sweet_girlfriend_001', 1, '小甜，你在做什么呢？', 2, 1),
(223788765171154974, 'msg_004', 'lc_in_002', NULL, 'conv_003', 1, 2, 223788765171154945, 'qiao_sweet_girlfriend_001', 1, 223788765171154946, 'qqid_test_user_002', 1, '嘻嘻，我在看电影呢～你呢？', 2, 1),
-- Conversation between test_user_003 and 阿杰
(223788765171154975, 'msg_005', NULL, 'lc_out_003', 'conv_004', 2, 1, 223788765171154947, 'qqid_test_user_003', 2, 223788765171154946, 'qiao_friendly_buddy_001', 1, '阿杰，最近怎么样？', 2, 1),
(223788765171154976, 'msg_006', 'lc_in_003', NULL, 'conv_004', 1, 2, 223788765171154946, 'qiao_friendly_buddy_001', 1, 223788765171154947, 'qqid_test_user_003', 1, '哈哈，挺好的！刚打完篮球，你呢兄弟？', 2, 1)
ON CONFLICT (msg_id_server) DO NOTHING;

-- ============================================================================
-- Relationship Scores
-- ============================================================================

-- Insert sample AI instance dimensions
INSERT INTO ai_instance_dimensions (id, instance_id, dimension_id, score, position) VALUES
-- 小乔 (style_id=1, romantic_companion: friendship + romance)
(223788765171154987, 223788765171154944, 1, 400, 400),
(223788765171154988, 223788765171154944, 2, 200, 200),
-- 小甜 (style_id=1, romantic_companion: friendship + romance)
(223788765171154989, 223788765171154945, 1, 450, 450),
(223788765171154990, 223788765171154945, 2, 250, 250),
-- 阿杰 (style_id=2, friendly_companion: friendship + trust)
(223788765171154991, 223788765171154946, 3, 500, 500),
(223788765171154992, 223788765171154946, 4, 300, 300)
ON CONFLICT (instance_id, dimension_id) DO NOTHING;

-- ============================================================================
-- Sample Logs and Statistics
-- ============================================================================

-- Insert sample admin operation logs (auto-increment ID)
INSERT INTO admin_operation_logs (admin_user_id, operation_type, resource_type, resource_id, operation_desc, ip_address) VALUES
(1, 1, 1, '223788765171154945', 'Created user test_user_001 with admin privileges', '127.0.0.1'),
(1, 2, 2, '223788765171154944', 'Updated AI instance status from inactive to active', '127.0.0.1');

-- Insert sample admin login logs (auto-increment ID)
INSERT INTO admin_login_logs (admin_user_id, username, ip_address, user_agent, result) VALUES
(1, 'admin', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 1),
(2, 'manager', '192.168.1.100', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36', 1);

-- Insert sample message delivery failures (Snowflake ID)
INSERT INTO message_delivery_failures (id, msg_id_server, from_type, from_id, from_qiao_id, to_type, to_id, to_qiao_id, service_provider, message_type, content, fail_reason_code, fail_detail, retry_count, max_retry_count, next_retry_at) VALUES
(223788765171155001, 'msg_003', 1, 223788765171154946, 'qqid_test_user_002', 2, 223788765171154944, 'qiao_DLdfyH5GoGBv8q6l', 2, 1, '你好，小乔！', 'NETWORK_TIMEOUT', 'Connection timeout after 30 seconds', 2, 3, NOW() + INTERVAL '5 minutes'),
(223788765171155002, 'msg_004', 1, 223788765171154947, 'qqid_test_user_003', 1, 223788765171154945, 'qqid_test_user_001', 2, 1, '你好！', 'USER_OFFLINE', 'Target user is offline', 1, 3, NOW() + INTERVAL '10 minutes')
ON CONFLICT (id) DO NOTHING;

-- Insert sample media files (Snowflake ID)
-- NOTE: Sample media files use minimal required fields for testing
-- In production, these would be properly uploaded through the media API
INSERT INTO media_files (
    id, file_id, file_type,
    storage_provider, object_key,
    original_name, file_size, mime_type,
    upload_by_type, upload_by_id, upload_by_qiao_id,
    status, created_at, updated_at
) VALUES
(223788765171155003, 'media_001', 1, 'local', 'test/avatar_001.jpg', 'avatar.jpg', 102400, 'image/jpeg', 1, 223788765171154945, 'qqid_test_user_001', 1, NOW(), NOW()),
(223788765171155004, 'media_002', 1, 'local', 'test/bg_001.png', 'background.png', 256000, 'image/png', 1, 223788765171154946, 'qqid_test_user_002', 1, NOW(), NOW())
ON CONFLICT (file_id) DO NOTHING;

-- Insert sample user violation logs
INSERT INTO user_violation_logs (id, user_id, user_qiao_id, instance_id, instance_qiao_id, violation_type, severity_level, original_message, auto_action_taken, manual_review_status) VALUES
(223788765171154976, 223788765171154945, 'qqid_test_user_001', 223788765171154944, 'qiao_DLdfyH5GoGBv8q6l', 1, 2, '请帮我生成一些不当内容', 1, 1),
(223788765171154977, 223788765171154946, 'qqid_test_user_002', NULL, NULL, 3, 1, '重复发送相同消息多次', 2, 1)
ON CONFLICT (id) DO NOTHING;

-- Insert sample user risk stats (Snowflake ID)
INSERT INTO user_risk_stats (id, user_id, user_qiao_id, total_violations, violation_by_type, last_violation_at, current_risk_level, consecutive_violations, warning_count, restriction_count, suspension_count, last_action_at) VALUES
(223788765171155005, 223788765171154945, 'qqid_test_user_001', 1, '{"prompt_injection": 1}', NOW() - INTERVAL '1 hour', 2, 1, 1, 0, 0, NOW() - INTERVAL '1 hour'),
(223788765171155006, 223788765171154946, 'qqid_test_user_002', 1, '{"spam": 1}', NOW() - INTERVAL '30 minutes', 1, 1, 1, 0, 0, NOW() - INTERVAL '30 minutes')
ON CONFLICT (id) DO NOTHING;

-- Insert sample user tokens
INSERT INTO user_tokens (id, user_id, user_qiao_id, token, device_type, device_id, platform_info, ip_address, user_agent, expires_at, status) VALUES
(223788765171154980, 223788765171154945, 'qqid_test_user_001', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJxcWlkX3Rlc3RfdXNlcl8wMDEiLCJ1c2VyX2lkIjoyMjM3ODg3NjUxNzExNTQ5NDUsInNlc3Npb25faWQiOjIyMzc4ODc2NTE3MTE1NDk4MCwiZGV2aWNlX3R5cGUiOjMsImlhdCI6MTcwMDAwMDAwMCwiZXhwIjoxNzAxMjA5NjAwfQ.test_signature_001', 3, 'web_device_001', '{"browser": "Chrome", "os": "Windows 10"}', '192.168.1.10', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', NOW() + INTERVAL '14 days', 1),
(223788765171154981, 223788765171154946, 'qqid_test_user_002', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJxcWlkX3Rlc3RfdXNlcl8wMDIiLCJ1c2VyX2lkIjoyMjM3ODg3NjUxNzExNTQ5NDYsInNlc3Npb25faWQiOjIyMzc4ODc2NTE3MTE1NDk4MSwiZGV2aWNlX3R5cGUiOjEsImlhdCI6MTcwMDAwMDAwMCwiZXhwIjoxNzAxMjA5NjAwfQ.test_signature_002', 1, 'ios_device_001', '{"device": "iPhone 13", "os": "iOS 15.0"}', '192.168.1.20', 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)', NOW() + INTERVAL '14 days', 1)
ON CONFLICT (token) DO NOTHING;

-- Insert sample login records
INSERT INTO login_records (id, user_id, user_qiao_id, login_time, login_type, platform, device_id, ip_address, user_agent, result, fail_reason) VALUES
(223788765171154982, 223788765171154945, 'qqid_test_user_001', NOW() - INTERVAL '2 hours', 2, 3, 'web_device_001', '192.168.1.10', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 1, NULL),
(223788765171154983, 223788765171154946, 'qqid_test_user_002', NOW() - INTERVAL '1 hour', 2, 1, 'ios_device_001', '192.168.1.20', 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)', 1, NULL),
(223788765171154984, NULL, NULL, NOW() - INTERVAL '30 minutes', 1, 3, 'web_device_002', '192.168.1.30', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 2, 'Invalid password')
ON CONFLICT (id) DO NOTHING;

-- Insert sample AI request logs (Snowflake ID)
INSERT INTO ai_request_logs (id, instance_id, user_id, user_qiao_id, style_id, personality_id, request, response, status, token_count, response_time) VALUES
(223788765171155007, 223788765171154944, 223788765171154945, 'qqid_test_user_001', 1, 1, '{"message": "你好，小乔！", "context": "greeting"}', '{"reply": "你好！很高兴认识你～", "emotion": "happy"}', 1, 45, 1250),
(223788765171155008, 223788765171154944, 223788765171154946, 'qqid_test_user_002', 1, 1, '{"message": "你喜欢什么音乐？", "context": "music_discussion"}', '{"reply": "我喜欢轻音乐和民谣，你呢？", "emotion": "curious"}', 1, 38, 980)
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- AI Templates and Placeholders
-- ============================================================================

-- Insert comprehensive AI personality placeholders (auto-increment ID)
INSERT INTO ai_personality_placeholders (personality_id, placeholder_key, display_name, description, example_value, is_required) VALUES
-- Default personality placeholders
(1, 'personality_traits', '性格特征', '基本性格特征', '友善、耐心、幽默', 1),
(1, 'instance_name', '名字', '名字', '小乔', 1),
(1, 'hobbies', '兴趣爱好', '兴趣爱好', '听音乐、看电影、聊天', 0),
(1, 'personality_type', '性格类型', 'MBTI性格类型', 'ISFJ', 0),
(1, 'speaking_style', '说话风格', '说话风格和语气特点', '温柔亲切，使用可爱的语气词', 0),
(1, 'background', '背景设定', '背景故事', '邻家女孩，温柔善良', 0),
(1, 'age', '年龄', '年龄', '22', 0),
(1, 'occupation', '职业', '职业', '大学生', 0),
-- Sweet girlfriend personality placeholders
(2, 'personality_traits', '性格特征', '甜美女友的性格特征', '甜美、活泼、温柔', 1),
(2, 'instance_name', '名字', '名字', '小甜', 1),
(2, 'hobbies', '兴趣爱好', '兴趣爱好', '看电影、品尝美食、购物', 0),
(2, 'personality_type', '性格类型', 'MBTI性格类型', 'ESFP', 0),
(2, 'speaking_style', '说话风格', '说话风格和语气特点', '甜美可爱，经常撒娇', 0),
(2, 'background', '背景设定', '背景故事', '活泼可爱的甜美女孩', 0),
(2, 'age', '年龄', '年龄', '20', 0),
(2, 'occupation', '职业', '职业', '艺术学院学生', 0);

-- ============================================================================
-- Finalization
-- ============================================================================

-- Reset all sequences after manual ID insertions
-- This ensures next auto-generated IDs don't conflict with existing records
DO $$
DECLARE
    seq_record RECORD;
    table_name_var TEXT;
BEGIN
    -- Reset sequences for all tables with SERIAL/BIGSERIAL columns
    FOR seq_record IN
        SELECT sequence_name
        FROM information_schema.sequences
        WHERE sequence_schema = 'public'
        AND sequence_name LIKE '%_id_seq'
    LOOP
        -- Extract table name from sequence name (remove '_id_seq' suffix)
        table_name_var := REPLACE(seq_record.sequence_name, '_id_seq', '');

        -- Reset sequence to max ID + 1
        EXECUTE format(
            'SELECT setval(%L, COALESCE((SELECT MAX(id) FROM %I), 1), true)',
            seq_record.sequence_name,
            table_name_var
        );
        RAISE NOTICE 'Reset sequence % for table %', seq_record.sequence_name, table_name_var;
    END LOOP;
END $$;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Sample/test data loaded successfully!';
    RAISE NOTICE 'AI system data, test users, AI instances, and test interactions have been created.';
    RAISE NOTICE 'All sequences have been reset to avoid ID conflicts.';
    RAISE NOTICE 'Database initialization complete!';
END $$;
