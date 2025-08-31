-- PostgreSQL Database Tables Creation Script
-- This script creates all database tables for the AI chat application
-- Optimized for PostgreSQL 16 with JSONB and performance enhancements
-- File naming: 02_ ensures this runs after extensions setup

-- Set timezone and encoding
SET timezone = 'UTC';
SET client_encoding = 'UTF8';

-- Success message for table creation start
DO $$
BEGIN
    RAISE NOTICE 'Creating database tables...';
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
    wechat_openid VARCHAR(64) UNIQUE,
    apple_id VARCHAR(128) UNIQUE,
    status INTEGER NOT NULL DEFAULT 1,
    user_type INTEGER NOT NULL DEFAULT 1,
    last_login TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for users table
CREATE INDEX IF NOT EXISTS idx_users_qiao_id ON users(qiao_id);
CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_wechat_openid ON users(wechat_openid);
CREATE INDEX IF NOT EXISTS idx_users_apple_id ON users(apple_id);
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
CREATE INDEX IF NOT EXISTS idx_users_user_type ON users(user_type);
CREATE INDEX IF NOT EXISTS idx_users_last_login ON users(last_login);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

-- User sessions table - Session management with device limits
CREATE TABLE IF NOT EXISTS user_sessions (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    user_qiao_id VARCHAR(32) NOT NULL,
    session_token VARCHAR(128) NOT NULL UNIQUE,
    device_type INTEGER NOT NULL,
    device_id VARCHAR(128),
    platform_info JSONB,
    ip_address INET,
    user_agent TEXT,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    last_activity_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for user_sessions table
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_qiao_id ON user_sessions(user_qiao_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_session_token ON user_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_user_sessions_device_type ON user_sessions(device_type);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_user_sessions_is_active ON user_sessions(is_active);
CREATE INDEX IF NOT EXISTS idx_user_sessions_last_activity_at ON user_sessions(last_activity_at);
-- GIN index for JSONB platform_info
CREATE INDEX IF NOT EXISTS idx_user_sessions_platform_info_gin ON user_sessions USING GIN(platform_info);

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
    session_token VARCHAR(128),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for login_records table
CREATE INDEX IF NOT EXISTS idx_login_records_user_id ON login_records(user_id);
CREATE INDEX IF NOT EXISTS idx_login_records_user_qiao_id ON login_records(user_qiao_id);
CREATE INDEX IF NOT EXISTS idx_login_records_login_time ON login_records(login_time);
CREATE INDEX IF NOT EXISTS idx_login_records_login_type ON login_records(login_type);
CREATE INDEX IF NOT EXISTS idx_login_records_platform ON login_records(platform);
CREATE INDEX IF NOT EXISTS idx_login_records_result ON login_records(result);
CREATE INDEX IF NOT EXISTS idx_login_records_ip_address ON login_records(ip_address);

-- ============================================================================
-- Contact Management Tables
-- ============================================================================

-- Contacts table - User contact relationships
CREATE TABLE IF NOT EXISTS contacts (
    id BIGINT PRIMARY KEY,
    conv_id VARCHAR(32) NOT NULL UNIQUE,
    user_id BIGINT,
    user_qiao_id VARCHAR(32),
    contact_type INTEGER NOT NULL,
    contact_id BIGINT NOT NULL,
    contact_qiao_id VARCHAR(32) NOT NULL,
    alias VARCHAR(100),
    avatar_alias_url VARCHAR(500),
    tags JSONB,
    remark TEXT,
    is_pinned INTEGER NOT NULL DEFAULT 0,
    is_muted INTEGER NOT NULL DEFAULT 0,
    is_blocked INTEGER NOT NULL DEFAULT 0,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for contacts table
CREATE INDEX IF NOT EXISTS idx_contacts_conv_id ON contacts(conv_id);
CREATE INDEX IF NOT EXISTS idx_contacts_user_id ON contacts(user_id);
CREATE INDEX IF NOT EXISTS idx_contacts_user_qiao_id ON contacts(user_qiao_id);
CREATE INDEX IF NOT EXISTS idx_contacts_contact_type ON contacts(contact_type);
CREATE INDEX IF NOT EXISTS idx_contacts_contact_id ON contacts(contact_id);
CREATE INDEX IF NOT EXISTS idx_contacts_contact_qiao_id ON contacts(contact_qiao_id);
CREATE INDEX IF NOT EXISTS idx_contacts_is_pinned ON contacts(is_pinned);
CREATE INDEX IF NOT EXISTS idx_contacts_is_deleted ON contacts(is_deleted);
-- GIN index for JSONB tags
CREATE INDEX IF NOT EXISTS idx_contacts_tags_gin ON contacts USING GIN(tags);

-- Contact requests table - Contact application management
CREATE TABLE IF NOT EXISTS contact_requests (
    id BIGINT PRIMARY KEY,
    from_qiao_id VARCHAR(32) NOT NULL,
    from_type INTEGER NOT NULL,
    from_id BIGINT NOT NULL,
    to_qiao_id VARCHAR(32) NOT NULL,
    to_type INTEGER NOT NULL,
    to_id BIGINT NOT NULL,
    message TEXT,
    source INTEGER NOT NULL,
    status INTEGER NOT NULL DEFAULT 1,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for contact_requests table
CREATE INDEX IF NOT EXISTS idx_contact_requests_from_qiao_id ON contact_requests(from_qiao_id);
CREATE INDEX IF NOT EXISTS idx_contact_requests_to_qiao_id ON contact_requests(to_qiao_id);
CREATE INDEX IF NOT EXISTS idx_contact_requests_status ON contact_requests(status);
CREATE INDEX IF NOT EXISTS idx_contact_requests_expires_at ON contact_requests(expires_at);

-- ============================================================================
-- Profile Management Tables
-- ============================================================================

-- Profiles table - Unified profile information
CREATE TABLE IF NOT EXISTS profiles (
    id BIGINT PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    owner_qiao_id VARCHAR(32) NOT NULL,
    owner_type INTEGER NOT NULL,
    nickname VARCHAR(100),
    gender INTEGER,
    avatar_file_id VARCHAR(32),
    avatar_url VARCHAR(500),
    avatar_prompt TEXT,
    bio TEXT,
    region VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for profiles table
CREATE INDEX IF NOT EXISTS idx_profiles_owner_id ON profiles(owner_id);
CREATE INDEX IF NOT EXISTS idx_profiles_owner_qiao_id ON profiles(owner_qiao_id);
CREATE INDEX IF NOT EXISTS idx_profiles_owner_type ON profiles(owner_type);
CREATE INDEX IF NOT EXISTS idx_profiles_nickname ON profiles(nickname);
CREATE INDEX IF NOT EXISTS idx_profiles_gender ON profiles(gender);

-- User profile logs table - Profile change tracking
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
CREATE INDEX IF NOT EXISTS idx_user_profile_logs_owner_id ON user_profile_logs(owner_id);
CREATE INDEX IF NOT EXISTS idx_user_profile_logs_owner_qiao_id ON user_profile_logs(owner_qiao_id);
CREATE INDEX IF NOT EXISTS idx_user_profile_logs_field_name ON user_profile_logs(field_name);
CREATE INDEX IF NOT EXISTS idx_user_profile_logs_created_at ON user_profile_logs(created_at);

-- ============================================================================
-- Message System Tables
-- ============================================================================

-- Message history table - Complete message records
CREATE TABLE IF NOT EXISTS message_history (
    id BIGINT PRIMARY KEY,
    msg_id_server VARCHAR(64) NOT NULL UNIQUE,
    msg_id_provider VARCHAR(64),
    msg_id_client VARCHAR(64),
    conversation_id VARCHAR(32) NOT NULL,
    direction INTEGER NOT NULL,
    platform INTEGER,
    client_sent_time TIMESTAMP WITH TIME ZONE,
    from_type INTEGER NOT NULL,
    from_id BIGINT NOT NULL,
    from_qiao_id VARCHAR(32) NOT NULL,
    to_type INTEGER NOT NULL,
    to_id BIGINT NOT NULL,
    to_qiao_id VARCHAR(32) NOT NULL,
    message_type INTEGER NOT NULL,
    content TEXT,
    service_provider INTEGER NOT NULL,
    status INTEGER NOT NULL,
    message_metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for message_history table
CREATE INDEX IF NOT EXISTS idx_message_history_msg_id_server ON message_history(msg_id_server);
CREATE INDEX IF NOT EXISTS idx_message_history_msg_id_client ON message_history(msg_id_client);
CREATE INDEX IF NOT EXISTS idx_message_history_conversation_id ON message_history(conversation_id);
CREATE INDEX IF NOT EXISTS idx_message_history_from_qiao_id ON message_history(from_qiao_id);
CREATE INDEX IF NOT EXISTS idx_message_history_to_qiao_id ON message_history(to_qiao_id);
CREATE INDEX IF NOT EXISTS idx_message_history_message_type ON message_history(message_type);
CREATE INDEX IF NOT EXISTS idx_message_history_status ON message_history(status);
CREATE INDEX IF NOT EXISTS idx_message_history_created_at ON message_history(created_at);
-- GIN index for JSONB message_metadata
CREATE INDEX IF NOT EXISTS idx_message_history_metadata_gin ON message_history USING GIN(message_metadata);

-- Message delivery failures table - Failed message tracking
CREATE TABLE IF NOT EXISTS message_delivery_failures (
    id BIGINT PRIMARY KEY,
    msg_id_server VARCHAR(64) NOT NULL,
    from_type INTEGER NOT NULL,
    from_id BIGINT NOT NULL,
    from_qiao_id VARCHAR(32) NOT NULL,
    to_type INTEGER NOT NULL,
    to_id BIGINT NOT NULL,
    to_qiao_id VARCHAR(32) NOT NULL,
    message_type INTEGER NOT NULL,
    content TEXT,
    service_provider INTEGER NOT NULL,
    fail_reason_code VARCHAR(50),
    fail_detail TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retry_count INTEGER NOT NULL DEFAULT 3,
    next_retry_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for message_delivery_failures table
CREATE INDEX IF NOT EXISTS idx_message_delivery_failures_msg_id_server ON message_delivery_failures(msg_id_server);
CREATE INDEX IF NOT EXISTS idx_message_delivery_failures_from_qiao_id ON message_delivery_failures(from_qiao_id);
CREATE INDEX IF NOT EXISTS idx_message_delivery_failures_to_qiao_id ON message_delivery_failures(to_qiao_id);
CREATE INDEX IF NOT EXISTS idx_message_delivery_failures_retry_count ON message_delivery_failures(retry_count);
CREATE INDEX IF NOT EXISTS idx_message_delivery_failures_next_retry_at ON message_delivery_failures(next_retry_at);

-- Media files table - File management
CREATE TABLE IF NOT EXISTS media_files (
    id BIGINT PRIMARY KEY,
    file_id VARCHAR(32) NOT NULL UNIQUE,
    file_type INTEGER NOT NULL,
    original_name VARCHAR(255),
    file_path VARCHAR(500),
    file_url VARCHAR(500),
    file_size BIGINT,
    mime_type VARCHAR(100),
    upload_by_type INTEGER NOT NULL,
    upload_by_id BIGINT NOT NULL,
    upload_by_qiao_id VARCHAR(32) NOT NULL,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for media_files table
CREATE INDEX IF NOT EXISTS idx_media_files_file_id ON media_files(file_id);
CREATE INDEX IF NOT EXISTS idx_media_files_file_type ON media_files(file_type);
CREATE INDEX IF NOT EXISTS idx_media_files_upload_by_type ON media_files(upload_by_type);
CREATE INDEX IF NOT EXISTS idx_media_files_upload_by_id ON media_files(upload_by_id);
CREATE INDEX IF NOT EXISTS idx_media_files_upload_by_qiao_id ON media_files(upload_by_qiao_id);
CREATE INDEX IF NOT EXISTS idx_media_files_status ON media_files(status);

-- Emoticons table - Emoticon management
CREATE TABLE IF NOT EXISTS emoticons (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    category INTEGER NOT NULL,
    file_id VARCHAR(32),
    url VARCHAR(500),
    description VARCHAR(255),
    created_by_type INTEGER NOT NULL,
    created_by_id BIGINT NOT NULL,
    status INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for emoticons table
CREATE INDEX IF NOT EXISTS idx_emoticons_code ON emoticons(code);
CREATE INDEX IF NOT EXISTS idx_emoticons_category ON emoticons(category);
CREATE INDEX IF NOT EXISTS idx_emoticons_status ON emoticons(status);
CREATE INDEX IF NOT EXISTS idx_emoticons_sort_order ON emoticons(sort_order);

-- ============================================================================
-- AI System Tables
-- ============================================================================

-- AI styles table - AI style definitions
CREATE TABLE IF NOT EXISTS ai_styles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    score_count INTEGER NOT NULL,
    score_name JSONB,
    usage_count INTEGER NOT NULL DEFAULT 0,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_styles table
CREATE INDEX IF NOT EXISTS idx_ai_styles_name ON ai_styles(name);
CREATE INDEX IF NOT EXISTS idx_ai_styles_status ON ai_styles(status);
CREATE INDEX IF NOT EXISTS idx_ai_styles_usage_count ON ai_styles(usage_count);

-- AI relationship table - Relationship type definitions
CREATE TABLE IF NOT EXISTS ai_relationship (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    prompt_fragment TEXT,
    usage_count INTEGER NOT NULL DEFAULT 0,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_relationship table
CREATE INDEX IF NOT EXISTS idx_ai_relationship_name ON ai_relationship(name);
CREATE INDEX IF NOT EXISTS idx_ai_relationship_status ON ai_relationship(status);
CREATE INDEX IF NOT EXISTS idx_ai_relationship_usage_count ON ai_relationship(usage_count);

-- AI relationship index table - Score to relationship mapping
CREATE TABLE IF NOT EXISTS ai_relationship_indexes (
    id SERIAL PRIMARY KEY,
    style_id INTEGER NOT NULL,
    score_order INTEGER NOT NULL,
    score_name VARCHAR(100) NOT NULL,
    start_position INTEGER NOT NULL,
    end_position INTEGER NOT NULL,
    relationship_id INTEGER NOT NULL,
    priority INTEGER NOT NULL,
    limit_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_relationship_indexes table
CREATE INDEX IF NOT EXISTS idx_ai_relationship_indexes_style_id ON ai_relationship_indexes(style_id);
CREATE INDEX IF NOT EXISTS idx_ai_relationship_indexes_relationship_id ON ai_relationship_indexes(relationship_id);
CREATE INDEX IF NOT EXISTS idx_ai_relationship_indexes_score_order ON ai_relationship_indexes(score_order);

-- AI personalities table - Personality templates
CREATE TABLE IF NOT EXISTS ai_personalities (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    prompt TEXT NOT NULL,
    json_schema JSONB,
    usage_count INTEGER NOT NULL DEFAULT 0,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_personalities table
CREATE INDEX IF NOT EXISTS idx_ai_personalities_name ON ai_personalities(name);
CREATE INDEX IF NOT EXISTS idx_ai_personalities_status ON ai_personalities(status);
CREATE INDEX IF NOT EXISTS idx_ai_personalities_usage_count ON ai_personalities(usage_count);
-- GIN index for JSONB json_schema
CREATE INDEX IF NOT EXISTS idx_ai_personalities_json_schema_gin ON ai_personalities USING GIN(json_schema);

-- AI personality placeholders table - Placeholder definitions
CREATE TABLE IF NOT EXISTS ai_personality_placeholders (
    id SERIAL PRIMARY KEY,
    personality_id INTEGER,
    placeholder_key VARCHAR(100) NOT NULL,
    placeholder_type VARCHAR(50) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    description VARCHAR(500),
    is_required INTEGER NOT NULL DEFAULT 0,
    validation_rules JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_personality_placeholders table
CREATE INDEX IF NOT EXISTS idx_ai_personality_placeholders_personality_id ON ai_personality_placeholders(personality_id);
CREATE INDEX IF NOT EXISTS idx_ai_personality_placeholders_placeholder_key ON ai_personality_placeholders(placeholder_key);
CREATE INDEX IF NOT EXISTS idx_ai_personality_placeholders_placeholder_type ON ai_personality_placeholders(placeholder_type);
CREATE INDEX IF NOT EXISTS idx_ai_personality_placeholders_is_required ON ai_personality_placeholders(is_required);
-- GIN index for JSONB validation_rules
CREATE INDEX IF NOT EXISTS idx_ai_personality_placeholders_validation_rules_gin ON ai_personality_placeholders USING GIN(validation_rules);

-- AI info templates table - AI core configuration templates
CREATE TABLE IF NOT EXISTS ai_info_templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    prompt TEXT NOT NULL,
    json_schema JSONB,
    usage_count INTEGER NOT NULL DEFAULT 0,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_info_templates table
CREATE INDEX IF NOT EXISTS idx_ai_info_templates_name ON ai_info_templates(name);
CREATE INDEX IF NOT EXISTS idx_ai_info_templates_status ON ai_info_templates(status);
CREATE INDEX IF NOT EXISTS idx_ai_info_templates_usage_count ON ai_info_templates(usage_count);
-- GIN index for JSONB json_schema
CREATE INDEX IF NOT EXISTS idx_ai_info_templates_json_schema_gin ON ai_info_templates USING GIN(json_schema);

-- AI profile templates table - AI profile templates
CREATE TABLE IF NOT EXISTS ai_profile_templates (
    id SERIAL PRIMARY KEY,
    qiao_id VARCHAR(32) NOT NULL UNIQUE,
    category VARCHAR(50),
    info_id INTEGER,
    nickname VARCHAR(100),
    gender INTEGER,
    avatar_url VARCHAR(500),
    bio TEXT,
    region VARCHAR(100),
    age_template VARCHAR(100),
    location_template VARCHAR(200),
    json_schema JSONB,
    usage_count INTEGER NOT NULL DEFAULT 0,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_profile_templates table
CREATE INDEX IF NOT EXISTS idx_ai_profile_templates_qiao_id ON ai_profile_templates(qiao_id);
CREATE INDEX IF NOT EXISTS idx_ai_profile_templates_category ON ai_profile_templates(category);
CREATE INDEX IF NOT EXISTS idx_ai_profile_templates_info_id ON ai_profile_templates(info_id);
CREATE INDEX IF NOT EXISTS idx_ai_profile_templates_nickname ON ai_profile_templates(nickname);
CREATE INDEX IF NOT EXISTS idx_ai_profile_templates_status ON ai_profile_templates(status);
-- GIN index for JSONB json_schema
CREATE INDEX IF NOT EXISTS idx_ai_profile_templates_json_schema_gin ON ai_profile_templates USING GIN(json_schema);

-- AI characters table - AI character instances
CREATE TABLE IF NOT EXISTS ai_characters (
    id BIGINT PRIMARY KEY,
    qiao_id VARCHAR(32) NOT NULL UNIQUE,
    user_id BIGINT,
    user_qiao_id VARCHAR(32),
    category VARCHAR(50),
    style_id INTEGER NOT NULL,
    personality_id INTEGER NOT NULL,
    memory TEXT,
    placeholder_overrides JSONB,
    score_offset_algorithm VARCHAR(100),
    score_offset_coefficient REAL,
    created_by INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_characters table
CREATE INDEX IF NOT EXISTS idx_ai_characters_user_id ON ai_characters(user_id);
CREATE INDEX IF NOT EXISTS idx_ai_characters_user_qiao_id ON ai_characters(user_qiao_id);
CREATE INDEX IF NOT EXISTS idx_ai_characters_category ON ai_characters(category);
CREATE INDEX IF NOT EXISTS idx_ai_characters_style_id ON ai_characters(style_id);
CREATE INDEX IF NOT EXISTS idx_ai_characters_personality_id ON ai_characters(personality_id);
CREATE INDEX IF NOT EXISTS idx_ai_characters_created_by ON ai_characters(created_by);
-- GIN index for JSONB placeholder_overrides
CREATE INDEX IF NOT EXISTS idx_ai_characters_placeholder_overrides_gin ON ai_characters USING GIN(placeholder_overrides);

-- AI contexts table - AI conversation contexts
CREATE TABLE IF NOT EXISTS ai_contexts (
    id BIGINT PRIMARY KEY,
    character_id BIGINT NOT NULL,
    character_qiao_id VARCHAR(32) NOT NULL,
    user_id BIGINT NOT NULL,
    user_qiao_id VARCHAR(32) NOT NULL,
    role INTEGER NOT NULL,
    content TEXT NOT NULL,
    source_type INTEGER NOT NULL,
    source_message_ids JSONB,
    metadata JSONB,
    position INTEGER NOT NULL,
    token_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_contexts table
CREATE INDEX IF NOT EXISTS idx_ai_contexts_character_id ON ai_contexts(character_id);
CREATE INDEX IF NOT EXISTS idx_ai_contexts_character_qiao_id ON ai_contexts(character_qiao_id);
CREATE INDEX IF NOT EXISTS idx_ai_contexts_user_id ON ai_contexts(user_id);
CREATE INDEX IF NOT EXISTS idx_ai_contexts_user_qiao_id ON ai_contexts(user_qiao_id);
CREATE INDEX IF NOT EXISTS idx_ai_contexts_role ON ai_contexts(role);
CREATE INDEX IF NOT EXISTS idx_ai_contexts_position ON ai_contexts(position);
-- GIN indexes for JSONB fields
CREATE INDEX IF NOT EXISTS idx_ai_contexts_source_message_ids_gin ON ai_contexts USING GIN(source_message_ids);
CREATE INDEX IF NOT EXISTS idx_ai_contexts_metadata_gin ON ai_contexts USING GIN(metadata);

-- AI relationship scores table - AI relationship scoring
CREATE TABLE IF NOT EXISTS ai_relationship_scores (
    id BIGINT PRIMARY KEY,
    character_id BIGINT NOT NULL,
    score_order INTEGER NOT NULL,
    score INTEGER NOT NULL,
    score_start INTEGER NOT NULL,
    score_end INTEGER NOT NULL,
    score_offset_algorithm VARCHAR(100),
    score_offset_coefficient REAL,
    score_position INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_relationship_scores table
CREATE INDEX IF NOT EXISTS idx_ai_relationship_scores_character_id ON ai_relationship_scores(character_id);
CREATE INDEX IF NOT EXISTS idx_ai_relationship_scores_score_order ON ai_relationship_scores(score_order);
CREATE INDEX IF NOT EXISTS idx_ai_relationship_scores_score ON ai_relationship_scores(score);

-- AI relationship counts table - Relationship usage statistics
CREATE TABLE IF NOT EXISTS ai_relationship_counts (
    id BIGINT PRIMARY KEY,
    character_id BIGINT NOT NULL,
    relationship_id INTEGER NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_relationship_counts table
CREATE INDEX IF NOT EXISTS idx_ai_relationship_counts_character_id ON ai_relationship_counts(character_id);
CREATE INDEX IF NOT EXISTS idx_ai_relationship_counts_relationship_id ON ai_relationship_counts(relationship_id);

-- AI request logs table - AI service request logging
CREATE TABLE IF NOT EXISTS ai_request_logs (
    id BIGINT PRIMARY KEY,
    character_id BIGINT,
    user_id BIGINT,
    style_id INTEGER,
    personality_id INTEGER,
    request JSONB,
    response JSONB,
    status INTEGER NOT NULL,
    token_count INTEGER,
    response_time INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_request_logs table
CREATE INDEX IF NOT EXISTS idx_ai_request_logs_character_id ON ai_request_logs(character_id);
CREATE INDEX IF NOT EXISTS idx_ai_request_logs_user_id ON ai_request_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_ai_request_logs_status ON ai_request_logs(status);
CREATE INDEX IF NOT EXISTS idx_ai_request_logs_created_at ON ai_request_logs(created_at);
-- GIN indexes for JSONB fields
CREATE INDEX IF NOT EXISTS idx_ai_request_logs_request_gin ON ai_request_logs USING GIN(request);
CREATE INDEX IF NOT EXISTS idx_ai_request_logs_response_gin ON ai_request_logs USING GIN(response);

-- ============================================================================
-- Security Monitoring Tables
-- ============================================================================

-- User security logs table - Security violation tracking
CREATE TABLE IF NOT EXISTS user_security_logs (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    user_qiao_id VARCHAR(32) NOT NULL,
    character_id BIGINT,
    character_qiao_id VARCHAR(32),
    violation_type INTEGER NOT NULL,
    severity_level INTEGER NOT NULL,
    original_message TEXT NOT NULL,
    ai_detection_result JSONB,
    confidence_score INTEGER,
    auto_action_taken INTEGER NOT NULL DEFAULT 1,
    manual_review_status INTEGER NOT NULL DEFAULT 1,
    reviewer_id INTEGER,
    review_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for user_security_logs table
CREATE INDEX IF NOT EXISTS idx_user_security_logs_user_id ON user_security_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_user_security_logs_user_qiao_id ON user_security_logs(user_qiao_id);
CREATE INDEX IF NOT EXISTS idx_user_security_logs_character_id ON user_security_logs(character_id);
CREATE INDEX IF NOT EXISTS idx_user_security_logs_violation_type ON user_security_logs(violation_type);
CREATE INDEX IF NOT EXISTS idx_user_security_logs_severity_level ON user_security_logs(severity_level);
CREATE INDEX IF NOT EXISTS idx_user_security_logs_auto_action_taken ON user_security_logs(auto_action_taken);
CREATE INDEX IF NOT EXISTS idx_user_security_logs_manual_review_status ON user_security_logs(manual_review_status);
CREATE INDEX IF NOT EXISTS idx_user_security_logs_created_at ON user_security_logs(created_at);
-- GIN index for JSONB ai_detection_result
CREATE INDEX IF NOT EXISTS idx_user_security_logs_ai_detection_result_gin ON user_security_logs USING GIN(ai_detection_result);

-- User security stats table - Security statistics summary
CREATE TABLE IF NOT EXISTS user_security_stats (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE,
    user_qiao_id VARCHAR(32) NOT NULL UNIQUE,
    total_violations INTEGER NOT NULL DEFAULT 0,
    violation_by_type JSONB,
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

-- Create indexes for user_security_stats table
CREATE INDEX IF NOT EXISTS idx_user_security_stats_user_id ON user_security_stats(user_id);
CREATE INDEX IF NOT EXISTS idx_user_security_stats_user_qiao_id ON user_security_stats(user_qiao_id);
CREATE INDEX IF NOT EXISTS idx_user_security_stats_current_risk_level ON user_security_stats(current_risk_level);
CREATE INDEX IF NOT EXISTS idx_user_security_stats_total_violations ON user_security_stats(total_violations);
CREATE INDEX IF NOT EXISTS idx_user_security_stats_last_violation_at ON user_security_stats(last_violation_at);
-- GIN index for JSONB violation_by_type
CREATE INDEX IF NOT EXISTS idx_user_security_stats_violation_by_type_gin ON user_security_stats USING GIN(violation_by_type);

-- ============================================================================
-- System Configuration Tables
-- ============================================================================

-- System config table - System configuration parameters
CREATE TABLE IF NOT EXISTS system_config (
    id SERIAL PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value TEXT,
    config_type INTEGER NOT NULL,
    description TEXT,
    is_public INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_by INTEGER
);

-- Create indexes for system_config table
CREATE INDEX IF NOT EXISTS idx_system_config_config_key ON system_config(config_key);
CREATE INDEX IF NOT EXISTS idx_system_config_config_type ON system_config(config_type);
CREATE INDEX IF NOT EXISTS idx_system_config_is_public ON system_config(is_public);

-- ============================================================================
-- Statistics Tables
-- ============================================================================

-- User statistics tables (daily/weekly/monthly)
CREATE TABLE IF NOT EXISTS stats_user_daily (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL,
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
    stat_date DATE NOT NULL,
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
    stat_date DATE NOT NULL,
    total_users INTEGER NOT NULL DEFAULT 0,
    new_users INTEGER NOT NULL DEFAULT 0,
    active_users INTEGER NOT NULL DEFAULT 0,
    subscriptions INTEGER NOT NULL DEFAULT 0,
    new_subscriptions INTEGER NOT NULL DEFAULT 0,
    canceled_subscriptions INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for user statistics tables
CREATE INDEX IF NOT EXISTS idx_stats_user_daily_stat_date ON stats_user_daily(stat_date);
CREATE INDEX IF NOT EXISTS idx_stats_user_weekly_stat_date ON stats_user_weekly(stat_date);
CREATE INDEX IF NOT EXISTS idx_stats_user_monthly_stat_date ON stats_user_monthly(stat_date);

-- Revenue statistics tables (daily/weekly/monthly)
CREATE TABLE IF NOT EXISTS stats_revenue_daily (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL,
    total_revenue DECIMAL(10,2) NOT NULL DEFAULT 0,
    orders_count INTEGER NOT NULL DEFAULT 0,
    avg_order_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    refund_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stats_revenue_weekly (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL,
    total_revenue DECIMAL(10,2) NOT NULL DEFAULT 0,
    orders_count INTEGER NOT NULL DEFAULT 0,
    avg_order_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    refund_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stats_revenue_monthly (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL,
    total_revenue DECIMAL(10,2) NOT NULL DEFAULT 0,
    orders_count INTEGER NOT NULL DEFAULT 0,
    avg_order_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    refund_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Message statistics tables (daily/weekly/monthly)
CREATE TABLE IF NOT EXISTS stats_message_daily (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL,
    total_messages INTEGER NOT NULL DEFAULT 0,
    avg_messages_per_user DECIMAL(10,2) NOT NULL DEFAULT 0,
    active_conversations INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stats_message_weekly (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL,
    total_messages INTEGER NOT NULL DEFAULT 0,
    avg_messages_per_user DECIMAL(10,2) NOT NULL DEFAULT 0,
    active_conversations INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stats_message_monthly (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL,
    total_messages INTEGER NOT NULL DEFAULT 0,
    avg_messages_per_user DECIMAL(10,2) NOT NULL DEFAULT 0,
    active_conversations INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- AI statistics tables (daily/weekly/monthly)
CREATE TABLE IF NOT EXISTS stats_ai_daily (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL,
    ai_characters INTEGER NOT NULL DEFAULT 0,
    active_ai_characters INTEGER NOT NULL DEFAULT 0,
    ai_requests_count INTEGER NOT NULL DEFAULT 0,
    avg_ai_requests_per_user DECIMAL(10,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stats_ai_weekly (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL,
    ai_characters INTEGER NOT NULL DEFAULT 0,
    active_ai_characters INTEGER NOT NULL DEFAULT 0,
    ai_requests_count INTEGER NOT NULL DEFAULT 0,
    avg_ai_requests_per_user DECIMAL(10,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stats_ai_monthly (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL,
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
CREATE INDEX IF NOT EXISTS idx_admin_users_username ON admin_users(username);
CREATE INDEX IF NOT EXISTS idx_admin_users_role ON admin_users(role);
CREATE INDEX IF NOT EXISTS idx_admin_users_status ON admin_users(status);

-- Admin operation logs table - Admin operation tracking
CREATE TABLE IF NOT EXISTS admin_operation_logs (
    id SERIAL PRIMARY KEY,
    admin_user_id INTEGER NOT NULL,
    operation_type INTEGER NOT NULL,
    resource_type INTEGER NOT NULL,
    resource_id VARCHAR(100),
    resource_name VARCHAR(255),
    operation_desc TEXT,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for admin_operation_logs table
CREATE INDEX IF NOT EXISTS idx_admin_operation_logs_admin_user_id ON admin_operation_logs(admin_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_operation_logs_operation_type ON admin_operation_logs(operation_type);
CREATE INDEX IF NOT EXISTS idx_admin_operation_logs_resource_type ON admin_operation_logs(resource_type);
CREATE INDEX IF NOT EXISTS idx_admin_operation_logs_created_at ON admin_operation_logs(created_at);

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
CREATE INDEX IF NOT EXISTS idx_admin_login_logs_admin_user_id ON admin_login_logs(admin_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_login_logs_username ON admin_login_logs(username);
CREATE INDEX IF NOT EXISTS idx_admin_login_logs_result ON admin_login_logs(result);
CREATE INDEX IF NOT EXISTS idx_admin_login_logs_created_at ON admin_login_logs(created_at);

-- ============================================================================
-- Triggers for automatic updated_at timestamps
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for tables with updated_at columns
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_sessions_updated_at BEFORE UPDATE ON user_sessions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_contacts_updated_at BEFORE UPDATE ON contacts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_contact_requests_updated_at BEFORE UPDATE ON contact_requests FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE ON profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_media_files_updated_at BEFORE UPDATE ON media_files FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_emoticons_updated_at BEFORE UPDATE ON emoticons FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_styles_updated_at BEFORE UPDATE ON ai_styles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_relationship_updated_at BEFORE UPDATE ON ai_relationship FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_relationship_indexes_updated_at BEFORE UPDATE ON ai_relationship_indexes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_personalities_updated_at BEFORE UPDATE ON ai_personalities FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_personality_placeholders_updated_at BEFORE UPDATE ON ai_personality_placeholders FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_info_templates_updated_at BEFORE UPDATE ON ai_info_templates FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_profile_templates_updated_at BEFORE UPDATE ON ai_profile_templates FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_characters_updated_at BEFORE UPDATE ON ai_characters FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_contexts_updated_at BEFORE UPDATE ON ai_contexts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_relationship_scores_updated_at BEFORE UPDATE ON ai_relationship_scores FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_relationship_counts_updated_at BEFORE UPDATE ON ai_relationship_counts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_message_delivery_failures_updated_at BEFORE UPDATE ON message_delivery_failures FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_security_logs_updated_at BEFORE UPDATE ON user_security_logs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_security_stats_updated_at BEFORE UPDATE ON user_security_stats FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_system_config_updated_at BEFORE UPDATE ON system_config FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_admin_users_updated_at BEFORE UPDATE ON admin_users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Initial Data
-- ============================================================================

-- Insert default admin users (password: admin123)
INSERT INTO admin_users (username, password_hash, role, status) VALUES
('admin', '$2b$12$i4kzuJnXuIQdxS3GgFXOh.JhvEjMntTakeqw4QKXah2zCpXpbwlJi', 1, 1),
('manager', '$2b$12$i4kzuJnXuIQdxS3GgFXOh.JhvEjMntTakeqw4QKXah2zCpXpbwlJi', 2, 1),
('viewer', '$2b$12$i4kzuJnXuIQdxS3GgFXOh.JhvEjMntTakeqw4QKXah2zCpXpbwlJi', 3, 1)
ON CONFLICT (username) DO NOTHING;

-- Insert basic system configuration
INSERT INTO system_config (config_key, config_value, config_type, description, is_public) VALUES
('app_name', 'AI Chat Application', 1, 'Application name', 1),
('app_version', '1.0.0', 1, 'Application version', 1),
('max_message_length', '1000', 2, 'Maximum message length', 1),
('max_contacts_per_user', '100', 2, 'Maximum contacts per user', 1),
('session_timeout_minutes', '30', 2, 'Session timeout in minutes', 0),
('enable_registration', 'true', 3, 'Enable user registration', 1),
('enable_sms_verification', 'true', 3, 'Enable SMS verification', 1),
-- LeanCloud configuration
('leancloud_app_id', '', 1, 'LeanCloud application ID', 0),
('leancloud_app_key', '', 1, 'LeanCloud application key', 0),
('leancloud_server_url', '', 1, 'LeanCloud server URL (optional)', 0),
('leancloud_base_url', 'https://api.leancloud.cn', 1, 'LeanCloud API base URL', 0),
('leancloud_webhook_enabled', 'true', 3, 'Enable LeanCloud webhook processing', 0),
('leancloud_message_timeout_seconds', '30', 2, 'LeanCloud message timeout in seconds', 0),
('leancloud_retry_max_count', '3', 2, 'Maximum retry count for LeanCloud operations', 0),
('leancloud_conversation_ttl_hours', '24', 2, 'LeanCloud conversation TTL in hours', 0),
-- AI JSON Schema validation configuration
('ai_json_schema_max_retries', '3', 2, 'JSON Schema validation failure max retry count', 0),
('ai_json_schema_retry_delay', '2', 2, 'JSON Schema validation retry delay in seconds', 0),
('ai_json_schema_validation_enabled', 'true', 3, 'Enable JSON Schema validation', 0)
ON CONFLICT (config_key) DO NOTHING;

-- Insert basic AI styles
INSERT INTO ai_styles (name, score_count, score_name, usage_count, status) VALUES
('Default Style', 2, '["friendship", "romance"]', 0, 1),
('Casual Style', 1, '["friendship"]', 0, 1),
('Professional Style', 1, '["professional"]', 0, 1)
ON CONFLICT DO NOTHING;

-- Insert basic AI relationships
INSERT INTO ai_relationship (name, prompt_fragment, usage_count, status) VALUES
('Stranger', 'You are meeting this person for the first time.', 0, 1),
('Acquaintance', 'You know this person casually.', 0, 1),
('Friend', 'You are good friends with this person.', 0, 1),
('Close Friend', 'You are very close friends with this person.', 0, 1),
('Best Friend', 'This person is your best friend.', 0, 1)
ON CONFLICT DO NOTHING;

-- Insert basic AI personality
INSERT INTO ai_personalities (name, prompt, json_schema, usage_count, status) VALUES
('Default Personality', 'You are a helpful and friendly AI assistant.', '{"type": "object", "properties": {"name": {"type": "string"}}}', 0, 1),
('Casual Personality', 'You are a casual and relaxed AI companion.', '{"type": "object", "properties": {"name": {"type": "string"}}}', 0, 1),
('Professional Personality', 'You are a professional and knowledgeable AI assistant.', '{"type": "object", "properties": {"name": {"type": "string"}}}', 0, 1)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- Database Optimization Settings
-- ============================================================================

-- Analyze tables for better query planning
ANALYZE;

-- Create comments on tables for documentation
COMMENT ON DATABASE says_db IS 'AI Chat Application Database - PostgreSQL optimized version';

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'PostgreSQL database initialization completed successfully!';
    RAISE NOTICE 'Database: says_db';
    RAISE NOTICE 'Extensions enabled: uuid-ossp, pg_stat_statements';
    RAISE NOTICE 'Tables created with JSONB optimization and GIN indexes';
    RAISE NOTICE 'Automatic updated_at triggers configured';
    RAISE NOTICE 'Initial data inserted';
END $$;
