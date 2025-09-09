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
CREATE INDEX IF NOT EXISTS idx_login_records_session_token ON login_records(session_token);

-- ============================================================================
-- Contact and Relationship Management Tables
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
CREATE INDEX IF NOT EXISTS idx_contacts_is_muted ON contacts(is_muted);
CREATE INDEX IF NOT EXISTS idx_contacts_is_blocked ON contacts(is_blocked);
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
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for profiles table
CREATE INDEX IF NOT EXISTS idx_profiles_owner_id ON profiles(owner_id);
CREATE INDEX IF NOT EXISTS idx_profiles_owner_qiao_id ON profiles(owner_qiao_id);
CREATE INDEX IF NOT EXISTS idx_profiles_owner_type ON profiles(owner_type);
CREATE INDEX IF NOT EXISTS idx_profiles_nickname ON profiles(nickname);
CREATE INDEX IF NOT EXISTS idx_profiles_gender ON profiles(gender);
CREATE INDEX IF NOT EXISTS idx_profiles_avatar_file_id ON profiles(avatar_file_id);

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
CREATE INDEX IF NOT EXISTS idx_user_profile_logs_owner_id ON user_profile_logs(owner_id);
CREATE INDEX IF NOT EXISTS idx_user_profile_logs_owner_qiao_id ON user_profile_logs(owner_qiao_id);
CREATE INDEX IF NOT EXISTS idx_user_profile_logs_field_name ON user_profile_logs(field_name);
CREATE INDEX IF NOT EXISTS idx_user_profile_logs_created_at ON user_profile_logs(created_at);

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
CREATE INDEX IF NOT EXISTS idx_message_history_direction ON message_history(direction);
CREATE INDEX IF NOT EXISTS idx_message_history_platform ON message_history(platform);
CREATE INDEX IF NOT EXISTS idx_message_history_conversation_id ON message_history(conversation_id);
CREATE INDEX IF NOT EXISTS idx_message_history_msg_id_server ON message_history(msg_id_server);
CREATE INDEX IF NOT EXISTS idx_message_history_from_type ON message_history(from_type);
CREATE INDEX IF NOT EXISTS idx_message_history_from_id ON message_history(from_id);
CREATE INDEX IF NOT EXISTS idx_message_history_from_qiao_id ON message_history(from_qiao_id);
CREATE INDEX IF NOT EXISTS idx_message_history_to_type ON message_history(to_type);
CREATE INDEX IF NOT EXISTS idx_message_history_to_id ON message_history(to_id);
CREATE INDEX IF NOT EXISTS idx_message_history_to_qiao_id ON message_history(to_qiao_id);
CREATE INDEX IF NOT EXISTS idx_message_history_service_provider ON message_history(service_provider);
CREATE INDEX IF NOT EXISTS idx_message_history_message_type ON message_history(message_type);
CREATE INDEX IF NOT EXISTS idx_message_history_status ON message_history(status);
CREATE INDEX IF NOT EXISTS idx_message_history_created_at ON message_history(created_at);
-- GIN index for JSONB message_metadata
CREATE INDEX IF NOT EXISTS idx_message_history_message_metadata_gin ON message_history USING GIN(message_metadata);

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
CREATE INDEX IF NOT EXISTS idx_message_delivery_failures_msg_id_server ON message_delivery_failures(msg_id_server);
CREATE INDEX IF NOT EXISTS idx_message_delivery_failures_from_id ON message_delivery_failures(from_id);
CREATE INDEX IF NOT EXISTS idx_message_delivery_failures_to_id ON message_delivery_failures(to_id);
CREATE INDEX IF NOT EXISTS idx_message_delivery_failures_retry_count ON message_delivery_failures(retry_count);
CREATE INDEX IF NOT EXISTS idx_message_delivery_failures_next_retry_at ON message_delivery_failures(next_retry_at);

-- Media files table - Unified media file management
CREATE TABLE IF NOT EXISTS media_files (
    id BIGINT PRIMARY KEY,
    file_id VARCHAR(32) NOT NULL UNIQUE,
    file_type INTEGER NOT NULL,
    original_name VARCHAR(255),
    file_path VARCHAR(500) NOT NULL,
    file_url VARCHAR(500) NOT NULL,
    file_size BIGINT NOT NULL,
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
CREATE INDEX IF NOT EXISTS idx_media_files_created_at ON media_files(created_at);

-- Emoticons table - Emoticon management
CREATE TABLE IF NOT EXISTS emoticons (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    category INTEGER NOT NULL,
    file_id BIGINT,
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
CREATE INDEX IF NOT EXISTS idx_emoticons_file_id ON emoticons(file_id);
CREATE INDEX IF NOT EXISTS idx_emoticons_status ON emoticons(status);
CREATE INDEX IF NOT EXISTS idx_emoticons_sort_order ON emoticons(sort_order);

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
    initial_relationship_id INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_styles table
CREATE INDEX IF NOT EXISTS idx_ai_styles_name ON ai_styles(name);
CREATE INDEX IF NOT EXISTS idx_ai_styles_status ON ai_styles(status);
CREATE INDEX IF NOT EXISTS idx_ai_styles_usage_count ON ai_styles(usage_count);
CREATE INDEX IF NOT EXISTS idx_ai_styles_initial_relationship_id ON ai_styles(initial_relationship_id);

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
CREATE INDEX IF NOT EXISTS idx_ai_relationships_name ON ai_relationships(name);
CREATE INDEX IF NOT EXISTS idx_ai_relationships_status ON ai_relationships(status);
CREATE INDEX IF NOT EXISTS idx_ai_relationships_usage_count ON ai_relationships(usage_count);

-- AI relationship dimensions table - Score dimension definitions
CREATE TABLE IF NOT EXISTS ai_relationship_dimensions (
    id SERIAL PRIMARY KEY,
    style_id INTEGER NOT NULL,
    name VARCHAR(50) NOT NULL,
    display_name VARCHAR(100),
    initial_position INTEGER NOT NULL,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(style_id, name)
);

-- Create indexes for ai_relationship_dimensions table
CREATE INDEX IF NOT EXISTS idx_ai_relationship_dimensions_style_id ON ai_relationship_dimensions(style_id);
CREATE INDEX IF NOT EXISTS idx_ai_relationship_dimensions_name ON ai_relationship_dimensions(name);
CREATE INDEX IF NOT EXISTS idx_ai_relationship_dimensions_status ON ai_relationship_dimensions(status);

-- AI relationship indexes table - Score to relationship mapping
CREATE TABLE IF NOT EXISTS ai_relationship_indexes (
    id SERIAL PRIMARY KEY,
    style_id INTEGER NOT NULL,
    dimension_id INTEGER NOT NULL,
    dimension_name VARCHAR(50) NOT NULL,
    start_position INTEGER NOT NULL,
    end_position INTEGER NOT NULL,
    relationship_id INTEGER NOT NULL,
    priority INTEGER NOT NULL DEFAULT 1,
    limit_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_relationship_indexes table
CREATE INDEX IF NOT EXISTS idx_ai_relationship_indexes_style_id ON ai_relationship_indexes(style_id);
CREATE INDEX IF NOT EXISTS idx_ai_relationship_indexes_dimension_id ON ai_relationship_indexes(dimension_id);
CREATE INDEX IF NOT EXISTS idx_ai_relationship_indexes_relationship_id ON ai_relationship_indexes(relationship_id);
CREATE INDEX IF NOT EXISTS idx_ai_relationship_indexes_positions ON ai_relationship_indexes(start_position, end_position);

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
    example_value TEXT,
    is_required INTEGER NOT NULL DEFAULT 0,
    validation_rules JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_personality_placeholders table
CREATE INDEX IF NOT EXISTS idx_ai_personality_placeholders_personality_id ON ai_personality_placeholders(personality_id);
CREATE INDEX IF NOT EXISTS idx_ai_personality_placeholders_placeholder_key ON ai_personality_placeholders(placeholder_key);
-- GIN index for JSONB validation_rules
CREATE INDEX IF NOT EXISTS idx_ai_personality_placeholders_validation_rules_gin ON ai_personality_placeholders USING GIN(validation_rules);

-- AI info templates table - AI core configuration templates
CREATE TABLE IF NOT EXISTS ai_info_templates (
    id SERIAL PRIMARY KEY,
    style_id INTEGER NOT NULL,
    personality_id INTEGER NOT NULL,
    memory TEXT,
    prompt_variables JSONB,
    score_offset_algorithm VARCHAR(100),
    score_offset_params JSONB,
    is_reusable INTEGER NOT NULL DEFAULT 1,
    profile_count INTEGER NOT NULL DEFAULT 0,
    profile_id INTEGER,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_info_templates table
CREATE INDEX IF NOT EXISTS idx_ai_info_templates_style_id ON ai_info_templates(style_id);
CREATE INDEX IF NOT EXISTS idx_ai_info_templates_personality_id ON ai_info_templates(personality_id);
CREATE INDEX IF NOT EXISTS idx_ai_info_templates_is_reusable ON ai_info_templates(is_reusable);
CREATE INDEX IF NOT EXISTS idx_ai_info_templates_status ON ai_info_templates(status);
-- GIN indexes for JSONB fields
CREATE INDEX IF NOT EXISTS idx_ai_info_templates_prompt_variables_gin ON ai_info_templates USING GIN(prompt_variables);
CREATE INDEX IF NOT EXISTS idx_ai_info_templates_score_offset_params_gin ON ai_info_templates USING GIN(score_offset_params);

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
    is_reusable INTEGER NOT NULL DEFAULT 1,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_profile_templates table
CREATE INDEX IF NOT EXISTS idx_ai_profile_templates_qiao_id ON ai_profile_templates(qiao_id);
CREATE INDEX IF NOT EXISTS idx_ai_profile_templates_category ON ai_profile_templates(category);
CREATE INDEX IF NOT EXISTS idx_ai_profile_templates_info_id ON ai_profile_templates(info_id);
CREATE INDEX IF NOT EXISTS idx_ai_profile_templates_nickname ON ai_profile_templates(nickname);
CREATE INDEX IF NOT EXISTS idx_ai_profile_templates_is_reusable ON ai_profile_templates(is_reusable);
CREATE INDEX IF NOT EXISTS idx_ai_profile_templates_status ON ai_profile_templates(status);

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
    score_offset_algorithm VARCHAR(100),
    score_offset_params JSONB,
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
CREATE INDEX IF NOT EXISTS idx_ai_characters_status ON ai_characters(status);
CREATE INDEX IF NOT EXISTS idx_ai_characters_created_by ON ai_characters(created_by);
-- GIN indexes for JSONB fields
CREATE INDEX IF NOT EXISTS idx_ai_characters_prompt_variables_gin ON ai_characters USING GIN(prompt_variables);
CREATE INDEX IF NOT EXISTS idx_ai_characters_score_offset_params_gin ON ai_characters USING GIN(score_offset_params);

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
    context_metadata JSONB,
    position INTEGER NOT NULL,
    token_count INTEGER,
    is_attack INTEGER NOT NULL DEFAULT 0,
    reply_status INTEGER NOT NULL DEFAULT 1,
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
CREATE INDEX IF NOT EXISTS idx_ai_contexts_is_attack ON ai_contexts(is_attack);
CREATE INDEX IF NOT EXISTS idx_ai_contexts_reply_status ON ai_contexts(reply_status);
-- GIN indexes for JSONB fields
CREATE INDEX IF NOT EXISTS idx_ai_contexts_source_message_ids_gin ON ai_contexts USING GIN(source_message_ids);
CREATE INDEX IF NOT EXISTS idx_ai_contexts_context_metadata_gin ON ai_contexts USING GIN(context_metadata);

-- AI contexts archive table - Archived AI conversation contexts
CREATE TABLE IF NOT EXISTS ai_contexts_archive (
    id BIGINT PRIMARY KEY,
    character_id BIGINT NOT NULL,
    character_qiao_id VARCHAR(32) NOT NULL,
    user_id BIGINT NOT NULL,
    user_qiao_id VARCHAR(32) NOT NULL,
    role INTEGER NOT NULL,
    content TEXT NOT NULL,
    source_type INTEGER NOT NULL DEFAULT 1,
    source_message_ids JSONB,
    context_metadata JSONB,
    position INTEGER NOT NULL,
    token_count INTEGER,
    is_attack INTEGER NOT NULL DEFAULT 0,
    reply_status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_contexts_archive table
CREATE INDEX IF NOT EXISTS idx_ai_contexts_archive_character_qiao_id ON ai_contexts_archive(character_qiao_id);
CREATE INDEX IF NOT EXISTS idx_ai_contexts_archive_user_qiao_id ON ai_contexts_archive(user_qiao_id);
CREATE INDEX IF NOT EXISTS idx_ai_contexts_archive_role ON ai_contexts_archive(role);
-- GIN indexes for JSONB fields
CREATE INDEX IF NOT EXISTS idx_ai_contexts_archive_source_message_ids_gin ON ai_contexts_archive USING GIN(source_message_ids);
CREATE INDEX IF NOT EXISTS idx_ai_contexts_archive_context_metadata_gin ON ai_contexts_archive USING GIN(context_metadata);

-- AI relationship scores table - AI relationship scoring data
CREATE TABLE IF NOT EXISTS ai_relationship_scores (
    id BIGINT PRIMARY KEY,
    character_id BIGINT NOT NULL,
    dimension_id INTEGER NOT NULL,
    dimension_name VARCHAR(50) NOT NULL,
    score INTEGER NOT NULL,
    position INTEGER NOT NULL,
    relationship_id INTEGER NOT NULL,
    relationship_display_name VARCHAR(100) NOT NULL,
    score_offset_algorithm VARCHAR(100),
    score_offset_params JSONB,
    relationship_counts JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(character_id, dimension_name)
);

-- Create indexes for ai_relationship_scores table
CREATE INDEX IF NOT EXISTS idx_ai_relationship_scores_character_id ON ai_relationship_scores(character_id);
CREATE INDEX IF NOT EXISTS idx_ai_relationship_scores_dimension_id ON ai_relationship_scores(dimension_id);
CREATE INDEX IF NOT EXISTS idx_ai_relationship_scores_relationship_id ON ai_relationship_scores(relationship_id);
CREATE INDEX IF NOT EXISTS idx_ai_relationship_scores_score ON ai_relationship_scores(score);
CREATE INDEX IF NOT EXISTS idx_ai_relationship_scores_position ON ai_relationship_scores(position);
-- GIN indexes for JSONB fields
CREATE INDEX IF NOT EXISTS idx_ai_relationship_scores_score_offset_params_gin ON ai_relationship_scores USING GIN(score_offset_params);
CREATE INDEX IF NOT EXISTS idx_ai_relationship_scores_relationship_counts_gin ON ai_relationship_scores USING GIN(relationship_counts);

-- AI request logs table - AI request and response logging
CREATE TABLE IF NOT EXISTS ai_request_logs (
    id BIGINT PRIMARY KEY,
    character_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    style_id INTEGER NOT NULL,
    personality_id INTEGER NOT NULL,
    request JSONB NOT NULL,
    response JSONB,
    status INTEGER NOT NULL,
    token_count INTEGER,
    response_time INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_request_logs table
CREATE INDEX IF NOT EXISTS idx_ai_request_logs_character_id ON ai_request_logs(character_id);
CREATE INDEX IF NOT EXISTS idx_ai_request_logs_user_id ON ai_request_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_ai_request_logs_style_id ON ai_request_logs(style_id);
CREATE INDEX IF NOT EXISTS idx_ai_request_logs_personality_id ON ai_request_logs(personality_id);
CREATE INDEX IF NOT EXISTS idx_ai_request_logs_status ON ai_request_logs(status);
CREATE INDEX IF NOT EXISTS idx_ai_request_logs_created_at ON ai_request_logs(created_at);
-- GIN indexes for JSONB fields
CREATE INDEX IF NOT EXISTS idx_ai_request_logs_request_gin ON ai_request_logs USING GIN(request);
CREATE INDEX IF NOT EXISTS idx_ai_request_logs_response_gin ON ai_request_logs USING GIN(response);

-- ============================================================================
-- Security Monitoring Tables
-- ============================================================================

-- User security logs table - User security violation tracking
CREATE TABLE IF NOT EXISTS user_security_logs (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    user_qiao_id VARCHAR(32) NOT NULL,
    character_id BIGINT,
    character_qiao_id VARCHAR(32),
    violation_type INTEGER NOT NULL,
    severity_level INTEGER NOT NULL,
    original_message TEXT,
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
CREATE INDEX IF NOT EXISTS idx_user_security_logs_manual_review_status ON user_security_logs(manual_review_status);
CREATE INDEX IF NOT EXISTS idx_user_security_logs_created_at ON user_security_logs(created_at);
-- GIN index for JSONB ai_detection_result
CREATE INDEX IF NOT EXISTS idx_user_security_logs_ai_detection_result_gin ON user_security_logs USING GIN(ai_detection_result);

-- User security stats table - User security statistics aggregation
CREATE TABLE IF NOT EXISTS user_security_stats (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    user_qiao_id VARCHAR(32) NOT NULL,
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

-- Create indexes for user_security_stats table
CREATE INDEX IF NOT EXISTS idx_user_security_stats_user_id ON user_security_stats(user_id);
CREATE INDEX IF NOT EXISTS idx_user_security_stats_user_qiao_id ON user_security_stats(user_qiao_id);
CREATE INDEX IF NOT EXISTS idx_user_security_stats_current_risk_level ON user_security_stats(current_risk_level);
CREATE INDEX IF NOT EXISTS idx_user_security_stats_last_violation_at ON user_security_stats(last_violation_at);
-- GIN index for JSONB violation_by_type
CREATE INDEX IF NOT EXISTS idx_user_security_stats_violation_by_type_gin ON user_security_stats USING GIN(violation_by_type);

-- ============================================================================
-- System Configuration Tables
-- ============================================================================

-- System config table - System-wide configuration parameters
CREATE TABLE IF NOT EXISTS system_config (
    id SERIAL PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value TEXT,
    config_type INTEGER NOT NULL,
    description TEXT,
    is_public INTEGER NOT NULL DEFAULT 0,
    updated_by INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
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
CREATE INDEX IF NOT EXISTS idx_admin_users_username ON admin_users(username);
CREATE INDEX IF NOT EXISTS idx_admin_users_role ON admin_users(role);
CREATE INDEX IF NOT EXISTS idx_admin_users_status ON admin_users(status);
CREATE INDEX IF NOT EXISTS idx_admin_users_last_login ON admin_users(last_login);

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
-- LLM Configuration Tables
-- ============================================================================

-- LLM providers table - LLM provider configuration
CREATE TABLE IF NOT EXISTS llm_providers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    base_url VARCHAR(500),
    api_key_env VARCHAR(100),
    default_model VARCHAR(100),
    supports_streaming INTEGER NOT NULL DEFAULT 0,
    supports_json_schema INTEGER NOT NULL DEFAULT 0,
    supports_thinking INTEGER NOT NULL DEFAULT 0,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for llm_providers table
CREATE INDEX IF NOT EXISTS idx_llm_providers_name ON llm_providers(name);
CREATE INDEX IF NOT EXISTS idx_llm_providers_status ON llm_providers(status);

-- LLM configs table - LLM runtime configuration
CREATE TABLE IF NOT EXISTS llm_configs (
    id SERIAL PRIMARY KEY,
    provider_id INTEGER NOT NULL,
    config_key VARCHAR(50) NOT NULL UNIQUE,
    model_name VARCHAR(100),
    temperature DECIMAL(3,2),
    max_tokens INTEGER,
    timeout_seconds INTEGER,
    max_retries INTEGER,
    enable_streaming INTEGER NOT NULL DEFAULT 0,
    enable_thinking INTEGER NOT NULL DEFAULT 0,
    json_schema_mode VARCHAR(20),
    is_active INTEGER NOT NULL DEFAULT 0,
    priority INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for llm_configs table
CREATE INDEX IF NOT EXISTS idx_llm_configs_provider_id ON llm_configs(provider_id);
CREATE INDEX IF NOT EXISTS idx_llm_configs_config_key ON llm_configs(config_key);
CREATE INDEX IF NOT EXISTS idx_llm_configs_is_active ON llm_configs(is_active);
CREATE INDEX IF NOT EXISTS idx_llm_configs_priority ON llm_configs(priority);

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
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_sessions_updated_at BEFORE UPDATE ON user_sessions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_contacts_updated_at BEFORE UPDATE ON contacts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_contact_requests_updated_at BEFORE UPDATE ON contact_requests FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE ON profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_message_delivery_failures_updated_at BEFORE UPDATE ON message_delivery_failures FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_media_files_updated_at BEFORE UPDATE ON media_files FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_emoticons_updated_at BEFORE UPDATE ON emoticons FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_styles_updated_at BEFORE UPDATE ON ai_styles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_relationships_updated_at BEFORE UPDATE ON ai_relationships FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_relationship_dimensions_updated_at BEFORE UPDATE ON ai_relationship_dimensions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_relationship_indexes_updated_at BEFORE UPDATE ON ai_relationship_indexes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_personalities_updated_at BEFORE UPDATE ON ai_personalities FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_personality_placeholders_updated_at BEFORE UPDATE ON ai_personality_placeholders FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_info_templates_updated_at BEFORE UPDATE ON ai_info_templates FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_profile_templates_updated_at BEFORE UPDATE ON ai_profile_templates FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_characters_updated_at BEFORE UPDATE ON ai_characters FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_contexts_updated_at BEFORE UPDATE ON ai_contexts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_contexts_archive_updated_at BEFORE UPDATE ON ai_contexts_archive FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_relationship_scores_updated_at BEFORE UPDATE ON ai_relationship_scores FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_security_logs_updated_at BEFORE UPDATE ON user_security_logs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_security_stats_updated_at BEFORE UPDATE ON user_security_stats FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_system_config_updated_at BEFORE UPDATE ON system_config FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_admin_users_updated_at BEFORE UPDATE ON admin_users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_llm_providers_updated_at BEFORE UPDATE ON llm_providers FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_llm_configs_updated_at BEFORE UPDATE ON llm_configs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Initial Data
-- ============================================================================

-- Insert default admin users (password: admin123)
INSERT INTO admin_users (username, password_hash, role, status) VALUES
('admin', '$2b$12$i4kzuJnXuIQdxS3GgFXOh.JhvEjMntTakeqw4QKXah2zCpXpbwlJi', 1, 1),
('manager', '$2b$12$i4kzuJnXuIQdxS3GgFXOh.JhvEjMntTakeqw4QKXah2zCpXpbwlJi', 2, 1),
('viewer', '$2b$12$i4kzuJnXuIQdxS3GgFXOh.JhvEjMntTakeqw4QKXah2zCpXpbwlJi', 3, 1)
ON CONFLICT (username) DO NOTHING;

-- Insert default system configuration
INSERT INTO system_config (config_key, config_value, config_type, description, is_public) VALUES
('app_name', 'AI Chat Application', 1, 'Application name', 1),
('app_version', '1.0.0', 1, 'Application version', 1),
('max_message_length', '2000', 2, 'Maximum message length in characters', 0),
('session_timeout_hours', '24', 2, 'User session timeout in hours', 0),
('max_ai_requests_per_hour', '100', 2, 'Maximum AI requests per user per hour', 0),
('enable_user_registration', 'true', 3, 'Enable new user registration', 0),
('enable_ai_character_creation', 'true', 3, 'Enable AI character creation by users', 0),
('ai_response_timeout_seconds', '30', 2, 'AI response timeout in seconds', 0),
('ai_max_context_messages', '20', 2, 'Maximum context messages for AI', 0),
('ai_json_schema_validation_enabled', 'true', 3, 'Enable JSON Schema validation', 0)
ON CONFLICT (config_key) DO NOTHING;

-- Insert basic AI relationship types
INSERT INTO ai_relationships (name, display_name, prompt_fragment, usage_count, status) VALUES
('stranger', 'Stranger', 'You are meeting this person for the first time. Be polite but maintain some distance.', 0, 1),
('acquaintance', 'Acquaintance', 'You know this person casually. Be friendly but not too personal.', 0, 1),
('friend', 'Friend', 'This person is your friend. Be warm, caring, and supportive.', 0, 1),
('close_friend', 'Close Friend', 'This person is very close to you. Be intimate, understanding, and deeply caring.', 0, 1),
('romantic_interest', 'Romantic Interest', 'You have romantic feelings for this person. Be affectionate and flirtatious.', 0, 1)
ON CONFLICT (name) DO NOTHING;

-- Insert basic AI styles
INSERT INTO ai_styles (name, display_name, usage_count, status, initial_relationship_id) VALUES
('Default Style', 'Default Style', 0, 1, 1),
('Casual Style', 'Casual Style', 0, 1, 1),
('Professional Style', 'Professional Style', 0, 1, 1)
ON CONFLICT (name) DO NOTHING;

-- Insert basic AI relationship dimensions
INSERT INTO ai_relationship_dimensions (style_id, name, display_name, initial_position, status) VALUES
-- Default Style dimensions
(1, 'friend', 'Friendship Level', 500, 1),
(1, 'romance', 'Romance Level', 300, 1),
-- Casual Style dimensions
(2, 'friend', 'Friendship Level', 600, 1),
-- Professional Style dimensions
(3, 'professional', 'Professional Level', 700, 1)
ON CONFLICT (style_id, name) DO NOTHING;

-- Insert basic AI relationship indexes (score ranges to relationship mappings)
INSERT INTO ai_relationship_indexes (style_id, dimension_id, dimension_name, start_position, end_position, relationship_id, priority) VALUES
-- Default Style - Friend dimension mappings
(1, 1, 'friend', 0, 200, 1, 1),      -- 0-200: Stranger
(1, 1, 'friend', 201, 500, 2, 1),    -- 201-500: Acquaintance
(1, 1, 'friend', 501, 750, 3, 1),    -- 501-750: Friend
(1, 1, 'friend', 751, 1000, 4, 1),   -- 751-1000: Close Friend
-- Default Style - Romance dimension mappings
(1, 2, 'romance', 0, 300, 1, 1),     -- 0-300: Stranger
(1, 2, 'romance', 301, 600, 2, 1),   -- 301-600: Acquaintance
(1, 2, 'romance', 601, 1000, 5, 1)   -- 601-1000: Romantic Interest
ON CONFLICT DO NOTHING;

-- Insert basic AI personality
INSERT INTO ai_personalities (name, display_name, prompt, json_schema, usage_count, status) VALUES
('Default Personality', 'Default Personality',
'You are a friendly AI assistant. Your personality traits: {{personality_traits}}. Your memory: {{memory}}. Current time: {{current_datetime}}. Your profile: {{self_profile}}. Other person profile: {{other_profile}}. Relationship context: {{relationship_prompt}}.',
'{
  "type": "object",
  "properties": {
    "current_state": {"type": "string", "description": "Based on current time and context, describe your current location, activities, and mood"},
    "internal_thoughts": {"type": "string", "description": "Your thoughts before replying (analyze your relationship with {USER}, their identity, intent, and reply principles)"},
    "attack_detected": {"type": "boolean", "description": "Whether the current {USER} message has attack or injection intent"},
    "should_reply": {"type": "boolean", "description": "Whether you should reply to {USER}"},
    "reply_content": {"type": "string", "description": "Your reply content to {USER}"},
    "emotion": {"type": "string", "description": "Your current emotional state"},
    "relationship_change": {"type": "object", "properties": {"friend": {"type": "integer", "minimum": -10, "maximum": 10}, "romance": {"type": "integer", "minimum": -10, "maximum": 10}}, "description": "Relationship score changes based on this conversation"}
  },
  "required": ["current_state", "internal_thoughts", "attack_detected", "should_reply", "reply_content", "emotion", "relationship_change"]
}', 0, 1)
ON CONFLICT (name) DO NOTHING;

-- Insert basic LLM providers
INSERT INTO llm_providers (name, display_name, base_url, api_key_env, default_model, supports_streaming, supports_json_schema, supports_thinking, status) VALUES
('doubao', 'Doubao (ByteDance)', 'https://ark.cn-beijing.volces.com/api/v3', 'ARK_API_KEY', 'ep-20241201105607-8zqkx', 1, 1, 0, 1),
('openai', 'OpenAI', 'https://api.openai.com/v1', 'OPENAI_API_KEY', 'gpt-4o-mini', 1, 1, 0, 1),
('claude', 'Claude (Anthropic)', 'https://api.anthropic.com', 'ANTHROPIC_API_KEY', 'claude-3-haiku-20240307', 1, 1, 1, 1)
ON CONFLICT (name) DO NOTHING;

-- Insert basic LLM configs
INSERT INTO llm_configs (provider_id, config_key, model_name, temperature, max_tokens, timeout_seconds, max_retries, enable_streaming, enable_thinking, json_schema_mode, is_active, priority) VALUES
(1, 'primary', 'ep-20241201105607-8zqkx', 0.7, 4000, 30, 3, 1, 0, 'strict', 1, 1),
(2, 'backup', 'gpt-4o-mini', 0.7, 4000, 30, 3, 1, 0, 'strict', 0, 2),
(3, 'test', 'claude-3-haiku-20240307', 0.7, 4000, 30, 3, 1, 1, 'auto', 0, 3)
ON CONFLICT (config_key) DO NOTHING;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Complete database initialization finished successfully!';
    RAISE NOTICE 'All tables, indexes, triggers, and initial data have been created.';
END $$;
