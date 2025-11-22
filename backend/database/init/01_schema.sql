-- Complete PostgreSQL Database Initialization Script
-- This script creates the complete database schema for the AI chat application
-- Optimized for PostgreSQL 16 with JSONB and performance enhancements
-- Combines all initialization steps into a single comprehensive script

-- ============================================================================
-- PostgreSQL Extensions and Configuration
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Set timezone and encoding
SET timezone = 'UTC';
SET client_encoding = 'UTF8';

-- Success message for initialization start
DO $$
BEGIN
    RAISE NOTICE 'Starting complete PostgreSQL database initialization...';
    RAISE NOTICE 'Target database: %', current_database();
    RAISE NOTICE 'PostgreSQL version: %', version();
END $$;

-- ============================================================================
-- Core User Management Tables
-- ============================================================================

-- Users table - Core user account information
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    qiao_id VARCHAR(32) NOT NULL UNIQUE,
    username VARCHAR(50) NOT NULL,
    phone VARCHAR(20) UNIQUE,
    email VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255),
    is_verified INTEGER NOT NULL DEFAULT 0,
    verified_at TIMESTAMP WITH TIME ZONE,
    verify_source VARCHAR(100),
    verification_info JSONB,
    status INTEGER NOT NULL DEFAULT 1,
    user_type INTEGER NOT NULL DEFAULT 1,
    last_login TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for users table
-- Note: No additional indexes needed for MVP


-- User tokens table - JWT token management with device limits
CREATE TABLE IF NOT EXISTS user_tokens (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    user_qiao_id VARCHAR(32) NOT NULL,
    token VARCHAR(512) NOT NULL UNIQUE,
    device_type INTEGER NOT NULL,
    device_id VARCHAR(128),
    platform_info JSONB,
    ip_address INET,
    user_agent TEXT,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    status INTEGER NOT NULL DEFAULT 1,
    last_activity_at TIMESTAMP WITH TIME ZONE,
    revoked_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for user_tokens table
CREATE INDEX idx_user_tokens_user_qiao_id ON user_tokens(user_qiao_id);

-- User auths table - Third-party identity bindings (WeChat/Apple/etc.)
CREATE TABLE IF NOT EXISTS user_auths (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    user_qiao_id VARCHAR(32) NOT NULL,
    auth_type INTEGER NOT NULL,
    provider_uid VARCHAR(128) NOT NULL,
    unionid VARCHAR(64),
    app_id VARCHAR(64),
    extra_data JSONB,
    status INTEGER NOT NULL DEFAULT 1,
    revoked_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Constraints and indexes for user_auths
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_user_auths_type_provider'
    ) THEN
        ALTER TABLE user_auths ADD CONSTRAINT uq_user_auths_type_provider UNIQUE (auth_type, provider_uid);
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_user_auths_user_qiao_id ON user_auths(user_qiao_id);

-- Login records table - Login attempt tracking
CREATE TABLE IF NOT EXISTS login_records (
    id BIGINT PRIMARY KEY,
    user_id BIGINT,
    user_qiao_id VARCHAR(32),
    login_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    login_type INTEGER NOT NULL,
    platform INTEGER NOT NULL,
    device_id VARCHAR(128),
    ip_address INET,
    user_agent TEXT,
    result INTEGER NOT NULL,
    fail_reason VARCHAR(255),
    token VARCHAR(512),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);


-- ============================================================================
-- Contact Tables
-- ============================================================================

-- Contacts table - Contact relationships between users and AI
CREATE TABLE IF NOT EXISTS contacts (
    id BIGINT PRIMARY KEY,
    conv_id VARCHAR(32) NOT NULL UNIQUE,
    user_id BIGINT,
    user_qiao_id VARCHAR(32),
    contact_type INTEGER NOT NULL,
    contact_id BIGINT NOT NULL,
    contact_qiao_id VARCHAR(32) NOT NULL,
    alias VARCHAR(100),
    custom_avatar_url VARCHAR(500),
    tags JSONB,
    remark TEXT,
    is_pinned INTEGER NOT NULL DEFAULT 0,
    is_muted INTEGER NOT NULL DEFAULT 0,
    is_blocked INTEGER NOT NULL DEFAULT 0,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    -- Ensure one user cannot add the same qiao_id contact twice
    CONSTRAINT contacts_user_contact_qiao_unique UNIQUE (user_id, contact_qiao_id)
);

-- Create indexes for contacts table
CREATE INDEX idx_contacts_user_qiao_id ON contacts(user_qiao_id);
CREATE INDEX idx_contacts_contact_qiao_id ON contacts(contact_qiao_id);

-- Contact requests table - Contact application management
CREATE TABLE IF NOT EXISTS contact_requests (
    id BIGINT PRIMARY KEY,
    from_qiao_id VARCHAR(32) NOT NULL,
    from_type INTEGER NOT NULL,
    from_id BIGINT NOT NULL,
    to_qiao_id VARCHAR(32) NOT NULL,
    to_type INTEGER NOT NULL,
    to_id BIGINT,  -- Allow NULL: AI character not created yet when request is created
    message TEXT,
    source INTEGER NOT NULL,
    status INTEGER NOT NULL DEFAULT 1,
    failure_code VARCHAR(50),
    failure_detail JSONB,
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_retry_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for contact_requests table
CREATE INDEX idx_contact_requests_expires_at ON contact_requests(expires_at);
-- Composite index for worker query (status + to_type + expires_at for AI requests)
CREATE INDEX idx_contact_requests_worker_query ON contact_requests(status, to_type, expires_at) WHERE status IN (1, 8);  -- PENDING=1, PROCESSING=8
CREATE UNIQUE INDEX uniq_contact_requests_pending_pair ON contact_requests(from_qiao_id, to_qiao_id) WHERE status IN (1, 8);


-- ============================================================================
-- Square Discovery Tables
-- ============================================================================

-- Square character entries - decouple Square exposure from core profile data
CREATE TABLE IF NOT EXISTS square_character_entries (
    id SERIAL PRIMARY KEY,
    square_category VARCHAR(50) NOT NULL,
    qiao_id VARCHAR(32) NOT NULL,
    template_type_id INTEGER NOT NULL REFERENCES ai_template_types(id),
    entry_group VARCHAR(50) NOT NULL DEFAULT 'default',
    exposure_strategy VARCHAR(30) NOT NULL DEFAULT 'random',
    status INTEGER NOT NULL DEFAULT 1,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_featured_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(square_category, entry_group, qiao_id)
);

COMMENT ON TABLE square_character_entries IS 'Square discovery entries - decoupled from template/profile inventory';
COMMENT ON COLUMN square_character_entries.square_category IS 'Hardcoded Square category identifier (friend, lover, etc.)';
COMMENT ON COLUMN square_character_entries.entry_group IS 'Optional grouping for experiments/exposure slots';
COMMENT ON COLUMN square_character_entries.exposure_strategy IS 'Selection strategy hint (random/default/fixed)';
COMMENT ON COLUMN square_character_entries.status IS '1=active, 2=inactive';
COMMENT ON COLUMN square_character_entries.template_type_id IS 'Template type for filtering/experimentation (references ai_template_types)';
COMMENT ON COLUMN square_character_entries.qiao_id IS 'qiao_id validated by service layer (must correspond to ai_instances.qiao_id)';

CREATE INDEX idx_square_character_entries_status ON square_character_entries(status);
CREATE INDEX idx_square_character_entries_category ON square_character_entries(square_category);
CREATE INDEX idx_square_character_entries_template_type ON square_character_entries(template_type_id);


-- ============================================================================
-- Profile Management Tables
-- ============================================================================

-- Profiles table - Unified profile management for users, AI, and official accounts
CREATE TABLE IF NOT EXISTS profiles (
    id BIGINT PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    owner_qiao_id VARCHAR(32) NOT NULL,
    owner_type INTEGER NOT NULL,
    nickname VARCHAR(100),
    gender INTEGER,
    avatar_file_id BIGINT,
    avatar_url VARCHAR(500),
    avatar_prompt TEXT,
    bio TEXT,
    region VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(owner_qiao_id, owner_type)
);

-- Create indexes for profiles table
-- Note: No additional indexes needed for MVP


-- User profile logs table - Profile change tracking for users only
CREATE TABLE IF NOT EXISTS user_profile_logs (
    id BIGINT PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    owner_qiao_id VARCHAR(32) NOT NULL,
    owner_type INTEGER NOT NULL,
    modified_by_type INTEGER NOT NULL,
    field_name VARCHAR(50) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    change_reason VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for user_profile_logs table
CREATE INDEX idx_user_profile_logs_owner_qiao_id ON user_profile_logs(owner_qiao_id);
CREATE INDEX idx_user_profile_logs_created_at ON user_profile_logs(created_at);
CREATE INDEX idx_user_profile_logs_owner_id ON user_profile_logs(owner_id);
CREATE INDEX idx_user_profile_logs_field_name ON user_profile_logs(field_name);
CREATE INDEX idx_user_profile_logs_modified_by_type ON user_profile_logs(modified_by_type);


-- ============================================================================
-- Message System Tables
-- ============================================================================

-- Message history table - All message records (only successful sends)
CREATE TABLE IF NOT EXISTS message_history (
    id BIGINT PRIMARY KEY,
    direction INTEGER NOT NULL,
    platform INTEGER,
    conversation_id VARCHAR(32) NOT NULL,
    msg_id_server VARCHAR(64) NOT NULL UNIQUE,
    msg_id_provider_inbound VARCHAR(128),
    msg_id_provider_outbound VARCHAR(128),
    msg_id_client VARCHAR(64),
    client_sent_time TIMESTAMP WITH TIME ZONE,
    sent_at TIMESTAMP WITH TIME ZONE,
    from_type INTEGER NOT NULL,
    from_id BIGINT NOT NULL,
    from_qiao_id VARCHAR(32) NOT NULL,
    to_type INTEGER NOT NULL,
    to_id BIGINT NOT NULL,
    to_qiao_id VARCHAR(32) NOT NULL,
    service_provider INTEGER NOT NULL,
    message_type INTEGER NOT NULL,
    content TEXT,
    status INTEGER NOT NULL DEFAULT 1,
    message_metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_message_history_conv_client_id UNIQUE (conversation_id, msg_id_client)
);

-- Create indexes for message_history table
CREATE INDEX idx_message_history_conversation_id ON message_history(conversation_id);
CREATE INDEX idx_message_history_from_qiao_id ON message_history(from_qiao_id);
CREATE INDEX idx_message_history_to_qiao_id ON message_history(to_qiao_id);
CREATE INDEX idx_message_history_created_at ON message_history(created_at);
CREATE INDEX idx_message_history_msg_id_client ON message_history(msg_id_client);
-- GIN index for JSONB message_metadata
CREATE INDEX idx_message_history_metadata_gin ON message_history USING GIN(message_metadata);

-- Notification push history table - Track all notification messages
CREATE TABLE IF NOT EXISTS notification_push_history (
    id BIGINT PRIMARY KEY,
    to_qiao_id VARCHAR(32) NOT NULL,
    notification_type INTEGER NOT NULL,
    action_data JSONB NOT NULL,
    status INTEGER NOT NULL DEFAULT 1,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create index for notification_push_history table
CREATE INDEX idx_notification_push_created_at ON notification_push_history(created_at);

-- Message delivery failures table - Failed message retry management
CREATE TABLE IF NOT EXISTS message_delivery_failures (
    id BIGINT PRIMARY KEY,
    msg_id_server VARCHAR(64) NOT NULL,
    from_id BIGINT NOT NULL,
    from_qiao_id VARCHAR(32) NOT NULL,
    from_type INTEGER NOT NULL,
    to_id BIGINT NOT NULL,
    to_qiao_id VARCHAR(32) NOT NULL,
    to_type INTEGER NOT NULL,
    service_provider INTEGER NOT NULL,
    message_type INTEGER NOT NULL,
    content TEXT,
    fail_reason_code VARCHAR(50),
    fail_detail TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retry_count INTEGER NOT NULL DEFAULT 3,
    next_retry_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for message_delivery_failures table
-- Note: No additional indexes needed for MVP


-- Media files table - Unified media file management
CREATE TABLE IF NOT EXISTS media_files (
    id BIGINT PRIMARY KEY,
    file_id VARCHAR(32) NOT NULL UNIQUE,
    file_type INTEGER NOT NULL,
    original_name VARCHAR(255),
    file_path VARCHAR(500) NOT NULL,
    file_url VARCHAR(500) NOT NULL,
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    upload_by_type INTEGER NOT NULL,
    upload_by_id BIGINT NOT NULL,
    upload_by_qiao_id VARCHAR(32) NOT NULL,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for media_files table
-- Note: No additional indexes needed for MVP


-- Preset assets table - Unified preset resource management (avatars, emoticons, etc.)
CREATE TABLE IF NOT EXISTS preset_assets (
    id SERIAL PRIMARY KEY,
    asset_type INTEGER NOT NULL,
    name VARCHAR(50) NOT NULL UNIQUE,
    category INTEGER NOT NULL,
    is_client_preset INTEGER NOT NULL DEFAULT 1,
    file_id BIGINT,
    url VARCHAR(500) NOT NULL,
    prompt TEXT,
    description VARCHAR(200),
    status INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for preset_assets table
CREATE INDEX idx_preset_assets_asset_type ON preset_assets(asset_type);
CREATE INDEX idx_preset_assets_category ON preset_assets(category);
CREATE INDEX idx_preset_assets_status ON preset_assets(status);
CREATE INDEX idx_preset_assets_sort_order ON preset_assets(sort_order);

-- ============================================================================
-- AI System Tables
-- ============================================================================

-- AI styles table - AI style definitions
CREATE TABLE IF NOT EXISTS ai_styles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    usage_count INTEGER NOT NULL DEFAULT 0,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_styles table
-- Note: No additional indexes needed for MVP


-- AI relationships table - Relationship type definitions
CREATE TABLE IF NOT EXISTS ai_relationships (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    prompt_fragment TEXT,
    usage_count INTEGER NOT NULL DEFAULT 0,
    status INTEGER NOT NULL DEFAULT 1,
    wake_time_min_ms INTEGER NOT NULL DEFAULT 3000 CHECK (wake_time_min_ms >= 500),
    wake_time_max_ms INTEGER NOT NULL DEFAULT 3000 CHECK (wake_time_max_ms >= wake_time_min_ms),
    wake_time_bias VARCHAR(20) NOT NULL DEFAULT 'balanced' CHECK (wake_time_bias <> ''),
    wake_window_ms INTEGER NOT NULL DEFAULT 60000 CHECK (wake_window_ms >= 0),
    wake_time_adjustment VARCHAR(20) NOT NULL DEFAULT 'random_half' CHECK (wake_time_adjustment <> ''),
    no_reply_probability DECIMAL(3,2) NOT NULL DEFAULT 0.00 CHECK (no_reply_probability >= 0 AND no_reply_probability <= 1),
    followup_delay_ms INTEGER NOT NULL DEFAULT 5000 CHECK (followup_delay_ms >= 0),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Add comments for ai_relationships table
COMMENT ON COLUMN ai_relationships.wake_time_min_ms IS 'Minimum wake wait time (ms), minimum 500ms';
COMMENT ON COLUMN ai_relationships.wake_time_max_ms IS 'Maximum wake wait time (ms), must be >= min';
COMMENT ON COLUMN ai_relationships.wake_time_bias IS 'Sampling bias: balanced/centered/fast/slow/very_fast/very_slow';
COMMENT ON COLUMN ai_relationships.wake_window_ms IS 'Skip wake if last message within this window (ms)';
COMMENT ON COLUMN ai_relationships.wake_time_adjustment IS 'Wait time adjustment when new message arrives';
COMMENT ON COLUMN ai_relationships.no_reply_probability IS 'Probability of not replying after wake (0.00-1.00)';
COMMENT ON COLUMN ai_relationships.followup_delay_ms IS 'Delay between outgoing and follow-up messages in milliseconds';

-- Create indexes for ai_relationships table
-- Note: No additional indexes needed for MVP


-- AI dimensions table - Dimension definitions
CREATE TABLE IF NOT EXISTS ai_dimensions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    display_name VARCHAR(100),
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_dimensions table
-- Note: No additional indexes needed for MVP


-- AI style dimensions table - Style-specific dimension configurations
CREATE TABLE IF NOT EXISTS ai_style_dimensions (
    id SERIAL PRIMARY KEY,
    style_id INTEGER NOT NULL,
    dimension_id INTEGER NOT NULL,
    initial_position INTEGER NOT NULL CHECK (initial_position >= 0 AND initial_position <= 1000),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(style_id, dimension_id)
);

-- Create indexes for ai_style_dimensions table
CREATE INDEX idx_ai_style_dimensions_style_id ON ai_style_dimensions(style_id);
CREATE INDEX idx_ai_style_dimensions_dimension_id ON ai_style_dimensions(dimension_id);


-- AI dimension relationship mappings table - Dimension to relationship mapping
CREATE TABLE IF NOT EXISTS ai_dimension_relationship_mappings (
    id SERIAL PRIMARY KEY,
    dimension_id INTEGER NOT NULL,
    start_position INTEGER NOT NULL,
    end_position INTEGER NOT NULL,
    relationship_id INTEGER NOT NULL,
    priority INTEGER NOT NULL DEFAULT 1,
    limit_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_dimension_relationship_mappings table
CREATE INDEX idx_ai_dim_rel_mappings_dimension_id ON ai_dimension_relationship_mappings(dimension_id);
CREATE INDEX idx_ai_dim_rel_mappings_relationship_id ON ai_dimension_relationship_mappings(relationship_id);


-- AI personalities table - Personality templates
CREATE TABLE IF NOT EXISTS ai_personalities (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    prompt TEXT NOT NULL,
    json_schema JSONB,
    usage_count INTEGER NOT NULL DEFAULT 0,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_personalities table
-- Note: No additional indexes needed for MVP


-- AI personality placeholders table - Placeholder definitions
CREATE TABLE IF NOT EXISTS ai_personality_placeholders (
    id SERIAL PRIMARY KEY,
    personality_id INTEGER NOT NULL,
    placeholder_key VARCHAR(100) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    description VARCHAR(500),
    example_value TEXT,
    is_required INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_personality_placeholders table
-- Note: No additional indexes needed for MVP


-- AI template types table - Internal management types (NOT related to Square categories)
CREATE TABLE IF NOT EXISTS ai_template_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE ai_template_types IS 'AI template types - INTERNAL inventory groupings, NOT related to Square categories';
COMMENT ON COLUMN ai_template_types.name IS 'Internal type identifier';
COMMENT ON COLUMN ai_template_types.display_name IS 'Display name for admin dashboard';

-- Create indexes for ai_template_types table
-- Note: No additional indexes needed for MVP


-- AI templates table - AI core configuration templates (renamed from ai_character_templates)
CREATE TABLE IF NOT EXISTS ai_templates (
    id SERIAL PRIMARY KEY,
    template_type_id INTEGER NOT NULL REFERENCES ai_template_types(id),
    style_id INTEGER NOT NULL,
    personality_id INTEGER NOT NULL,
    memory TEXT,
    prompt_variables JSONB,
    request_params JSONB,
    typing_speed_wpm INTEGER NOT NULL,
    display_name VARCHAR(100),
    position_mapping_config JSONB,
    is_reusable INTEGER NOT NULL DEFAULT 1,
    priority INTEGER NOT NULL DEFAULT 1,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE ai_templates IS 'AI templates - core configuration templates for AI characters';
COMMENT ON COLUMN ai_templates.template_type_id IS 'Template type ID (internal management), NOT related to Square categories';
COMMENT ON COLUMN ai_templates.request_params IS 'Template-level LLM request parameters (temperature, max_tokens, etc.) - inherited by character instances';
COMMENT ON COLUMN ai_templates.is_reusable IS '1=reusable (can create multiple characters), 0=non-reusable (can only create once)';
COMMENT ON COLUMN ai_templates.priority IS 'Priority for selection, lower number = higher priority (non-reusable templates have priority)';
COMMENT ON COLUMN ai_templates.status IS '1=active, 2=inactive, 3=used (only for is_reusable=0, after being used once)';

-- Create indexes for ai_templates table
CREATE INDEX idx_ai_templates_template_type ON ai_templates(template_type_id);
CREATE INDEX idx_ai_templates_usage ON ai_templates(template_type_id, status, is_reusable);


-- AI character profiles table - Manages unique qiao_id for characters (replaces ai_profile_templates)
CREATE TABLE IF NOT EXISTS ai_instances (
    id BIGINT PRIMARY KEY,
    qiao_id VARCHAR(32) NOT NULL UNIQUE,
    template_type_id INTEGER NOT NULL REFERENCES ai_template_types(id),
    is_reusable INTEGER NOT NULL DEFAULT 1,
    usage_count INTEGER NOT NULL DEFAULT 0,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE ai_instances IS 'AI character profiles - manages unique qiao_id and reusability (similar to product SKU)';
COMMENT ON COLUMN ai_instances.qiao_id IS 'External unique identifier, visible to users in Square';
COMMENT ON COLUMN ai_instances.template_type_id IS 'Template type ID (internal management), NOT related to Square categories';
COMMENT ON COLUMN ai_instances.is_reusable IS '1=reusable (multiple users can add), 0=non-reusable (only one user can add)';
COMMENT ON COLUMN ai_instances.usage_count IS 'Number of times this profile has been added (statistics)';
COMMENT ON COLUMN ai_instances.status IS '1=active (visible in Square), 2=inactive (hidden from Square), 3=used (only for is_reusable=0, after being added once)';

-- Create indexes for ai_instances table
CREATE INDEX idx_ai_instances_template_type ON ai_instances(template_type_id);
CREATE INDEX idx_ai_instances_status ON ai_instances(status);


-- AI characters table - AI character instances
CREATE TABLE IF NOT EXISTS ai_instances (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    user_qiao_id VARCHAR(32) NOT NULL,
    qiao_id VARCHAR(32) NOT NULL,
    template_type_id INTEGER NOT NULL REFERENCES ai_template_types(id),
    character_profile_id BIGINT NOT NULL REFERENCES ai_instances(id),
    style_id INTEGER NOT NULL,
    personality_id INTEGER NOT NULL,
    status INTEGER NOT NULL DEFAULT 1,
    memory TEXT,
    prompt_variables JSONB,
    relationship_id INTEGER,
    relationship_counts JSONB,
    request_params JSONB,
    typing_speed_wpm INTEGER NOT NULL,
    timezone VARCHAR(50) NOT NULL DEFAULT 'Asia/Shanghai',
    created_by INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT ai_instances_user_profile_unique UNIQUE (user_id, character_profile_id)
);

-- Create indexes for ai_instances table
CREATE INDEX idx_ai_instances_user_id ON ai_instances(user_id);
CREATE INDEX idx_ai_instances_user_qiao_id ON ai_instances(user_qiao_id);
CREATE INDEX idx_ai_instances_qiao_id ON ai_instances(qiao_id);
CREATE INDEX idx_ai_instanceslate_type ON ai_instances(template_type_id);
CREATE INDEX idx_ai_instances_profile ON ai_instances(character_profile_id);
CREATE INDEX idx_ai_instances_style_id ON ai_instances(style_id);
CREATE INDEX idx_ai_instances_personality_id ON ai_instances(personality_id);

-- Add comments for fields
COMMENT ON TABLE ai_instances IS 'AI character instances - created when users add contacts';
COMMENT ON COLUMN ai_instances.qiao_id IS 'External character identifier (can be duplicate, multiple users can add same character)';
COMMENT ON COLUMN ai_instances.template_type_id IS 'Template type ID (internal management)';
COMMENT ON COLUMN ai_instances.character_profile_id IS 'Associated character profile ID';
COMMENT ON COLUMN ai_instances.user_id IS 'Owning user ID (each row belongs to exactly one user)';
COMMENT ON COLUMN ai_instances.user_qiao_id IS 'Owning user qiao_id';
COMMENT ON COLUMN ai_instances.status IS '1=active, 2=inactive, 3=blocking (AI has blocked the user)';
COMMENT ON COLUMN ai_instances.request_params IS 'AI character request parameters configuration (JSON format) - can override default LLM settings';
COMMENT ON COLUMN ai_instances.timezone IS 'IANA timezone for the character (e.g., Asia/Shanghai)';

-- AI message buffer table - aggregation windows for inbound messages
CREATE TABLE IF NOT EXISTS ai_message_buffer (
    id BIGINT PRIMARY KEY,
    user_qiao_id VARCHAR(32) NOT NULL,
    character_qiao_id VARCHAR(32) NOT NULL,
    aggregate_state SMALLINT NOT NULL,
    micro_expires_at_ms BIGINT,
    macro_expires_at_ms BIGINT,
    buffer_expires_at_ms BIGINT,
    wake_expires_at_ms BIGINT,
    last_message_category VARCHAR(32),
    first_msg_id_client VARCHAR(64),
    last_msg_id_client VARCHAR(64),
    message_count INTEGER NOT NULL DEFAULT 1,
    last_msg_time_ms BIGINT,
    locked_at TIMESTAMP WITH TIME ZONE,
    wake_adjustment_count SMALLINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_wake_expires_state CHECK (
        (aggregate_state = 0 AND wake_expires_at_ms IS NOT NULL)
        OR (aggregate_state <> 0 AND wake_expires_at_ms IS NULL)
    )
);

CREATE INDEX idx_ai_message_buffer_session_state ON ai_message_buffer(user_qiao_id, character_qiao_id, aggregate_state);
CREATE INDEX idx_ai_message_buffer_micro ON ai_message_buffer(micro_expires_at_ms) WHERE aggregate_state = 1 AND micro_expires_at_ms IS NOT NULL;
CREATE INDEX idx_ai_message_buffer_macro ON ai_message_buffer(macro_expires_at_ms) WHERE aggregate_state = 1 AND macro_expires_at_ms IS NOT NULL;
CREATE UNIQUE INDEX idx_ai_message_buffer_locked ON ai_message_buffer(user_qiao_id, character_qiao_id) WHERE aggregate_state = 2;
CREATE INDEX idx_ai_message_buffer_expire_scan ON ai_message_buffer(user_qiao_id, character_qiao_id, buffer_expires_at_ms) WHERE aggregate_state = 1 AND buffer_expires_at_ms IS NOT NULL;
CREATE INDEX idx_ai_message_buffer_wake_scan ON ai_message_buffer(wake_expires_at_ms) WHERE aggregate_state = 0 AND wake_expires_at_ms IS NOT NULL;

COMMENT ON COLUMN ai_message_buffer.wake_expires_at_ms IS 'Wake timer expiration (ms), NULL if already awake or in OPEN state';
COMMENT ON COLUMN ai_message_buffer.wake_adjustment_count IS 'Number of times wake time was adjusted by new messages';

-- AI conversation items table - simple message fields
CREATE TABLE IF NOT EXISTS ai_conversation_items (
    id BIGINT PRIMARY KEY,
    user_qiao_id VARCHAR(32) NOT NULL,
    character_qiao_id VARCHAR(32) NOT NULL,
    role VARCHAR(20) NOT NULL,
    message_type VARCHAR(20) NOT NULL DEFAULT 'text',
    text_content TEXT,
    media_url TEXT,
    media_metadata JSONB,
    client_msg_ids TEXT[] NOT NULL DEFAULT '{}',
    buffer_id BIGINT,
    is_excluded_from_context SMALLINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_ai_conversation_items_user_buffer CHECK (
        (role = 'user' AND buffer_id IS NOT NULL) OR (role <> 'user')
    ),
    CONSTRAINT ck_ai_conversation_items_content CHECK (
        (message_type = 'text' AND text_content IS NOT NULL AND media_url IS NULL)
        OR (message_type IN ('image', 'audio') AND media_url IS NOT NULL)
    )
);

COMMENT ON COLUMN ai_conversation_items.buffer_id IS 'Associated buffer ID (references ai_message_buffer.id, no FK constraint)';
COMMENT ON COLUMN ai_conversation_items.media_metadata IS 'Media metadata (dimensions, duration, transcript, etc.)';
COMMENT ON COLUMN ai_conversation_items.is_excluded_from_context IS 'Context status enum: 0=included, 1=excluded';

CREATE INDEX idx_ai_conv_items_session ON ai_conversation_items(user_qiao_id, character_qiao_id, created_at DESC);
CREATE INDEX idx_ai_conv_items_buffer ON ai_conversation_items(buffer_id) WHERE buffer_id IS NOT NULL;
CREATE INDEX idx_ai_conv_items_text_search ON ai_conversation_items USING gin(text_content gin_trgm_ops);
CREATE INDEX idx_ai_conv_items_excluded ON ai_conversation_items(user_qiao_id, character_qiao_id, created_at DESC) WHERE is_excluded_from_context = 1;

-- AI conversation archive table - cold storage for history
CREATE TABLE IF NOT EXISTS ai_conversation_items_archive (
    id BIGINT PRIMARY KEY,
    user_qiao_id VARCHAR(32) NOT NULL,
    character_qiao_id VARCHAR(32) NOT NULL,
    role VARCHAR(20) NOT NULL,
    message_type VARCHAR(20) NOT NULL DEFAULT 'text',
    text_content TEXT,
    media_url TEXT,
    media_metadata JSONB,
    client_msg_ids TEXT[] NOT NULL DEFAULT '{}',
    buffer_id BIGINT,
    is_excluded_from_context SMALLINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    archived_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON COLUMN ai_conversation_items_archive.buffer_id IS 'Associated buffer ID (references ai_message_buffer.id, no FK constraint)';
COMMENT ON COLUMN ai_conversation_items_archive.media_metadata IS 'Media metadata (dimensions, duration, transcript, etc.)';
COMMENT ON COLUMN ai_conversation_items_archive.is_excluded_from_context IS 'Context status enum: 0=included, 1=excluded';

CREATE INDEX idx_ai_conv_items_archive_session ON ai_conversation_items_archive(user_qiao_id, character_qiao_id, created_at DESC);


-- AI character dimensions table - AI character dimension scoring data
CREATE TABLE IF NOT EXISTS ai_character_dimensions (
    id BIGINT PRIMARY KEY,
    character_id BIGINT NOT NULL,
    dimension_id INTEGER NOT NULL,
    score INTEGER NOT NULL,
    position INTEGER NOT NULL,
    position_mapping_algorithm INTEGER DEFAULT 1,
    position_mapping_params JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(character_id, dimension_id)
);

-- Create indexes for ai_character_dimensions table
CREATE INDEX idx_ai_character_dimensions_character_id ON ai_character_dimensions(character_id);
CREATE INDEX idx_ai_character_dimensions_dimension_id ON ai_character_dimensions(dimension_id);


-- AI request logs table - AI request and response logging
CREATE TABLE IF NOT EXISTS ai_request_logs (
    id BIGINT PRIMARY KEY,
    character_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    style_id INTEGER NOT NULL,
    personality_id INTEGER NOT NULL,
    request_type VARCHAR(20) NOT NULL DEFAULT 'production',
    provider_name VARCHAR(50),
    model_name VARCHAR(100),
    llm_config_id INTEGER,
    response_id VARCHAR(64),
    cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
    buffer_id BIGINT,
    request JSONB NOT NULL,
    response JSONB,
    status INTEGER NOT NULL,
    token_count INTEGER,
    response_time INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_ai_request_logs_response_id ON ai_request_logs(response_id);

-- llm_session_cache removed in refactor (Responses API session cache conflicts with dynamic prompts)


-- ============================================================================
-- Security Monitoring Tables
-- ============================================================================

-- User violation logs table - User security violation tracking
CREATE TABLE IF NOT EXISTS user_violation_logs (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    user_qiao_id VARCHAR(32) NOT NULL,
    character_id BIGINT,
    character_qiao_id VARCHAR(32),
    violation_type INTEGER NOT NULL,
    severity_level INTEGER NOT NULL,
    original_message TEXT NOT NULL,
    auto_action_taken INTEGER NOT NULL DEFAULT 1,
    manual_review_status INTEGER NOT NULL DEFAULT 1,
    reviewer_id INTEGER,
    review_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for user_violation_logs table
-- Note: No additional indexes needed for MVP


-- User risk stats table - User security statistics aggregation
CREATE TABLE IF NOT EXISTS user_risk_stats (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE,
    user_qiao_id VARCHAR(32) NOT NULL UNIQUE,
    total_violations INTEGER NOT NULL DEFAULT 0,
    violation_by_type JSONB NOT NULL DEFAULT '{}',
    last_violation_at TIMESTAMP WITH TIME ZONE,
    current_risk_level INTEGER NOT NULL DEFAULT 1,
    consecutive_violations INTEGER NOT NULL DEFAULT 0,
    warning_count INTEGER NOT NULL DEFAULT 0,
    restriction_count INTEGER NOT NULL DEFAULT 0,
    suspension_count INTEGER NOT NULL DEFAULT 0,
    last_action_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for user_risk_stats table
-- Note: No additional indexes needed for MVP


-- ============================================================================
-- System Configuration Tables
-- ============================================================================

-- System config table - System-wide configuration parameters
CREATE TABLE IF NOT EXISTS system_configs (
    id SERIAL PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value TEXT NOT NULL,
    default_value TEXT NOT NULL,
    config_type INTEGER NOT NULL,
    description TEXT,
    updated_by INTEGER,
    group_name VARCHAR(50),
    allowed_values JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for system_configs table
-- Note: No additional indexes needed for MVP


-- ============================================================================
-- Statistics Tables
-- ============================================================================

-- User statistics tables (daily/weekly/monthly)
CREATE TABLE IF NOT EXISTS stats_user_daily (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL UNIQUE,
    total_users INTEGER NOT NULL DEFAULT 0,
    new_users INTEGER NOT NULL DEFAULT 0,
    active_users INTEGER NOT NULL DEFAULT 0,
    subscriptions INTEGER NOT NULL DEFAULT 0,
    new_subscriptions INTEGER NOT NULL DEFAULT 0,
    canceled_subscriptions INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stats_user_weekly (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL UNIQUE,
    total_users INTEGER NOT NULL DEFAULT 0,
    new_users INTEGER NOT NULL DEFAULT 0,
    active_users INTEGER NOT NULL DEFAULT 0,
    subscriptions INTEGER NOT NULL DEFAULT 0,
    new_subscriptions INTEGER NOT NULL DEFAULT 0,
    canceled_subscriptions INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stats_user_monthly (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL UNIQUE,
    total_users INTEGER NOT NULL DEFAULT 0,
    new_users INTEGER NOT NULL DEFAULT 0,
    active_users INTEGER NOT NULL DEFAULT 0,
    subscriptions INTEGER NOT NULL DEFAULT 0,
    new_subscriptions INTEGER NOT NULL DEFAULT 0,
    canceled_subscriptions INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Revenue statistics tables (daily/weekly/monthly)
CREATE TABLE IF NOT EXISTS stats_revenue_daily (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL UNIQUE,
    total_revenue DECIMAL(15,2) NOT NULL DEFAULT 0,
    orders_count INTEGER NOT NULL DEFAULT 0,
    avg_order_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    refund_amount DECIMAL(15,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stats_revenue_weekly (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL UNIQUE,
    total_revenue DECIMAL(15,2) NOT NULL DEFAULT 0,
    orders_count INTEGER NOT NULL DEFAULT 0,
    avg_order_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    refund_amount DECIMAL(15,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stats_revenue_monthly (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL UNIQUE,
    total_revenue DECIMAL(15,2) NOT NULL DEFAULT 0,
    orders_count INTEGER NOT NULL DEFAULT 0,
    avg_order_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    refund_amount DECIMAL(15,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Message statistics tables (daily/weekly/monthly)
CREATE TABLE IF NOT EXISTS stats_message_daily (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL UNIQUE,
    total_messages INTEGER NOT NULL DEFAULT 0,
    avg_messages_per_user DECIMAL(10,2) NOT NULL DEFAULT 0,
    active_conversations INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stats_message_weekly (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL UNIQUE,
    total_messages INTEGER NOT NULL DEFAULT 0,
    avg_messages_per_user DECIMAL(10,2) NOT NULL DEFAULT 0,
    active_conversations INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stats_message_monthly (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL UNIQUE,
    total_messages INTEGER NOT NULL DEFAULT 0,
    avg_messages_per_user DECIMAL(10,2) NOT NULL DEFAULT 0,
    active_conversations INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- AI statistics tables (daily/weekly/monthly)
CREATE TABLE IF NOT EXISTS stats_ai_daily (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL UNIQUE,
    ai_instances INTEGER NOT NULL DEFAULT 0,
    active_ai_instances INTEGER NOT NULL DEFAULT 0,
    ai_requests_count INTEGER NOT NULL DEFAULT 0,
    avg_ai_requests_per_user DECIMAL(10,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stats_ai_weekly (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL UNIQUE,
    ai_instances INTEGER NOT NULL DEFAULT 0,
    active_ai_instances INTEGER NOT NULL DEFAULT 0,
    ai_requests_count INTEGER NOT NULL DEFAULT 0,
    avg_ai_requests_per_user DECIMAL(10,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stats_ai_monthly (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL UNIQUE,
    ai_instances INTEGER NOT NULL DEFAULT 0,
    active_ai_instances INTEGER NOT NULL DEFAULT 0,
    ai_requests_count INTEGER NOT NULL DEFAULT 0,
    avg_ai_requests_per_user DECIMAL(10,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- Admin Management Tables
-- ============================================================================

-- Admin users table - Backend admin accounts
CREATE TABLE IF NOT EXISTS admin_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role INTEGER NOT NULL,
    status INTEGER NOT NULL DEFAULT 1,
    last_login TIMESTAMP WITH TIME ZONE,
    login_count INTEGER NOT NULL DEFAULT 0,
    created_by INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for admin_users table
-- Note: No additional indexes needed for MVP


-- Admin operation logs table - Admin operation tracking
CREATE TABLE IF NOT EXISTS admin_operation_logs (
    id SERIAL PRIMARY KEY,
    admin_user_id INTEGER NOT NULL,
    operation_type INTEGER NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(100),
    resource_name VARCHAR(255),
    operation_desc TEXT NOT NULL,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for admin_operation_logs table
-- Note: No additional indexes needed for MVP


-- Admin login logs table - Admin login tracking
CREATE TABLE IF NOT EXISTS admin_login_logs (
    id SERIAL PRIMARY KEY,
    admin_user_id INTEGER,
    username VARCHAR(50) NOT NULL,
    user_agent TEXT,
    ip_address INET,
    result INTEGER NOT NULL,
    fail_reason VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for admin_login_logs table
-- Note: No additional indexes needed for MVP


-- ============================================================================
-- LLM Configuration Tables
-- ============================================================================

-- LLM providers table - LLM provider configuration
CREATE TABLE IF NOT EXISTS llm_providers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    display_name VARCHAR(100) NOT NULL UNIQUE,
    api_key_env VARCHAR(100),
    base_url VARCHAR(500),
    default_model VARCHAR(100),
    supports_streaming INTEGER NOT NULL,
    supports_json_schema INTEGER NOT NULL,
    supports_thinking INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Migrate existing table if it exists (for development/upgrade scenarios)
-- Add api_key_env column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'llm_providers' AND column_name = 'api_key_env'
    ) THEN
        ALTER TABLE llm_providers ADD COLUMN api_key_env VARCHAR(100);
    END IF;
END $$;

-- Remove old UNIQUE constraint on name if it exists
ALTER TABLE llm_providers DROP CONSTRAINT IF EXISTS llm_providers_name_key;

-- Add UNIQUE constraint on display_name if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'llm_providers_display_name_key'
    ) THEN
        ALTER TABLE llm_providers ADD CONSTRAINT llm_providers_display_name_key UNIQUE (display_name);
    END IF;
END $$;

COMMENT ON COLUMN llm_providers.name IS 'Provider identifier (doubao, openai, claude, etc.)';
COMMENT ON COLUMN llm_providers.display_name IS 'Display name for UI (must be unique)';
COMMENT ON COLUMN llm_providers.api_key_env IS 'Environment variable name for API key (optional, defaults to {NAME}_API_KEY)';

-- Create indexes for llm_providers table
-- Note: No additional indexes needed for MVP


-- LLM configs table - LLM runtime configuration
CREATE TABLE IF NOT EXISTS llm_configs (
    id SERIAL PRIMARY KEY,
    provider_id INTEGER NOT NULL,
    name VARCHAR(50) NOT NULL UNIQUE,
    model_name VARCHAR(100),
    temperature DECIMAL(3,2),
    max_tokens INTEGER,
    timeout_seconds INTEGER,
    thinking_mode VARCHAR(20) NOT NULL DEFAULT 'auto',
    top_p DECIMAL(3,2) NOT NULL DEFAULT 0.70,
    frequency_penalty DECIMAL(3,2) NOT NULL DEFAULT 0.00,
    presence_penalty DECIMAL(3,2) NOT NULL DEFAULT 0.00,
    stop_sequences JSONB NOT NULL DEFAULT '[]'::jsonb,
    json_schema_mode VARCHAR(20),
    default_tools JSONB NOT NULL DEFAULT '[]'::jsonb,
    default_tool_choice VARCHAR(30) NOT NULL DEFAULT 'auto',
    parallel_tool_calls BOOLEAN NOT NULL DEFAULT FALSE,
    max_tool_calls SMALLINT NOT NULL DEFAULT 1,
    default_extra_headers JSONB NOT NULL DEFAULT '{}'::jsonb,
    default_extra_query JSONB NOT NULL DEFAULT '{}'::jsonb,
    enable_streaming BOOLEAN NOT NULL DEFAULT FALSE,
    status INTEGER NOT NULL DEFAULT 1,
    priority INTEGER NOT NULL DEFAULT 1,
    extra_params JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT check_thinking_mode CHECK (thinking_mode <> ''),
    CONSTRAINT check_top_p CHECK (top_p >= 0 AND top_p <= 1),
    CONSTRAINT check_frequency_penalty CHECK (frequency_penalty >= -2 AND frequency_penalty <= 2),
    CONSTRAINT check_presence_penalty CHECK (presence_penalty >= -2 AND presence_penalty <= 2),
    CONSTRAINT check_default_tool_choice CHECK (default_tool_choice <> ''),
    CONSTRAINT check_max_tool_calls CHECK (max_tool_calls >= 0)
);

COMMENT ON COLUMN llm_configs.json_schema_mode IS 'JSON Schema support status: strict=verified supported, disabled=verified not supported, auto=not verified (default)';
COMMENT ON COLUMN llm_configs.thinking_mode IS 'Thinking mode: enabled=force on, disabled=force off, auto=let model decide';
COMMENT ON COLUMN llm_configs.top_p IS 'Nucleus sampling threshold [0, 1]. Controls diversity of output.';
COMMENT ON COLUMN llm_configs.frequency_penalty IS 'Frequency penalty [-2, 2]. Reduces repetition based on token frequency.';
COMMENT ON COLUMN llm_configs.presence_penalty IS 'Presence penalty [-2, 2]. Encourages new topics based on token presence.';
COMMENT ON COLUMN llm_configs.stop_sequences IS 'Stop sequences (max 4 strings). Model stops when encountering these strings.';
COMMENT ON COLUMN llm_configs.default_tools IS 'Default tool definitions in JSON array form';
COMMENT ON COLUMN llm_configs.default_tool_choice IS 'Tool choice behavior: auto/none/required';
COMMENT ON COLUMN llm_configs.parallel_tool_calls IS 'Allow provider to execute tools in parallel';
COMMENT ON COLUMN llm_configs.max_tool_calls IS 'Maximum number of tool calls allowed per request';
COMMENT ON COLUMN llm_configs.default_extra_headers IS 'Default extra headers appended to each provider request';
COMMENT ON COLUMN llm_configs.default_extra_query IS 'Default extra query parameters for each request';
COMMENT ON COLUMN llm_configs.enable_streaming IS 'Enable streaming output (experimental, default: false)';

-- Create indexes for llm_configs table
CREATE INDEX idx_llm_configs_provider_id ON llm_configs(provider_id);

-- LLM test logs table - LLM configuration testing logs
CREATE TABLE IF NOT EXISTS llm_test_logs (
    id BIGINT PRIMARY KEY,
    config_id INTEGER NOT NULL,
    config_name VARCHAR(100) NOT NULL,
    provider_name VARCHAR(50) NOT NULL,
    model_name VARCHAR(100),
    test_message TEXT NOT NULL,
    override_temperature DECIMAL(3,2),
    override_max_tokens INTEGER,
    thinking_mode VARCHAR(20) NOT NULL,
    enable_json_schema INTEGER NOT NULL,
    request JSONB NOT NULL,
    response JSONB,
    status INTEGER NOT NULL,
    error_message TEXT,
    response_time_ms INTEGER,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    reasoning_content TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

ALTER TABLE llm_test_logs
    ADD CONSTRAINT check_llm_test_logs_thinking_mode CHECK (thinking_mode <> '');

COMMENT ON COLUMN llm_test_logs.thinking_mode IS 'Thinking mode: enabled/disabled/auto';

-- Create indexes for llm_test_logs table
-- Note: No additional indexes needed for MVP


-- ============================================================================
-- Database Functions and Triggers
-- ============================================================================

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for all tables with updated_at column
-- Drop existing triggers first to ensure idempotency
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
DROP TRIGGER IF EXISTS update_user_tokens_updated_at ON user_tokens;
DROP TRIGGER IF EXISTS update_user_auths_updated_at ON user_auths;
DROP TRIGGER IF EXISTS update_contacts_updated_at ON contacts;
DROP TRIGGER IF EXISTS update_contact_requests_updated_at ON contact_requests;
DROP TRIGGER IF EXISTS update_square_character_entries_updated_at ON square_character_entries;
DROP TRIGGER IF EXISTS update_profiles_updated_at ON profiles;
DROP TRIGGER IF EXISTS update_message_delivery_failures_updated_at ON message_delivery_failures;
DROP TRIGGER IF EXISTS update_media_files_updated_at ON media_files;
DROP TRIGGER IF EXISTS update_ai_styles_updated_at ON ai_styles;
DROP TRIGGER IF EXISTS update_ai_relationships_updated_at ON ai_relationships;
DROP TRIGGER IF EXISTS update_ai_dimensions_updated_at ON ai_dimensions;
DROP TRIGGER IF EXISTS update_ai_style_dimensions_updated_at ON ai_style_dimensions;
DROP TRIGGER IF EXISTS update_ai_dimension_relationship_mappings_updated_at ON ai_dimension_relationship_mappings;
DROP TRIGGER IF EXISTS update_ai_personalities_updated_at ON ai_personalities;
DROP TRIGGER IF EXISTS update_ai_personality_placeholders_updated_at ON ai_personality_placeholders;
DROP TRIGGER IF EXISTS update_ai_template_types_updated_at ON ai_template_types;
DROP TRIGGER IF EXISTS update_ai_templates_updated_at ON ai_templates;
DROP TRIGGER IF EXISTS update_ai_instances_updated_at ON ai_instances;
DROP TRIGGER IF EXISTS update_ai_instances_updated_at ON ai_instances;
DROP TRIGGER IF EXISTS update_ai_message_buffer_updated_at ON ai_message_buffer;
DROP TRIGGER IF EXISTS update_ai_character_dimensions_updated_at ON ai_character_dimensions;
DROP TRIGGER IF EXISTS update_user_violation_logs_updated_at ON user_violation_logs;
DROP TRIGGER IF EXISTS update_user_risk_stats_updated_at ON user_risk_stats;
DROP TRIGGER IF EXISTS update_system_configs_updated_at ON system_configs;
DROP TRIGGER IF EXISTS update_admin_users_updated_at ON admin_users;
DROP TRIGGER IF EXISTS update_llm_providers_updated_at ON llm_providers;
DROP TRIGGER IF EXISTS update_llm_configs_updated_at ON llm_configs;

-- Create triggers
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_tokens_updated_at BEFORE UPDATE ON user_tokens FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_auths_updated_at BEFORE UPDATE ON user_auths FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_contacts_updated_at BEFORE UPDATE ON contacts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_contact_requests_updated_at BEFORE UPDATE ON contact_requests FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_square_character_entries_updated_at BEFORE UPDATE ON square_character_entries FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE ON profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_message_delivery_failures_updated_at BEFORE UPDATE ON message_delivery_failures FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_media_files_updated_at BEFORE UPDATE ON media_files FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_styles_updated_at BEFORE UPDATE ON ai_styles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_relationships_updated_at BEFORE UPDATE ON ai_relationships FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_dimensions_updated_at BEFORE UPDATE ON ai_dimensions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_style_dimensions_updated_at BEFORE UPDATE ON ai_style_dimensions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_dimension_relationship_mappings_updated_at BEFORE UPDATE ON ai_dimension_relationship_mappings FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_personalities_updated_at BEFORE UPDATE ON ai_personalities FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_personality_placeholders_updated_at BEFORE UPDATE ON ai_personality_placeholders FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_template_types_updated_at BEFORE UPDATE ON ai_template_types FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_templates_updated_at BEFORE UPDATE ON ai_templates FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_instances_updated_at BEFORE UPDATE ON ai_instances FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_instances_updated_at BEFORE UPDATE ON ai_instances FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_message_buffer_updated_at BEFORE UPDATE ON ai_message_buffer FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_character_dimensions_updated_at BEFORE UPDATE ON ai_character_dimensions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_violation_logs_updated_at BEFORE UPDATE ON user_violation_logs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_risk_stats_updated_at BEFORE UPDATE ON user_risk_stats FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_system_configs_updated_at BEFORE UPDATE ON system_configs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_admin_users_updated_at BEFORE UPDATE ON admin_users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_llm_providers_updated_at BEFORE UPDATE ON llm_providers FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_llm_configs_updated_at BEFORE UPDATE ON llm_configs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
-- Note: llm_request_logs doesn't need updated_at trigger as it's append-only

-- ============================================================================
-- Schema Initialization Complete
-- ============================================================================

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Database schema initialization completed successfully!';
    RAISE NOTICE 'All tables, indexes, triggers, and functions have been created.';
    RAISE NOTICE 'Ready to load initial data.';
END $$;
