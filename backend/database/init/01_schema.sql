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
-- Common Database Functions
-- ============================================================================

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Core User Management Tables
-- ============================================================================

-- Users table - Core user account information
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    qiao_id VARCHAR(32) NOT NULL UNIQUE,
    username VARCHAR(20) NULL,
    phone VARCHAR(20) UNIQUE,
    email VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255),
    is_verified INTEGER NOT NULL DEFAULT 0,
    verified_at TIMESTAMP WITH TIME ZONE,
    verify_source VARCHAR(100),
    verification_info JSONB,
    status INTEGER NOT NULL DEFAULT 1,
    needs_profile_setup BOOLEAN NOT NULL DEFAULT TRUE,
    user_type INTEGER NOT NULL DEFAULT 1,
    last_login TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for users table
-- Note: No additional indexes needed for MVP
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username_lower
    ON users (LOWER(username)) WHERE username IS NOT NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_users_username_format'
    ) THEN
        ALTER TABLE users DROP CONSTRAINT ck_users_username_format;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_users_username_length'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT ck_users_username_length
            CHECK (username IS NULL OR CHAR_LENGTH(username) BETWEEN 5 AND 20);
    END IF;
END $$;


-- User tokens table - JWT token management with device limits and dual-token support
CREATE TABLE IF NOT EXISTS user_tokens (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    user_qiao_id VARCHAR(32) NOT NULL,
    access_token VARCHAR(512) NOT NULL UNIQUE,
    device_type INTEGER NOT NULL,
    device_id UUID NOT NULL,
    platform_info JSONB,
    ip_address INET,
    user_agent TEXT,
    access_expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    status INTEGER NOT NULL DEFAULT 1,
    last_activity_at TIMESTAMP WITH TIME ZONE,
    access_revoked_at TIMESTAMP WITH TIME ZONE,
    refresh_token_hash VARCHAR(512),
    refresh_expires_at TIMESTAMP WITH TIME ZONE,
    refresh_revoked_at TIMESTAMP WITH TIME ZONE,
    token_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for user_tokens table
CREATE INDEX idx_user_tokens_user_qiao_id ON user_tokens(user_qiao_id);
CREATE UNIQUE INDEX idx_user_tokens_refresh_hash ON user_tokens(refresh_token_hash) WHERE refresh_token_hash IS NOT NULL;

-- Add foreign key constraint for user_tokens
ALTER TABLE user_tokens ADD CONSTRAINT fk_user_tokens_user
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

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
CREATE INDEX idx_user_auths_user_qiao_id ON user_auths(user_qiao_id);

-- Add foreign key constraint for user_auths
ALTER TABLE user_auths ADD CONSTRAINT fk_user_auths_user
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- Login records table - Login attempt tracking
CREATE TABLE IF NOT EXISTS login_records (
    id BIGINT PRIMARY KEY,
    user_id BIGINT,
    user_qiao_id VARCHAR(32),
    login_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    login_type INTEGER NOT NULL,
    platform INTEGER NOT NULL,
    device_id UUID,
    ip_address INET,
    user_agent TEXT,
    result INTEGER NOT NULL,
    fail_reason VARCHAR(255),
    user_token_id BIGINT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_login_records_user_token_id ON login_records(user_token_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_login_records_user_token'
    ) THEN
        ALTER TABLE login_records ADD CONSTRAINT fk_login_records_user_token
            FOREIGN KEY (user_token_id) REFERENCES user_tokens(id) ON DELETE SET NULL;
    END IF;
END $$;


-- ============================================================================
-- Media Files Tables (Must be defined before profiles/contacts for FK references)
-- ============================================================================

-- Media files table - Unified media file management (object storage)
CREATE TABLE IF NOT EXISTS media_files (
    id BIGINT PRIMARY KEY,
    file_id VARCHAR(32) NOT NULL UNIQUE,
    file_type SMALLINT NOT NULL,
    category VARCHAR(50),
    storage_provider VARCHAR(20) NOT NULL CHECK (storage_provider = 'tencent_cos'),
    bucket_name VARCHAR(100),
    object_key VARCHAR(500) NOT NULL,
    storage_region VARCHAR(50),
    original_name VARCHAR(255) NOT NULL,
    file_size INTEGER NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    file_hash VARCHAR(64),
    is_public BOOLEAN DEFAULT false,
    upload_by_type SMALLINT NOT NULL,
    upload_by_id BIGINT,
    upload_by_qiao_id VARCHAR(32),
    etag VARCHAR(64),
    confirmed_at TIMESTAMP WITH TIME ZONE,
    confirmed_by_id BIGINT,
    status SMALLINT NOT NULL DEFAULT 2,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON COLUMN media_files.etag IS 'ETag returned by storage provider (for upload verification)';
COMMENT ON COLUMN media_files.confirmed_at IS 'Upload confirmation timestamp';
COMMENT ON COLUMN media_files.confirmed_by_id IS 'User/admin ID who confirmed the upload (for audit trail)';
COMMENT ON COLUMN media_files.status IS 'File status: 1=active, 2=pending (awaiting confirmation), 3=deleted (soft delete)';

-- Create indexes for media_files table
CREATE INDEX idx_media_files_file_id ON media_files(file_id);
CREATE INDEX idx_media_files_upload_by ON media_files(upload_by_type, upload_by_id);
CREATE INDEX idx_media_files_status ON media_files(status);
CREATE INDEX idx_media_files_file_hash ON media_files(file_hash);
CREATE UNIQUE INDEX idx_media_files_storage_unique ON media_files(storage_provider, bucket_name, object_key);



-- ============================================================================
-- Contact Tables
-- ============================================================================

-- Contacts table - Contact relationships between users and AI
CREATE TABLE IF NOT EXISTS contacts (
    id BIGINT PRIMARY KEY,
    conversation_id VARCHAR(32) NOT NULL UNIQUE,
    user_id BIGINT,
    user_qiao_id VARCHAR(32),
    contact_type INTEGER NOT NULL,
    contact_id BIGINT NOT NULL,
    contact_qiao_id VARCHAR(32) NOT NULL,
    alias VARCHAR(100),
    custom_avatar_key VARCHAR(255),
    custom_avatar_media_id BIGINT,
    avatar_display_mode INTEGER NOT NULL DEFAULT 1,
    tags JSONB,
    remark TEXT,
    source INTEGER NOT NULL DEFAULT 0,
    is_pinned INTEGER NOT NULL DEFAULT 0,
    is_muted INTEGER NOT NULL DEFAULT 0,
    is_blocked INTEGER NOT NULL DEFAULT 0,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    -- Ensure one user cannot add the same qiao_id contact twice
    CONSTRAINT ck_contacts_avatar_display_mode CHECK (avatar_display_mode IN (1, 2)),
    CONSTRAINT ck_contacts_source CHECK (source IN (0, 1, 2, 3, 4, 5, 6)),
    CONSTRAINT uq_contacts_user_contact_qiao UNIQUE (user_id, contact_qiao_id),
    CONSTRAINT fk_contacts_custom_avatar_media FOREIGN KEY (custom_avatar_media_id) REFERENCES media_files(id) ON DELETE SET NULL
);

-- Create indexes for contacts table
CREATE INDEX idx_contacts_user_qiao_id ON contacts(user_qiao_id);
CREATE INDEX idx_contacts_contact_qiao_id ON contacts(contact_qiao_id);

-- Add foreign key constraint for contacts
ALTER TABLE contacts ADD CONSTRAINT fk_contacts_user
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- Contact requests table - Contact application management
CREATE TABLE IF NOT EXISTS contact_requests (
    id BIGINT PRIMARY KEY,
    from_qiao_id VARCHAR(32) NOT NULL,
    from_type INTEGER NOT NULL,
    from_id BIGINT NOT NULL,
    to_qiao_id VARCHAR(32) NOT NULL,
    to_type INTEGER NOT NULL,
    to_id BIGINT,  -- Allow NULL: AI instance not created yet when request is created
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
-- Profile Management Tables
-- ============================================================================

-- Profiles table - Unified profile management for users, AI, and official accounts
CREATE TABLE IF NOT EXISTS profiles (
    id BIGINT PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    owner_qiao_id VARCHAR(32) NOT NULL UNIQUE,
    owner_type INTEGER NOT NULL,
    nickname VARCHAR(100),
    gender INTEGER,
    avatar_key VARCHAR(255),
    avatar_media_id BIGINT,
    avatar_prompt TEXT,
    bio TEXT,
    region VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_profiles_avatar_media FOREIGN KEY (avatar_media_id) REFERENCES media_files(id) ON DELETE SET NULL
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

-- Message history table - Message facts (no delivery state)
CREATE TABLE IF NOT EXISTS message_history (
    id BIGINT PRIMARY KEY,
    direction INTEGER NOT NULL,
    conversation_id VARCHAR(32) NOT NULL,
    msg_id_server VARCHAR(64) NOT NULL UNIQUE,
    msg_id_provider_inbound VARCHAR(128),
    msg_id_client VARCHAR(64),
    client_sent_at TIMESTAMP WITH TIME ZONE,
    sent_at TIMESTAMP WITH TIME ZONE,
    from_type INTEGER NOT NULL,
    from_id BIGINT NOT NULL,
    from_qiao_id VARCHAR(32) NOT NULL,
    to_type INTEGER NOT NULL,
    to_id BIGINT NOT NULL,
    to_qiao_id VARCHAR(32) NOT NULL,
    message_type INTEGER NOT NULL,
    content TEXT,
    inbound_provider SMALLINT,
    inbound_device_id UUID,
    message_metadata JSONB,
    llm_request_id BIGINT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_message_history_conv_client_id UNIQUE (conversation_id, msg_id_client),
    CONSTRAINT ck_message_history_inbound_provider
        CHECK (inbound_provider IS NULL OR inbound_provider IN (1, 2))
);

-- Create indexes for message_history table
CREATE INDEX idx_message_history_conversation_id ON message_history(conversation_id);
CREATE INDEX idx_message_history_from_qiao_id ON message_history(from_qiao_id);
CREATE INDEX idx_message_history_to_qiao_id ON message_history(to_qiao_id);
CREATE INDEX idx_message_history_created_at ON message_history(created_at);
CREATE INDEX idx_message_history_msg_id_client ON message_history(msg_id_client);
CREATE INDEX idx_message_history_llm_request_id ON message_history(llm_request_id);
-- GIN index for JSONB message_metadata
CREATE INDEX idx_message_history_metadata_gin ON message_history USING GIN(message_metadata);

-- message_devices table - offline cursor and device-level state (cursor is per (user_id, device_id))
CREATE TABLE IF NOT EXISTS message_devices (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    user_qiao_id VARCHAR(32) NOT NULL,
    device_id UUID NOT NULL,
    last_acked_msg_id VARCHAR(64),
    last_acked_msg_sent_at TIMESTAMP WITH TIME ZONE,
    last_pull_at TIMESTAMP WITH TIME ZONE,
    last_seen_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_message_devices_user_device UNIQUE (user_id, device_id)
);

CREATE INDEX idx_message_devices_user_qiao_id ON message_devices(user_qiao_id);
CREATE INDEX idx_message_devices_device_id ON message_devices(device_id);
CREATE INDEX idx_message_devices_last_acked_msg_sent_at ON message_devices(last_acked_msg_sent_at);

ALTER TABLE message_devices ADD CONSTRAINT fk_message_devices_user
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- Endpoints table - routable targets (provider binding + lease)
CREATE TABLE IF NOT EXISTS message_endpoints (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    user_qiao_id VARCHAR(32) NOT NULL,
    endpoint_scope SMALLINT NOT NULL,
    device_id UUID,
    provider SMALLINT NOT NULL,
    target_key VARCHAR(256) NOT NULL,
    client_kind SMALLINT,
    lease_expires_at TIMESTAMP WITH TIME ZONE,
    last_seen_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_message_endpoints_provider_user_target UNIQUE (provider, user_id, target_key),
    CONSTRAINT ck_message_endpoints_provider CHECK (provider IN (1, 2)),
    CONSTRAINT ck_message_endpoints_scope CHECK (endpoint_scope IN (1, 2)),
    CONSTRAINT ck_message_endpoints_scope_device CHECK (
        (endpoint_scope = 1 AND device_id IS NULL) OR
        (endpoint_scope = 2 AND device_id IS NOT NULL)
    )
);

CREATE INDEX idx_message_endpoints_user_qiao_id ON message_endpoints(user_qiao_id);
CREATE INDEX idx_message_endpoints_device_id ON message_endpoints(device_id);
CREATE INDEX idx_message_endpoints_provider ON message_endpoints(provider);
CREATE INDEX idx_message_endpoints_scope ON message_endpoints(endpoint_scope);
CREATE INDEX idx_message_endpoints_lease_expires_at ON message_endpoints(lease_expires_at);
CREATE UNIQUE INDEX uq_message_endpoints_provider_user_device_scope ON message_endpoints(provider, user_id, device_id) WHERE endpoint_scope = 2;

ALTER TABLE message_endpoints ADD CONSTRAINT fk_message_endpoints_user
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE message_endpoints ADD CONSTRAINT fk_message_endpoints_device
    FOREIGN KEY (user_id, device_id) REFERENCES message_devices(user_id, device_id) ON DELETE CASCADE;

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

-- Message deliveries table - delivery records per endpoint
CREATE TABLE IF NOT EXISTS message_deliveries (
    id BIGINT PRIMARY KEY,
    msg_id_server VARCHAR(64) NOT NULL,
    endpoint_id BIGINT NOT NULL,
    provider SMALLINT NOT NULL,
    target_key VARCHAR(256) NOT NULL,
    provider_msg_id VARCHAR(128),
    status SMALLINT NOT NULL,
    dispatched_at TIMESTAMP WITH TIME ZONE,
    failed_reason_code VARCHAR(50),
    failed_detail TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_message_deliveries_msg_endpoint UNIQUE (msg_id_server, endpoint_id),
    CONSTRAINT ck_message_deliveries_provider CHECK (provider IN (1, 2)),
    CONSTRAINT ck_message_deliveries_status CHECK (status IN (1, 2, 3))
);

CREATE INDEX idx_message_deliveries_msg_id_server ON message_deliveries(msg_id_server);
CREATE INDEX idx_message_deliveries_endpoint_id ON message_deliveries(endpoint_id);
CREATE INDEX idx_message_deliveries_status ON message_deliveries(status);

ALTER TABLE message_deliveries ADD CONSTRAINT fk_message_deliveries_message
    FOREIGN KEY (msg_id_server) REFERENCES message_history(msg_id_server) ON DELETE CASCADE;
ALTER TABLE message_deliveries ADD CONSTRAINT fk_message_deliveries_endpoint
    FOREIGN KEY (endpoint_id) REFERENCES message_endpoints(id) ON DELETE CASCADE;

-- Message dispatch outbox table - dispatch task queue with retry state
CREATE TABLE IF NOT EXISTS message_dispatch_outbox (
    id BIGINT PRIMARY KEY,
    outbox_type SMALLINT NOT NULL,
    msg_id_server VARCHAR(64) NOT NULL,
    owner_user_id BIGINT NOT NULL,
    status SMALLINT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    next_retry_at TIMESTAMP WITH TIME ZONE,
    locked_at TIMESTAMP WITH TIME ZONE,
    last_error_code VARCHAR(50),
    last_error_detail TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_message_dispatch_outbox_type_msg UNIQUE (outbox_type, msg_id_server),
    CONSTRAINT ck_message_dispatch_outbox_type CHECK (outbox_type IN (1)),
    CONSTRAINT ck_message_dispatch_outbox_status CHECK (status IN (1, 2, 3, 4)),
    CONSTRAINT ck_message_dispatch_outbox_attempt_count CHECK (attempt_count >= 0)
);

CREATE INDEX idx_message_dispatch_outbox_status_next_retry ON message_dispatch_outbox(status, next_retry_at);
CREATE INDEX idx_message_dispatch_outbox_owner_user_id ON message_dispatch_outbox(owner_user_id);

ALTER TABLE message_dispatch_outbox ADD CONSTRAINT fk_message_dispatch_outbox_message
    FOREIGN KEY (msg_id_server) REFERENCES message_history(msg_id_server) ON DELETE CASCADE;
ALTER TABLE message_dispatch_outbox ADD CONSTRAINT fk_message_dispatch_outbox_owner_user
    FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE;


-- ============================================================================
-- AI System Tables
-- ============================================================================

-- AI styles table - AI style definitions
CREATE TABLE IF NOT EXISTS ai_styles (
    id SERIAL PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for ai_styles table
-- Note: No additional indexes needed for MVP


-- AI relationships table - Relationship type definitions
CREATE TABLE IF NOT EXISTS ai_relationships (
    id SERIAL PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    prompt_fragment TEXT,
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

-- Add foreign key constraints for ai_style_dimensions
ALTER TABLE ai_style_dimensions ADD CONSTRAINT fk_ai_style_dimensions_style
    FOREIGN KEY (style_id) REFERENCES ai_styles(id) ON DELETE CASCADE;
ALTER TABLE ai_style_dimensions ADD CONSTRAINT fk_ai_style_dimensions_dimension
    FOREIGN KEY (dimension_id) REFERENCES ai_dimensions(id) ON DELETE CASCADE;


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

-- Add foreign key constraints for ai_dimension_relationship_mappings
ALTER TABLE ai_dimension_relationship_mappings ADD CONSTRAINT fk_ai_dim_rel_mappings_dimension
    FOREIGN KEY (dimension_id) REFERENCES ai_dimensions(id) ON DELETE CASCADE;
ALTER TABLE ai_dimension_relationship_mappings ADD CONSTRAINT fk_ai_dim_rel_mappings_relationship
    FOREIGN KEY (relationship_id) REFERENCES ai_relationships(id) ON DELETE CASCADE;


-- AI personalities table - Personality templates
CREATE TABLE IF NOT EXISTS ai_personalities (
    id SERIAL PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    prompt TEXT NOT NULL,
    json_schema JSONB,
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

-- Add foreign key constraint for ai_personality_placeholders
ALTER TABLE ai_personality_placeholders ADD CONSTRAINT fk_ai_personality_placeholders_personality
    FOREIGN KEY (personality_id) REFERENCES ai_personalities(id) ON DELETE CASCADE;


-- AI template types table - Internal management types (NOT related to Square categories)
CREATE TABLE IF NOT EXISTS ai_types (
    id SERIAL PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE ai_types IS 'AI template types - INTERNAL inventory groupings, NOT related to Square categories';
COMMENT ON COLUMN ai_types.display_name IS 'Display name for admin dashboard';

-- Create indexes for ai_types table
-- Note: No additional indexes needed for MVP


-- ============================================================================
-- Square Discovery Tables
-- ============================================================================

-- Square type entries - decouple Square exposure from persona inventory
CREATE TABLE IF NOT EXISTS square_type_entries (
    id SERIAL PRIMARY KEY,
    square_category INTEGER NOT NULL,
    type_id INTEGER NOT NULL,
    exposure_strategy INTEGER NOT NULL DEFAULT 1,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(square_category, type_id)
);

COMMENT ON TABLE square_type_entries IS 'Square discovery entries - decoupled from template/profile inventory';
COMMENT ON COLUMN square_type_entries.square_category IS 'Square category enum: 1=friend, 2=love, 3=talk, 4=bestie, 5=hobby';
COMMENT ON COLUMN square_type_entries.exposure_strategy IS 'Exposure strategy enum: 1=random';
COMMENT ON COLUMN square_type_entries.status IS '1=active, 2=inactive';
COMMENT ON COLUMN square_type_entries.type_id IS 'AI type exposed in this slot (references ai_types)';

CREATE INDEX idx_square_type_entries_status ON square_type_entries(status);
CREATE INDEX idx_square_type_entries_category ON square_type_entries(square_category);
CREATE INDEX idx_square_type_entries_ai_type ON square_type_entries(type_id);

-- Add foreign key constraint for square_type_entries
ALTER TABLE square_type_entries ADD CONSTRAINT fk_square_type_entries_type
    FOREIGN KEY (type_id) REFERENCES ai_types(id) ON DELETE RESTRICT;


-- AI templates table - AI core configuration templates (renamed from ai_templates)
CREATE TABLE IF NOT EXISTS ai_templates (
    id SERIAL PRIMARY KEY,
    type_id INTEGER NOT NULL,
    style_id INTEGER NOT NULL,
    personality_id INTEGER NOT NULL,
    prompt_variables JSONB,
    request_params JSONB,
    llm_config_id INTEGER,
    timezone VARCHAR(50) NOT NULL DEFAULT 'Asia/Shanghai',
    typing_speed_wpm INTEGER NOT NULL,
    display_name VARCHAR(100),
    position_mapping_config JSONB,
    is_reusable INTEGER NOT NULL DEFAULT 1,
    priority INTEGER NOT NULL DEFAULT 1,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE ai_templates IS 'AI templates - core configuration templates for AI instances';
COMMENT ON COLUMN ai_templates.type_id IS 'AI type ID (internal management), NOT related to Square categories';
COMMENT ON COLUMN ai_templates.request_params IS 'Template-level LLM request parameters (temperature, max_tokens, etc.) - inherited by instances';
COMMENT ON COLUMN ai_templates.llm_config_id IS 'Soft reference to llm_configs.id; NULL uses system default';
COMMENT ON COLUMN ai_templates.timezone IS 'Default IANA timezone copied to AI instances';
COMMENT ON COLUMN ai_templates.is_reusable IS '1=reusable (can create multiple instances), 0=non-reusable (can only create once)';
COMMENT ON COLUMN ai_templates.priority IS 'Priority for selection, lower number = higher priority (non-reusable templates have priority)';
COMMENT ON COLUMN ai_templates.status IS '1=active, 2=inactive, 3=used (only for is_reusable=0, after being used once)';

-- Create indexes for ai_templates table
CREATE INDEX idx_ai_templates_ai_type ON ai_templates(type_id);
CREATE INDEX idx_ai_templates_usage ON ai_templates(type_id, status, is_reusable);
CREATE INDEX idx_ai_templates_llm_config ON ai_templates(llm_config_id) WHERE llm_config_id IS NOT NULL;

-- Add foreign key constraints for ai_templates
ALTER TABLE ai_templates ADD CONSTRAINT fk_ai_templates_type
    FOREIGN KEY (type_id) REFERENCES ai_types(id) ON DELETE RESTRICT;
ALTER TABLE ai_templates ADD CONSTRAINT fk_ai_templates_style
    FOREIGN KEY (style_id) REFERENCES ai_styles(id) ON DELETE RESTRICT;
ALTER TABLE ai_templates ADD CONSTRAINT fk_ai_templates_personality
    FOREIGN KEY (personality_id) REFERENCES ai_personalities(id) ON DELETE RESTRICT;


-- AI template memories table - Seed memories for templates to be copied to instances
CREATE TABLE IF NOT EXISTS ai_template_memories (
    id BIGINT PRIMARY KEY,
    template_id INTEGER NOT NULL,
    memory_type VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    importance INTEGER NOT NULL DEFAULT 5,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_template_memories_type
        CHECK (memory_type IN ('core', 'recent')),
    CONSTRAINT ck_template_memories_importance
        CHECK (importance >= 1 AND importance <= 10)
);

COMMENT ON TABLE ai_template_memories IS 'Template seed memories - static memory definitions copied to instances during instantiation';
COMMENT ON COLUMN ai_template_memories.template_id IS 'Reference to ai_templates.id';
COMMENT ON COLUMN ai_template_memories.memory_type IS 'core=permanent, recent=will fade with time';
COMMENT ON COLUMN ai_template_memories.content IS 'Memory content - concise description';
COMMENT ON COLUMN ai_template_memories.importance IS 'Importance level 1-10, determines lifetime (importance × 10 = days)';
COMMENT ON COLUMN ai_template_memories.display_order IS 'Display and copy order, lower value = higher priority';

-- Create indexes for ai_template_memories table
CREATE INDEX idx_template_memories_template
    ON ai_template_memories(template_id, display_order);

-- Add foreign key constraint for ai_template_memories
ALTER TABLE ai_template_memories ADD CONSTRAINT fk_template_memories_template
    FOREIGN KEY (template_id) REFERENCES ai_templates(id) ON DELETE CASCADE;

-- Create trigger for ai_template_memories
DROP TRIGGER IF EXISTS update_ai_template_memories_updated_at ON ai_template_memories;
CREATE TRIGGER update_ai_template_memories_updated_at
    BEFORE UPDATE ON ai_template_memories
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- AI persona table - Manages unique qiao_id for instances (replaces ai_profile_templates)
CREATE TABLE IF NOT EXISTS ai_personas (
    id BIGINT PRIMARY KEY,
    qiao_id VARCHAR(32) NOT NULL UNIQUE,
    username VARCHAR(20) NOT NULL,
    type_id INTEGER NOT NULL,
    is_reusable INTEGER NOT NULL DEFAULT 1,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE ai_personas IS 'AI personas - manages unique qiao_id inventory (similar to product SKU)';
COMMENT ON COLUMN ai_personas.qiao_id IS 'External unique identifier, visible to users in Square';
COMMENT ON COLUMN ai_personas.username IS 'Public AI username, unique in ai_personas (case-insensitive)';
COMMENT ON COLUMN ai_personas.type_id IS 'AI type ID (internal management), NOT related to Square categories';
COMMENT ON COLUMN ai_personas.is_reusable IS '1=reusable (multiple users can add), 0=non-reusable (only one user can add)';
COMMENT ON COLUMN ai_personas.status IS '1=active (visible), 2=inactive (hidden), 3=used (single-use consumed)';

-- Create indexes for ai_personas table
CREATE INDEX idx_ai_personas_ai_type ON ai_personas(type_id);
CREATE INDEX idx_ai_personas_status ON ai_personas(status);
CREATE UNIQUE INDEX uq_ai_personas_username_lower ON ai_personas(LOWER(username));

-- Add foreign key constraint for ai_personas
ALTER TABLE ai_personas ADD CONSTRAINT fk_ai_personas_type
    FOREIGN KEY (type_id) REFERENCES ai_types(id) ON DELETE RESTRICT;


-- AI instances table - user-specific persona instantiations
CREATE TABLE IF NOT EXISTS ai_instances (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    user_qiao_id VARCHAR(32) NOT NULL,
    qiao_id VARCHAR(32) NOT NULL,
    username VARCHAR(20),
    creation_metadata JSONB NOT NULL,
    style_id INTEGER NOT NULL,
    personality_id INTEGER NOT NULL,
    status INTEGER NOT NULL DEFAULT 1,
    prompt_variables JSONB,
    relationship_id INTEGER,
    relationship_counts JSONB,
    request_params JSONB,
    llm_config_id INTEGER,
    typing_speed_wpm INTEGER NOT NULL,
    timezone VARCHAR(50) NOT NULL DEFAULT 'Asia/Shanghai',
    created_by INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ai_instances_user_qiao UNIQUE (user_id, qiao_id),
    CONSTRAINT ck_ai_instances_manual_username_null
        CHECK ((creation_metadata->>'source') <> 'admin_manual' OR username IS NULL)
);

-- Create indexes for ai_instances table
CREATE INDEX idx_ai_instances_user_id ON ai_instances(user_id);
CREATE INDEX idx_ai_instances_user_qiao_id ON ai_instances(user_qiao_id);
CREATE INDEX idx_ai_instances_user_username ON ai_instances(user_id, username);
CREATE INDEX idx_ai_instances_qiao_id ON ai_instances(qiao_id);
CREATE INDEX idx_ai_instances_style_id ON ai_instances(style_id);
CREATE INDEX idx_ai_instances_personality_id ON ai_instances(personality_id);
CREATE INDEX idx_ai_instances_llm_config ON ai_instances(llm_config_id) WHERE llm_config_id IS NOT NULL;
CREATE INDEX idx_ai_instances_creation_persona ON ai_instances USING gin((creation_metadata -> 'persona_id'));

-- Add foreign key constraints for ai_instances
ALTER TABLE ai_instances ADD CONSTRAINT fk_ai_instances_user
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE ai_instances ADD CONSTRAINT fk_ai_instances_style
    FOREIGN KEY (style_id) REFERENCES ai_styles(id) ON DELETE RESTRICT;
ALTER TABLE ai_instances ADD CONSTRAINT fk_ai_instances_personality
    FOREIGN KEY (personality_id) REFERENCES ai_personalities(id) ON DELETE RESTRICT;
ALTER TABLE ai_instances ADD CONSTRAINT fk_ai_instances_relationship
    FOREIGN KEY (relationship_id) REFERENCES ai_relationships(id) ON DELETE RESTRICT;

-- Add comments for fields
COMMENT ON TABLE ai_instances IS 'AI instances - created when users add personas';
COMMENT ON COLUMN ai_instances.qiao_id IS 'External persona identifier (multiple users can add same persona)';
COMMENT ON COLUMN ai_instances.username IS 'Runtime username snapshot; source=persona should equal persona.username, source=admin_manual must be NULL';
COMMENT ON COLUMN ai_instances.creation_metadata IS 'Immutable snapshot at creation time (persona_id, persona_qiao_id, persona_type_id, persona_type_name, template_id, template_display_name, etc.)';
COMMENT ON COLUMN ai_instances.user_id IS 'Owning user ID (each row belongs to exactly one user)';
COMMENT ON COLUMN ai_instances.user_qiao_id IS 'Owning user qiao_id (redundant for query convenience)';
COMMENT ON COLUMN ai_instances.status IS '1=active, 2=inactive, 3=blocking (AI has blocked the user)';
COMMENT ON COLUMN ai_instances.request_params IS 'AI instance request parameters configuration (JSON)';
COMMENT ON COLUMN ai_instances.llm_config_id IS 'Preferred llm_configs.id; NULL falls back to primary config';
COMMENT ON COLUMN ai_instances.timezone IS 'IANA timezone for the instance (e.g., Asia/Shanghai)';

-- AI conversation state table - manages conversation state and pending messages
CREATE TABLE IF NOT EXISTS ai_conversation_state (
    user_qiao_id VARCHAR(32) NOT NULL,
    instance_qiao_id VARCHAR(32) NOT NULL,
    pending_messages JSONB,
    interrupted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_qiao_id, instance_qiao_id)
);

CREATE INDEX idx_ai_conversation_state_updated ON ai_conversation_state(updated_at);

COMMENT ON TABLE ai_conversation_state IS 'AI conversation state - tracks pending messages and interruption state';
COMMENT ON COLUMN ai_conversation_state.pending_messages IS 'Pending outgoing payload {"outgoing":[...],"total_pending":N}';
COMMENT ON COLUMN ai_conversation_state.interrupted_at IS 'Timestamp when conversation was interrupted by user message';

-- AI conversation runtime table - turn version source for delayed preemption
CREATE TABLE IF NOT EXISTS ai_conversation_runtime (
    user_qiao_id VARCHAR(32) NOT NULL,
    instance_qiao_id VARCHAR(32) NOT NULL,
    ingress_version BIGINT NOT NULL DEFAULT 0,
    active_turn_version BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_qiao_id, instance_qiao_id)
);

CREATE INDEX idx_ai_conversation_runtime_updated ON ai_conversation_runtime(updated_at);

COMMENT ON TABLE ai_conversation_runtime IS 'AI conversation runtime turn versions for delayed preemption';
COMMENT ON COLUMN ai_conversation_runtime.ingress_version IS 'Inbound version incremented on each content input';
COMMENT ON COLUMN ai_conversation_runtime.active_turn_version IS 'Active processing version switched on new locked window';

-- AI message buffer table - aggregation windows for inbound messages
CREATE TABLE IF NOT EXISTS ai_message_buffer (
    id BIGINT PRIMARY KEY,
    user_qiao_id VARCHAR(32) NOT NULL,
    instance_qiao_id VARCHAR(32) NOT NULL,
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

CREATE INDEX idx_ai_message_buffer_session_state ON ai_message_buffer(user_qiao_id, instance_qiao_id, aggregate_state);
CREATE UNIQUE INDEX uniq_ai_message_buffer_locked ON ai_message_buffer(user_qiao_id, instance_qiao_id) WHERE aggregate_state = 2;
CREATE INDEX idx_ai_message_buffer_expire_scan ON ai_message_buffer(user_qiao_id, instance_qiao_id, buffer_expires_at_ms) WHERE aggregate_state IN (0, 1) AND buffer_expires_at_ms IS NOT NULL;

COMMENT ON COLUMN ai_message_buffer.buffer_expires_at_ms IS 'Effective processing deadline (ms), combining micro/macro timers with wake gate';
COMMENT ON COLUMN ai_message_buffer.wake_expires_at_ms IS 'Wake gate deadline (ms), NULL when wake gate is inactive';
COMMENT ON COLUMN ai_message_buffer.wake_adjustment_count IS 'Number of times wake time was adjusted by new messages';

-- AI conversation items table - simple message fields
CREATE TABLE IF NOT EXISTS ai_conversation_items (
    id BIGINT PRIMARY KEY,
    user_qiao_id VARCHAR(32) NOT NULL,
    instance_qiao_id VARCHAR(32) NOT NULL,
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

CREATE INDEX idx_ai_conv_items_session ON ai_conversation_items(user_qiao_id, instance_qiao_id, created_at DESC);
CREATE INDEX idx_ai_conv_items_buffer ON ai_conversation_items(buffer_id) WHERE buffer_id IS NOT NULL;
CREATE INDEX idx_ai_conv_items_text_search ON ai_conversation_items USING gin(text_content gin_trgm_ops);
CREATE INDEX idx_ai_conv_items_excluded ON ai_conversation_items(user_qiao_id, instance_qiao_id, created_at DESC) WHERE is_excluded_from_context = 1;

-- AI conversation archive table - cold storage for history
CREATE TABLE IF NOT EXISTS ai_conversation_items_archive (
    id BIGINT PRIMARY KEY,
    user_qiao_id VARCHAR(32) NOT NULL,
    instance_qiao_id VARCHAR(32) NOT NULL,
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

CREATE INDEX idx_ai_conv_items_archive_session ON ai_conversation_items_archive(user_qiao_id, instance_qiao_id, created_at DESC);


-- AI instance dimensions table - AI instance dimension scoring data
CREATE TABLE IF NOT EXISTS ai_instance_dimensions (
    id BIGINT PRIMARY KEY,
    instance_id BIGINT NOT NULL,
    dimension_id INTEGER NOT NULL,
    score INTEGER NOT NULL,
    position INTEGER NOT NULL,
    position_mapping_algorithm INTEGER DEFAULT 1,
    position_mapping_params JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(instance_id, dimension_id)
);

-- Create indexes for ai_instance_dimensions table
CREATE INDEX idx_ai_instance_dimensions_instance_id ON ai_instance_dimensions(instance_id);
CREATE INDEX idx_ai_instance_dimensions_dimension_id ON ai_instance_dimensions(dimension_id);

-- Add foreign key constraints for ai_instance_dimensions
ALTER TABLE ai_instance_dimensions ADD CONSTRAINT fk_ai_instance_dimensions_instance
    FOREIGN KEY (instance_id) REFERENCES ai_instances(id) ON DELETE CASCADE;
ALTER TABLE ai_instance_dimensions ADD CONSTRAINT fk_ai_instance_dimensions_dimension
    FOREIGN KEY (dimension_id) REFERENCES ai_dimensions(id) ON DELETE CASCADE;


-- AI request logs table - AI request and response logging
CREATE TABLE IF NOT EXISTS ai_request_logs (
    id BIGINT PRIMARY KEY,
    instance_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    user_qiao_id VARCHAR(32) NOT NULL,
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

ALTER TABLE message_history ADD CONSTRAINT fk_message_history_llm_request
    FOREIGN KEY (llm_request_id) REFERENCES ai_request_logs(id) ON DELETE SET NULL;

CREATE INDEX idx_ai_request_logs_response_id ON ai_request_logs(response_id);
CREATE INDEX idx_ai_request_logs_user_qiao_id ON ai_request_logs(user_qiao_id);



-- ============================================================================
-- AI Memory System
-- ============================================================================

-- AI instance memories table - AI's memories about users with importance-based lifetime
CREATE TABLE IF NOT EXISTS ai_instance_memories (
    id BIGINT PRIMARY KEY,
    instance_id BIGINT NOT NULL,
    instance_qiao_id VARCHAR(32) NOT NULL,
    user_id BIGINT NOT NULL,
    user_qiao_id VARCHAR(32) NOT NULL,
    memory_type VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    importance INTEGER NOT NULL DEFAULT 5,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    refreshed_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    source_message_id BIGINT,
    status INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_ai_instance_memories_type CHECK (memory_type IN ('core', 'recent')),
    CONSTRAINT ck_ai_instance_memories_importance CHECK (importance >= 1 AND importance <= 10),
    CONSTRAINT ck_ai_instance_memories_status CHECK (status IN (1, 2))
);

-- Create indexes for ai_instance_memories table
CREATE INDEX idx_ai_instance_memories_session ON ai_instance_memories(user_qiao_id, instance_qiao_id, status);
CREATE INDEX idx_ai_instance_memories_instance_id ON ai_instance_memories(instance_id);
CREATE UNIQUE INDEX uq_ai_instance_memories_content ON ai_instance_memories(instance_id, content);
-- Performance optimization: use expires_at for fast filtering of unexpired recent memories
CREATE INDEX idx_ai_instance_memories_expires ON ai_instance_memories(memory_type, status, expires_at) WHERE memory_type = 'recent' AND status = 1;
-- Traceability: link to source message (optional)
CREATE INDEX idx_ai_instance_memories_source ON ai_instance_memories(source_message_id) WHERE source_message_id IS NOT NULL;

-- Add foreign key constraint for ai_instance_memories
ALTER TABLE ai_instance_memories ADD CONSTRAINT fk_ai_instance_memories_user
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE ai_instance_memories ADD CONSTRAINT fk_ai_instance_memories_instance
    FOREIGN KEY (instance_id) REFERENCES ai_instances(id) ON DELETE CASCADE;

-- Add comments for ai_instance_memories table
COMMENT ON TABLE ai_instance_memories IS 'AI instance memories - manages AI memories about users with importance-based lifetime';
COMMENT ON COLUMN ai_instance_memories.memory_type IS 'Memory type: core (permanent), recent (will fade)';
COMMENT ON COLUMN ai_instance_memories.content IS 'Memory content - concise one-sentence description';
COMMENT ON COLUMN ai_instance_memories.importance IS 'Importance level 1-10, determines lifetime (importance × 10 = days)';
COMMENT ON COLUMN ai_instance_memories.refreshed_at IS 'AI refresh timestamp, resets lifetime if not NULL';
COMMENT ON COLUMN ai_instance_memories.expires_at IS 'Pre-calculated expiration timestamp (auto-computed by trigger for recent memories)';
COMMENT ON COLUMN ai_instance_memories.source_message_id IS 'Source message ID that triggered this memory creation (for traceability)';
COMMENT ON COLUMN ai_instance_memories.status IS 'Status: 1=active, 2=archived (forgotten)';

-- Trigger function for auto-calculating expires_at
CREATE OR REPLACE FUNCTION calculate_memory_expires_at()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.memory_type = 'recent' THEN
        NEW.expires_at := COALESCE(NEW.refreshed_at, NEW.created_at) +
                         (NEW.importance * INTERVAL '10 days');
    ELSE
        NEW.expires_at := NULL;  -- core memories never expire
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for ai_instance_memories
DROP TRIGGER IF EXISTS update_ai_instance_memories_updated_at ON ai_instance_memories;
CREATE TRIGGER update_ai_instance_memories_updated_at
    BEFORE UPDATE ON ai_instance_memories
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS set_memory_expires_at ON ai_instance_memories;
CREATE TRIGGER set_memory_expires_at
    BEFORE INSERT OR UPDATE OF importance, refreshed_at, memory_type
    ON ai_instance_memories
    FOR EACH ROW
    EXECUTE FUNCTION calculate_memory_expires_at();


-- ============================================================================
-- Security Monitoring Tables
-- ============================================================================

-- User violation logs table - User security violation tracking
CREATE TABLE IF NOT EXISTS user_violation_logs (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    user_qiao_id VARCHAR(32) NOT NULL,
    instance_id BIGINT,
    instance_qiao_id VARCHAR(32),
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

-- App pages table - rendered page content for client display
CREATE TABLE IF NOT EXISTS app_pages (
    id BIGINT PRIMARY KEY,
    page_key VARCHAR(64) NOT NULL,
    client_type VARCHAR(32) NOT NULL,
    locale VARCHAR(16) NOT NULL,
    page_category SMALLINT NOT NULL,
    title VARCHAR(200),
    source_type SMALLINT NOT NULL,
    content_md TEXT,
    content_html TEXT,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_app_pages_page_client_locale UNIQUE (page_key, client_type, locale),
    CONSTRAINT ck_app_pages_client_type CHECK (client_type IN ('mini-program')),
    CONSTRAINT ck_app_pages_locale CHECK (locale IN ('zh-CN')),
    CONSTRAINT ck_app_pages_page_category CHECK (page_category IN (1, 2)),
    CONSTRAINT ck_app_pages_source_type CHECK (source_type IN (1, 2)),
    CONSTRAINT ck_app_pages_status CHECK (status IN (1, 2))
);

CREATE INDEX idx_app_pages_page_key ON app_pages(page_key);
CREATE INDEX idx_app_pages_client_locale ON app_pages(client_type, locale);
CREATE INDEX idx_app_pages_status ON app_pages(status);


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
-- Backup Management Tables
-- ============================================================================

-- Backup jobs table - Database backup execution records (written by host scripts)
CREATE TABLE IF NOT EXISTS backup_jobs (
    id SERIAL PRIMARY KEY,
    status INTEGER NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    finished_at TIMESTAMP WITH TIME ZONE,
    duration_ms BIGINT,
    backup_file_name VARCHAR(255),
    object_key TEXT,
    bucket_name VARCHAR(255),
    storage_region VARCHAR(64),
    file_size BIGINT,
    sha256 CHAR(64),
    etag VARCHAR(128),
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_backup_jobs_status'
    ) THEN
        ALTER TABLE backup_jobs ADD CONSTRAINT ck_backup_jobs_status
            CHECK (status IN (1, 2, 3));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_backup_jobs_started_at ON backup_jobs(started_at);
CREATE INDEX IF NOT EXISTS idx_backup_jobs_status ON backup_jobs(status);
CREATE INDEX IF NOT EXISTS idx_backup_jobs_created_at ON backup_jobs(created_at);


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
    CONSTRAINT ck_llm_configs_thinking_mode CHECK (thinking_mode <> ''),
    CONSTRAINT ck_llm_configs_top_p CHECK (top_p >= 0 AND top_p <= 1),
    CONSTRAINT ck_llm_configs_frequency_penalty CHECK (frequency_penalty >= -2 AND frequency_penalty <= 2),
    CONSTRAINT ck_llm_configs_presence_penalty CHECK (presence_penalty >= -2 AND presence_penalty <= 2),
    CONSTRAINT ck_llm_configs_default_tool_choice CHECK (default_tool_choice <> ''),
    CONSTRAINT ck_llm_configs_max_tool_calls CHECK (max_tool_calls >= 0)
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

-- Add foreign key constraint for llm_configs
ALTER TABLE llm_configs ADD CONSTRAINT fk_llm_configs_provider
    FOREIGN KEY (provider_id) REFERENCES llm_providers(id) ON DELETE RESTRICT;

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
    ADD CONSTRAINT ck_llm_test_logs_thinking_mode CHECK (thinking_mode <> '');

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

-- ============================================================================

-- Create triggers for all tables with updated_at column
-- Drop existing triggers first to ensure idempotency
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
DROP TRIGGER IF EXISTS update_user_tokens_updated_at ON user_tokens;
DROP TRIGGER IF EXISTS update_user_auths_updated_at ON user_auths;
DROP TRIGGER IF EXISTS update_contacts_updated_at ON contacts;
DROP TRIGGER IF EXISTS update_contact_requests_updated_at ON contact_requests;
DROP TRIGGER IF EXISTS update_square_type_entries_updated_at ON square_type_entries;
DROP TRIGGER IF EXISTS update_profiles_updated_at ON profiles;
DROP TRIGGER IF EXISTS update_message_devices_updated_at ON message_devices;
DROP TRIGGER IF EXISTS update_message_endpoints_updated_at ON message_endpoints;
DROP TRIGGER IF EXISTS update_message_deliveries_updated_at ON message_deliveries;
DROP TRIGGER IF EXISTS update_message_dispatch_outbox_updated_at ON message_dispatch_outbox;
DROP TRIGGER IF EXISTS update_media_files_updated_at ON media_files;
DROP TRIGGER IF EXISTS update_ai_styles_updated_at ON ai_styles;
DROP TRIGGER IF EXISTS update_ai_relationships_updated_at ON ai_relationships;
DROP TRIGGER IF EXISTS update_ai_dimensions_updated_at ON ai_dimensions;
DROP TRIGGER IF EXISTS update_ai_style_dimensions_updated_at ON ai_style_dimensions;
DROP TRIGGER IF EXISTS update_ai_dimension_relationship_mappings_updated_at ON ai_dimension_relationship_mappings;
DROP TRIGGER IF EXISTS update_ai_personalities_updated_at ON ai_personalities;
DROP TRIGGER IF EXISTS update_ai_personality_placeholders_updated_at ON ai_personality_placeholders;
DROP TRIGGER IF EXISTS update_ai_types_updated_at ON ai_types;
DROP TRIGGER IF EXISTS update_ai_templates_updated_at ON ai_templates;
DROP TRIGGER IF EXISTS update_ai_personas_updated_at ON ai_personas;
DROP TRIGGER IF EXISTS update_ai_instances_updated_at ON ai_instances;
DROP TRIGGER IF EXISTS update_ai_conversation_state_updated_at ON ai_conversation_state;
DROP TRIGGER IF EXISTS update_ai_conversation_runtime_updated_at ON ai_conversation_runtime;
DROP TRIGGER IF EXISTS update_ai_message_buffer_updated_at ON ai_message_buffer;
DROP TRIGGER IF EXISTS update_ai_instance_dimensions_updated_at ON ai_instance_dimensions;
DROP TRIGGER IF EXISTS update_user_violation_logs_updated_at ON user_violation_logs;
DROP TRIGGER IF EXISTS update_user_risk_stats_updated_at ON user_risk_stats;
DROP TRIGGER IF EXISTS update_system_configs_updated_at ON system_configs;
DROP TRIGGER IF EXISTS update_app_pages_updated_at ON app_pages;
DROP TRIGGER IF EXISTS update_admin_users_updated_at ON admin_users;
DROP TRIGGER IF EXISTS update_backup_jobs_updated_at ON backup_jobs;
DROP TRIGGER IF EXISTS update_llm_providers_updated_at ON llm_providers;
DROP TRIGGER IF EXISTS update_llm_configs_updated_at ON llm_configs;

-- Create triggers
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_tokens_updated_at BEFORE UPDATE ON user_tokens FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_auths_updated_at BEFORE UPDATE ON user_auths FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_contacts_updated_at BEFORE UPDATE ON contacts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_contact_requests_updated_at BEFORE UPDATE ON contact_requests FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_square_type_entries_updated_at BEFORE UPDATE ON square_type_entries FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE ON profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_message_devices_updated_at BEFORE UPDATE ON message_devices FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_message_endpoints_updated_at BEFORE UPDATE ON message_endpoints FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_message_deliveries_updated_at BEFORE UPDATE ON message_deliveries FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_message_dispatch_outbox_updated_at BEFORE UPDATE ON message_dispatch_outbox FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_media_files_updated_at BEFORE UPDATE ON media_files FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_styles_updated_at BEFORE UPDATE ON ai_styles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_relationships_updated_at BEFORE UPDATE ON ai_relationships FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_dimensions_updated_at BEFORE UPDATE ON ai_dimensions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_style_dimensions_updated_at BEFORE UPDATE ON ai_style_dimensions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_dimension_relationship_mappings_updated_at BEFORE UPDATE ON ai_dimension_relationship_mappings FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_personalities_updated_at BEFORE UPDATE ON ai_personalities FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_personality_placeholders_updated_at BEFORE UPDATE ON ai_personality_placeholders FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_types_updated_at BEFORE UPDATE ON ai_types FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_templates_updated_at BEFORE UPDATE ON ai_templates FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_personas_updated_at BEFORE UPDATE ON ai_personas FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_instances_updated_at BEFORE UPDATE ON ai_instances FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_conversation_state_updated_at BEFORE UPDATE ON ai_conversation_state FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_conversation_runtime_updated_at BEFORE UPDATE ON ai_conversation_runtime FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_message_buffer_updated_at BEFORE UPDATE ON ai_message_buffer FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_instance_dimensions_updated_at BEFORE UPDATE ON ai_instance_dimensions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_violation_logs_updated_at BEFORE UPDATE ON user_violation_logs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_risk_stats_updated_at BEFORE UPDATE ON user_risk_stats FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_system_configs_updated_at BEFORE UPDATE ON system_configs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_app_pages_updated_at BEFORE UPDATE ON app_pages FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_admin_users_updated_at BEFORE UPDATE ON admin_users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_backup_jobs_updated_at BEFORE UPDATE ON backup_jobs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
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
