-- Required System Data - Development Environment
-- This file contains essential data required for the system to function
-- Must be loaded after schema initialization

-- Set timezone and encoding
SET timezone = 'UTC';
SET client_encoding = 'UTF8';

-- Success message for data loading start
DO $$
BEGIN
    RAISE NOTICE 'Loading required system data for DEVELOPMENT environment...';
END $$;

-- ============================================================================
-- Admin Users
-- ============================================================================

-- Insert default admin users (password: admin123)
INSERT INTO admin_users (username, password_hash, role, status) VALUES
('admin', '$2b$12$i4kzuJnXuIQdxS3GgFXOh.JhvEjMntTakeqw4QKXah2zCpXpbwlJi', 1, 1),
('manager', '$2b$12$i4kzuJnXuIQdxS3GgFXOh.JhvEjMntTakeqw4QKXah2zCpXpbwlJi', 2, 1),
('viewer', '$2b$12$i4kzuJnXuIQdxS3GgFXOh.JhvEjMntTakeqw4QKXah2zCpXpbwlJi', 3, 1)
ON CONFLICT (username) DO NOTHING;

-- ============================================================================
-- System Configuration
-- ============================================================================
--
-- IMPORTANT: All config_key values MUST follow the naming convention
-- See: docs/spec/system-configs/naming.md
--
-- Insert default system configuration
INSERT INTO system_configs (config_key, config_value, default_value, config_type, description, group_name, allowed_values) VALUES
-- Contacts configurations
('default_contact_limit', '10', '3', 2, 'Default contact limit per user', 'contacts', NULL),
('contact_request_expiration_days', '3', '3', 2, 'Contact request expiration time in days (default: 3 days)', 'contacts', NULL),

-- Discovery configurations
('square_page_size', '20', '20', 2, 'Square page size (items per page)', 'discovery_square', NULL),

-- Messaging configurations
('max_message_length_chars', '49', '49', 2, 'Maximum message length in characters', 'messaging', NULL),

-- Authentication configurations
('jwt_token_expires_in_days', '14', '14', 2, 'JWT token expiration time in days', 'auth', NULL),
('refresh_token_expires_in_days', '90', '90', 2, 'Refresh token expiration time in days', 'auth', NULL),
('wechat_phone_mock_enabled', 'false', 'false', 3, 'Enable WeChat phone mock (non-production environments only)', 'auth', NULL),
('wechat_phone_mock_number', '', '', 1, 'Mock phone number for WeChat virtual accounts (E.164 format)', 'auth', NULL),

-- Username configurations
('username_reserved_words', '["admin","root","system","support","operator","moderator","service","official","help","security"]', '["admin","root","system","support","operator","moderator","service","official","help","security"]', 4, 'Reserved usernames (lowercase), JSON array', 'username', NULL),

-- LeanCloud IM configurations
('leancloud_im_server_url', 'https://zcuk19lc.lc-cn-n1-shared.com', '', 1, 'LeanCloud IM server URL', 'im_leancloud', NULL),
('leancloud_im_service_conversation_id', '', '', 1, 'LeanCloud IM system conversation ID for message routing', 'im_leancloud', NULL),
('leancloud_im_webhook_token', '', '', 1, 'LeanCloud IM webhook security token (24-character URL-safe string)', 'im_leancloud', NULL),

-- API configurations
('api_base_url', 'http://localhost:8000', 'http://localhost:8000', 1, 'Base URL for API (e.g., https://example.com)', 'api', NULL),

-- Media configurations
('media_public_base_url', '', '', 1, 'Authoritative public base URL for serving media files (CDN or COS bucket domain)', 'media', NULL),

-- Message buffer configurations
('message_buffer_normal_wait_ms', '3000', '3000', 2, 'Normal wait time in milliseconds for message buffering', 'messaging', NULL),
('message_buffer_typing_short_wait_ms', '16000', '16000', 2, 'Typing short wait in milliseconds after typing_start', 'messaging', NULL),
('message_buffer_typing_total_wait_ms', '32000', '32000', 2, 'Typing session total wait in milliseconds after typing_start', 'messaging', NULL),
('message_buffer_typing_end_wait_ms', '3000', '3000', 2, 'Short wait time in milliseconds after typing ends', 'messaging', NULL),
('message_buffer_no_typing_wait_ms', '8000', '8000', 2, 'Wait time in milliseconds for clients without typing support', 'messaging', NULL),

-- AI conversation archive configurations (values in seconds unless otherwise noted)
('ai_conversation_archive_time_days', '7', '7', 2, 'Archive AI conversation items older than this many days', 'ai_conversation', NULL),
('ai_conversation_archive_max_count', '50', '50', 2, 'Archive AI conversation items when count exceeds this limit', 'ai_conversation', NULL),
('ai_conversation_archive_min_count', '10', '10', 2, 'Minimum AI conversation items to keep; do not archive if below this count', 'ai_conversation', NULL),
('ai_conversation_archive_threshold', '80', '80', 2, 'Trigger immediate archive when AI conversation items exceed this threshold', 'ai_conversation', NULL),
('ai_llm_min_contract_retry_enabled', 'true', 'true', 3, 'Enable minimal-contract retry for AI LLM responses', 'ai_conversation', NULL),
('ai_llm_min_contract_retry_max_attempts', '3', '3', 2, 'Maximum attempts for minimal-contract retry (>=1)', 'ai_conversation', NULL),
('ai_llm_min_contract_retry_backoff_ms', '300', '300', 2, 'Fixed backoff interval in milliseconds for minimal-contract retry (>=0)', 'ai_conversation', NULL),

-- Alerting configurations
('alerting_cleanup_enabled', 'true', 'true', 3, 'Enable alert_events cleanup worker', 'alerting', NULL),
('alerting_cleanup_interval_seconds', '3600', '3600', 2, 'Cleanup interval in seconds for alert_events (>=1)', 'alerting', NULL),
('alerting_default_retention_days', '30', '30', 2, 'Default retention days for alert_events (>=0)', 'alerting', NULL),

-- API rate limit configuration
('api_rate_limit_requests', '1000', '100', 2, 'API requests per window', 'api', NULL),
('api_rate_limit_window_seconds', '60', '60', 2, 'API window in seconds', 'api', NULL),

-- Admin authentication rate limit and security
('admin_auth_rate_limit_requests', '100', '30', 2, 'Admin auth requests per window', 'admin_auth', NULL),
('admin_auth_rate_limit_window_seconds', '60', '60', 2, 'Admin auth window in seconds', 'admin_auth', NULL),
('admin_auth_max_failures', '100', '10', 2, 'Max admin failures before lockout', 'admin_auth', NULL),
('admin_auth_lockout_duration_minutes', '5', '30', 2, 'Admin lockout duration in minutes', 'admin_auth', NULL),
('admin_auth_whitelist', '127.0.0.1,::1', '127.0.0.1,::1', 1, 'Admin whitelist IPs (comma separated)', 'admin_auth', NULL),

-- User authentication rate limit and security
('auth_password_rate_limit_short_requests', '10', '5', 2, 'Password login short-window requests (per ip+identifier)', 'auth_password', NULL),
('auth_password_rate_limit_short_window_seconds', '10', '10', 2, 'Password login short window in seconds', 'auth_password', NULL),
('auth_password_rate_limit_long_requests', '50', '20', 2, 'Password login long-window requests (per ip+identifier)', 'auth_password', NULL),
('auth_password_rate_limit_long_window_seconds', '60', '60', 2, 'Password login long window in seconds', 'auth_password', NULL),
('auth_password_max_failures', '10', '5', 2, 'Password login max failures before lockout (per ip+identifier)', 'auth_password', NULL),
('auth_password_failure_window_seconds', '3600', '1800', 2, 'Password login failure counting window in seconds', 'auth_password', NULL),
('auth_password_lockout_duration_seconds', '300', '900', 2, 'Password login lockout duration in seconds', 'auth_password', NULL),

-- Username rate limit configuration
('username_check_rate_limit_short_requests', '5', '5', 2, 'Username check short-window requests (per user)', 'username', NULL),
('username_check_rate_limit_short_window_seconds', '10', '10', 2, 'Username check short window in seconds', 'username', NULL),
('username_check_rate_limit_long_requests', '20', '20', 2, 'Username check long-window requests (per user)', 'username', NULL),
('username_check_rate_limit_long_window_seconds', '60', '60', 2, 'Username check long window in seconds', 'username', NULL),
('username_submit_rate_limit_requests', '3', '3', 2, 'Username submit requests (per user)', 'username', NULL),
('username_submit_rate_limit_window_seconds', '60', '60', 2, 'Username submit window in seconds', 'username', NULL),

-- SMS rate limit configuration
('sms_rate_limit_requests', '10', '1', 2, 'SMS requests per window', 'sms', NULL),
('sms_rate_limit_window_seconds', '60', '60', 2, 'SMS window in seconds', 'sms', NULL),
('sms_whitelist', '', '', 1, 'SMS whitelist phones (comma separated)', 'sms', NULL),

-- SMS provider configuration
('sms_provider', 'mock', 'mock', 1, 'SMS provider', 'sms', '["mock"]'::jsonb),
('sms_code_expires_in_seconds', '300', '300', 2, 'SMS code expiration time in seconds', 'sms', NULL),

-- Admin CAPTCHA configuration
('admin_captcha_provider', 'turnstile', 'turnstile', 5, 'Admin captcha provider', 'admin_auth', '["none","turnstile"]'::jsonb),
('admin_captcha_threshold_failures', '1', '1', 2, 'Admin captcha trigger threshold (failures)', 'admin_auth', NULL),
('admin_captcha_mode', 'fallback', 'strict', 5, 'Admin CAPTCHA verification mode: strict (block on any error) or fallback (allow on service errors)', 'admin_auth', '["strict", "fallback"]'::jsonb),

-- Message rate limit configuration
('message_rate_limit_short_requests', '5', '5', 2, 'Max messages per short window', 'messaging', NULL),
('message_rate_limit_short_window_seconds', '10', '10', 2, 'Short window in seconds', 'messaging', NULL),
('message_rate_limit_long_requests', '20', '20', 2, 'Max messages per long window', 'messaging', NULL),
('message_rate_limit_long_window_seconds', '60', '60', 2, 'Long window in seconds', 'messaging', NULL),

-- Square rate limit configuration
('square_rate_limit_requests', '1', '1', 2, 'Square refresh requests per window', 'discovery_square', NULL),
('square_rate_limit_window_seconds', '10', '10', 2, 'Square refresh window in seconds', 'discovery_square', NULL),

-- Media upload configuration
('avatar_max_size_mb', '2', '2', 2, 'Maximum avatar file size in MB', 'media', NULL),
('avatar_allowed_formats', 'image/jpeg,image/png,image/webp', 'image/jpeg,image/png,image/webp', 1, 'Allowed avatar MIME types (comma-separated)', 'media', NULL),

-- Media upload quota configuration (✅ MVP P0)
('avatar_upload_daily_quota', '5', '5', 2, 'Maximum avatar uploads per user per day', 'media', NULL),
('avatar_upload_daily_size_quota_mb', '10', '10', 2, 'Maximum total avatar upload size per user per day (MB)', 'media', NULL),

-- Media upload rate limit configuration
('media_upload_rate_limit_requests', '10', '10', 2, 'Media upload requests per window', 'media', NULL),
('media_upload_rate_limit_window_seconds', '60', '60', 2, 'Media upload window in seconds', 'media', NULL)
ON CONFLICT (config_key) DO UPDATE SET
    config_value = EXCLUDED.config_value,
    default_value = EXCLUDED.default_value,
    config_type = EXCLUDED.config_type,
    description = EXCLUDED.description,
    group_name = EXCLUDED.group_name,
    allowed_values = EXCLUDED.allowed_values;


-- ============================================================================
-- LLM Providers and Configurations
-- ============================================================================

-- Insert basic LLM providers
INSERT INTO llm_providers (id, name, display_name, api_key_env, base_url, default_model, supports_streaming, supports_json_schema, supports_thinking) VALUES
(1, 'doubao', 'Doubao Production', 'DOUBAO_API_KEY', 'https://ark.cn-beijing.volces.com/api/v3', 'doubao-seed-1-6-250615', 1, 1, 1),
(2, 'mock', 'Mock LLM (Testing)', NULL, NULL, 'mock-model-v1', 0, 1, 0)
ON CONFLICT (display_name) DO UPDATE SET
    name = EXCLUDED.name,
    api_key_env = EXCLUDED.api_key_env,
    base_url = EXCLUDED.base_url,
    default_model = EXCLUDED.default_model,
    supports_streaming = EXCLUDED.supports_streaming,
    supports_json_schema = EXCLUDED.supports_json_schema,
    supports_thinking = EXCLUDED.supports_thinking,
    updated_at = NOW();

-- Insert basic LLM configs
INSERT INTO llm_configs (
    provider_id,
    name,
    model_name,
    temperature,
    max_tokens,
    timeout_seconds,
    thinking_mode,
    top_p,
    frequency_penalty,
    presence_penalty,
    stop_sequences,
    json_schema_mode,
    status,
    priority,
    extra_params
) VALUES
(1, 'advanced', 'ep-20250619205554-wwsr7', 0.7, 4000, 30, 'disabled', 0.70, 0.00, 0.00, '[]'::jsonb, 'strict', 1, 1, '{"memory_limits": {"core": 30, "recent": 50}}'::jsonb),
(2, 'mock', 'mock-model-v1', 0.7, 2000, 5, 'disabled', 0.70, 0.00, 0.00, '[]'::jsonb, 'strict', 1, 999, '{"memory_limits": {"core": 30, "recent": 50}}'::jsonb)
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- Data Loading Complete
-- ============================================================================

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Required system data loaded successfully for DEVELOPMENT environment!';
    RAISE NOTICE 'Admin users, system configs, and LLM configurations have been initialized.';
END $$;
