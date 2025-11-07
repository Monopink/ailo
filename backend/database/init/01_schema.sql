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
    -- Ensure one owner can only have one contact record for each contact
    CONSTRAINT contacts_user_contact_unique UNIQUE (user_id, contact_id, contact_type)
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
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for contact_requests table
CREATE INDEX idx_contact_requests_expires_at ON contact_requests(expires_at);
-- Composite index for worker query (status + to_type + expires_at for AI requests)
CREATE INDEX idx_contact_requests_worker_query ON contact_requests(status, to_type, expires_at) WHERE status IN (1, 8);  -- PENDING=1, PROCESSING=8


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
    msg_id_provider VARCHAR(128),
    msg_id_client VARCHAR(64),
    client_sent_time TIMESTAMP WITH TIME ZONE,
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
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
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
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

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
    typing_speed INTEGER,
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


-- AI character templates table - AI core configuration templates
CREATE TABLE IF NOT EXISTS ai_character_templates (
    id SERIAL PRIMARY KEY,
    style_id INTEGER NOT NULL,
    personality_id INTEGER NOT NULL,
    memory TEXT,
    prompt_variables JSONB,
    display_name VARCHAR(100),
    position_mapping_config JSONB,
    is_reusable INTEGER NOT NULL DEFAULT 1,
    profile_count INTEGER NOT NULL DEFAULT 0,
    profile_id INTEGER,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_character_templates table
-- Note: No additional indexes needed for MVP


-- AI profile templates table - AI profile templates
CREATE TABLE IF NOT EXISTS ai_profile_templates (
    id BIGINT PRIMARY KEY,  -- Changed from SERIAL to BIGINT for Snowflake ID
    qiao_id VARCHAR(32) NOT NULL UNIQUE,
    category VARCHAR(50),
    character_template_id INTEGER NOT NULL,  -- Changed from nullable to NOT NULL (matches model)
    nickname VARCHAR(100),
    gender INTEGER,
    avatar_url VARCHAR(500),
    bio TEXT,
    region VARCHAR(100),
    is_reusable INTEGER NOT NULL DEFAULT 1,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_profile_templates table
-- Note: No additional indexes needed for MVP


-- AI characters table - AI character instances
CREATE TABLE IF NOT EXISTS ai_characters (
    id BIGINT PRIMARY KEY,
    qiao_id VARCHAR(32) NOT NULL UNIQUE,
    user_id BIGINT,
    user_qiao_id VARCHAR(32),
    category VARCHAR(50),
    style_id INTEGER NOT NULL,
    personality_id INTEGER NOT NULL,
    status INTEGER NOT NULL DEFAULT 1,
    memory TEXT,
    prompt_variables JSONB,
    relationship_id INTEGER,
    relationship_counts JSONB,
    request_params JSONB,
    created_by INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_characters table
CREATE INDEX idx_ai_characters_user_qiao_id ON ai_characters(user_qiao_id);
CREATE INDEX idx_ai_characters_style_id ON ai_characters(style_id);
CREATE INDEX idx_ai_characters_personality_id ON ai_characters(personality_id);

-- Add comment for new field
COMMENT ON COLUMN ai_characters.request_params IS 'AI character request parameters configuration (JSON format) - can override default LLM settings';

-- AI contexts table - AI conversation contexts
CREATE TABLE IF NOT EXISTS ai_contexts (
    id BIGINT PRIMARY KEY,
    character_id BIGINT NOT NULL,
    character_qiao_id VARCHAR(32) NOT NULL,
    user_id BIGINT NOT NULL,
    user_qiao_id VARCHAR(32) NOT NULL,
    role INTEGER NOT NULL,
    content TEXT NOT NULL,
    first_msg_id_client VARCHAR(64),
    last_msg_id_client VARCHAR(64),
    token_count INTEGER,
    is_attack INTEGER NOT NULL DEFAULT 0,
    last_msg_time_ms BIGINT,
    buffer_expires_at_ms BIGINT,
    aggregate_state INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_contexts table
CREATE INDEX idx_ai_contexts_character_qiao_id ON ai_contexts(character_qiao_id);
CREATE INDEX idx_ai_contexts_user_qiao_id ON ai_contexts(user_qiao_id);
CREATE INDEX idx_ai_contexts_created_at ON ai_contexts(created_at);
CREATE INDEX idx_ai_contexts_character_id ON ai_contexts(character_id);
CREATE UNIQUE INDEX idx_ai_contexts_unique_locked ON ai_contexts(user_qiao_id, character_qiao_id) WHERE role=2 AND aggregate_state=2;
CREATE INDEX idx_ai_contexts_expire_scan ON ai_contexts(user_qiao_id, character_qiao_id, buffer_expires_at_ms) WHERE role=2 AND aggregate_state=1;


-- AI contexts archive table - Archived AI conversation contexts
CREATE TABLE IF NOT EXISTS ai_contexts_archive (
    id BIGINT PRIMARY KEY,
    character_id BIGINT NOT NULL,
    character_qiao_id VARCHAR(32) NOT NULL,
    user_id BIGINT NOT NULL,
    user_qiao_id VARCHAR(32) NOT NULL,
    role INTEGER NOT NULL,
    content TEXT NOT NULL,
    first_msg_id_client VARCHAR(64),
    last_msg_id_client VARCHAR(64),
    token_count INTEGER,
    is_attack INTEGER NOT NULL DEFAULT 0,
    last_msg_time_ms BIGINT,
    buffer_expires_at_ms BIGINT,
    aggregate_state INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_contexts_archive table
-- Note: No additional indexes needed for MVP


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
    request JSONB NOT NULL,
    response JSONB,
    status INTEGER NOT NULL,
    token_count INTEGER,
    response_time INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for ai_request_logs table
-- Note: No additional indexes needed for MVP


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
    ai_characters INTEGER NOT NULL DEFAULT 0,
    active_ai_characters INTEGER NOT NULL DEFAULT 0,
    ai_requests_count INTEGER NOT NULL DEFAULT 0,
    avg_ai_requests_per_user DECIMAL(10,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stats_ai_weekly (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL UNIQUE,
    ai_characters INTEGER NOT NULL DEFAULT 0,
    active_ai_characters INTEGER NOT NULL DEFAULT 0,
    ai_requests_count INTEGER NOT NULL DEFAULT 0,
    avg_ai_requests_per_user DECIMAL(10,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stats_ai_monthly (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL UNIQUE,
    ai_characters INTEGER NOT NULL DEFAULT 0,
    active_ai_characters INTEGER NOT NULL DEFAULT 0,
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
    max_retries INTEGER,
    enable_streaming INTEGER NOT NULL,
    enable_thinking INTEGER NOT NULL,
    json_schema_mode VARCHAR(20),
    status INTEGER NOT NULL DEFAULT 1,
    priority INTEGER NOT NULL DEFAULT 1,
    extra_params JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON COLUMN llm_configs.json_schema_mode IS 'JSON Schema support status: strict=verified supported, disabled=verified not supported, auto=not verified (default)';

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
    enable_thinking INTEGER NOT NULL,
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
DROP TRIGGER IF EXISTS update_ai_character_templates_updated_at ON ai_character_templates;
DROP TRIGGER IF EXISTS update_ai_profile_templates_updated_at ON ai_profile_templates;
DROP TRIGGER IF EXISTS update_ai_characters_updated_at ON ai_characters;
DROP TRIGGER IF EXISTS update_ai_contexts_updated_at ON ai_contexts;
DROP TRIGGER IF EXISTS update_ai_contexts_archive_updated_at ON ai_contexts_archive;
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
CREATE TRIGGER update_ai_character_templates_updated_at BEFORE UPDATE ON ai_character_templates FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_profile_templates_updated_at BEFORE UPDATE ON ai_profile_templates FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_characters_updated_at BEFORE UPDATE ON ai_characters FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_contexts_updated_at BEFORE UPDATE ON ai_contexts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_contexts_archive_updated_at BEFORE UPDATE ON ai_contexts_archive FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
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
