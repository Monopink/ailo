-- Required System Data - Production Environment
-- This file contains essential data required for the system to function
-- Must be loaded after schema initialization

-- Set timezone and encoding
SET timezone = 'UTC';
SET client_encoding = 'UTF8';

-- Success message for data loading start
DO $$
BEGIN
    RAISE NOTICE 'Loading required system data for PRODUCTION environment...';
END $$;

-- ============================================================================
-- Admin Users
-- ============================================================================

-- IMPORTANT: Change admin password after first login in production!
-- Insert default admin users (password: 3JLvy06YUlKJ5r)
INSERT INTO admin_users (username, password_hash, role, status) VALUES
('admin', '$2b$12$dmJKVzwwpvXf.Xy2fmmRgOzR1svv.Eyvzahv8KDvDp9I2ESqMUW02', 1, 1)
ON CONFLICT (username) DO NOTHING;

-- ============================================================================
-- System Configuration
-- ============================================================================

-- Insert default system configuration
INSERT INTO system_configs (config_key, config_value, default_value, config_type, description, group_name, allowed_values) VALUES
-- Business configurations
('default_contact_limit', '3', '3', 2, 'Default contact limit per user', 'business', NULL),
('contact_request_expiration_days', '3', '3', 2, 'Contact request expiration time in days (default: 3 days)', 'business', NULL),
('square_page_size', '20', '20', 2, 'Square page size (items per page)', 'business', NULL),
('max_message_length_chars', '49', '49', 2, 'Maximum message length in characters', 'business', NULL),

-- Authentication configurations
('jwt_token_expires_in_days', '14', '14', 2, 'JWT token expiration time in days', 'auth', NULL),
('jwt_sliding_window_days', '7', '7', 2, 'JWT sliding window threshold in days (auto-renew if < this)', 'auth', NULL),
('jwt_algorithm', 'HS256', 'HS256', 1, 'JWT signing algorithm', 'auth', NULL),
('token_max_active_per_device', '1', '1', 2, 'Maximum active tokens per device type', 'auth', NULL),
('token_cleanup_after_days', '30', '30', 2, 'Clean up revoked tokens older than N days', 'auth', NULL),
('wechat_phone_mock_enabled', 'false', 'false', 3, 'Enable WeChat phone mock (non-production environments only)', 'auth', NULL),
('wechat_phone_mock_number', '', '', 1, 'Mock phone number for WeChat virtual accounts (E.164 format)', 'auth', NULL),
('username_reserved_words', '["admin","root","system","support","operator","moderator","service","official","help","security"]', '["admin","root","system","support","operator","moderator","service","official","help","security"]', 4, 'Reserved usernames (lowercase), JSON array', 'auth', NULL),

-- LeanCloud IM configurations (must be configured via admin dashboard)
('leancloud_im_app_id', '', '', 1, 'LeanCloud IM App ID', 'leancloud', NULL),
('leancloud_im_app_key', '', '', 1, 'LeanCloud IM App Key', 'leancloud', NULL),
('leancloud_im_server_url', '', '', 1, 'LeanCloud IM server URL', 'leancloud', NULL),
('leancloud_im_service_conversation_id', '', '', 1, 'LeanCloud IM system conversation ID for message routing', 'leancloud', NULL),
('leancloud_im_webhook_token', '', '', 1, 'LeanCloud IM webhook security token (24-character URL-safe string)', 'leancloud', NULL),
('api_base_url', '', '', 1, 'Base URL for API (e.g., https://example.com)', 'system', NULL),
('media_public_base_url', '', '', 1, 'Authoritative public base URL for serving media files (CDN or COS bucket domain)', 'media', NULL),

-- Message buffer configurations
('message_buffer_normal_wait_ms', '3000', '3000', 2, 'Normal wait time in milliseconds for message buffering', 'message_buffer', NULL),
('message_buffer_typing_short_wait_ms', '16000', '16000', 2, 'Typing short wait in milliseconds after typing_start', 'message_buffer', NULL),
('message_buffer_typing_total_wait_ms', '32000', '32000', 2, 'Typing session total wait in milliseconds after typing_start', 'message_buffer', NULL),
('message_buffer_typing_end_wait_ms', '3000', '3000', 2, 'Short wait time in milliseconds after typing ends', 'message_buffer', NULL),
('message_buffer_no_typing_wait_ms', '8000', '8000', 2, 'Wait time in milliseconds for clients without typing support', 'message_buffer', NULL),

-- Message transport configurations
('ws_presence_lease_ttl_seconds', '90', '90', 2, 'WebSocket presence lease TTL in seconds', 'message_transport', NULL),
('ws_ping_interval_seconds', '25', '25', 2, 'WebSocket client ping interval in seconds', 'message_transport', NULL),
('registration_lease_ttl_days', '365', '365', 2, 'Registration lease TTL in days (e.g., LeanCloud installation binding)', 'message_transport', NULL),

-- AI conversation archive configurations (values in seconds unless otherwise noted)
('ai_conversation_archive_time_days', '7', '7', 2, 'Archive AI conversation items older than this many days', 'ai_conversation', NULL),
('ai_conversation_archive_max_count', '50', '50', 2, 'Archive AI conversation items when count exceeds this limit', 'ai_conversation', NULL),
('ai_conversation_archive_min_count', '10', '10', 2, 'Minimum AI conversation items to keep; do not archive if below this count', 'ai_conversation', NULL),
('ai_conversation_archive_threshold', '80', '80', 2, 'Trigger immediate archive when AI conversation items exceed this threshold', 'ai_conversation', NULL),

-- API rate limit configuration
('api_rate_limit_requests', '100', '100', 2, 'API requests per window', 'rate_limit', NULL),
('api_rate_limit_window_seconds', '60', '60', 2, 'API window in seconds', 'rate_limit', NULL),
('api_whitelist', '', '', 1, 'API whitelist IPs (comma separated)', 'rate_limit', NULL),

-- Admin authentication rate limit and security
('admin_auth_rate_limit_requests', '20', '20', 2, 'Admin auth requests per window', 'rate_limit', NULL),
('admin_auth_rate_limit_window_seconds', '60', '60', 2, 'Admin auth window in seconds', 'rate_limit', NULL),
('admin_auth_max_failures', '5', '5', 2, 'Max admin failures before lockout', 'security', NULL),
('admin_auth_lockout_duration_minutes', '60', '60', 2, 'Admin lockout duration in minutes', 'security', NULL),
('admin_auth_whitelist', '', '', 1, 'Admin whitelist IPs (comma separated)', 'security', NULL),

-- User authentication rate limit and security
('auth_password_rate_limit_short_requests', '3', '5', 2, 'Password login short-window requests (per ip+identifier)', 'rate_limit', NULL),
('auth_password_rate_limit_short_window_seconds', '10', '10', 2, 'Password login short window in seconds', 'rate_limit', NULL),
('auth_password_rate_limit_long_requests', '10', '20', 2, 'Password login long-window requests (per ip+identifier)', 'rate_limit', NULL),
('auth_password_rate_limit_long_window_seconds', '60', '60', 2, 'Password login long window in seconds', 'rate_limit', NULL),
('auth_password_max_failures', '3', '5', 2, 'Password login max failures before lockout (per ip+identifier)', 'security', NULL),
('auth_password_failure_window_seconds', '1800', '1800', 2, 'Password login failure counting window in seconds', 'security', NULL),
('auth_password_lockout_duration_seconds', '1800', '900', 2, 'Password login lockout duration in seconds', 'security', NULL),

-- Username rate limit configuration
('username_check_rate_limit_short_requests', '5', '5', 2, 'Username check short-window requests (per user)', 'rate_limit', NULL),
('username_check_rate_limit_short_window_seconds', '10', '10', 2, 'Username check short window in seconds', 'rate_limit', NULL),
('username_check_rate_limit_long_requests', '20', '20', 2, 'Username check long-window requests (per user)', 'rate_limit', NULL),
('username_check_rate_limit_long_window_seconds', '60', '60', 2, 'Username check long window in seconds', 'rate_limit', NULL),
('username_submit_rate_limit_requests', '3', '3', 2, 'Username submit requests (per user)', 'rate_limit', NULL),
('username_submit_rate_limit_window_seconds', '60', '60', 2, 'Username submit window in seconds', 'rate_limit', NULL),

-- SMS rate limit configuration
('sms_rate_limit_requests', '1', '1', 2, 'SMS requests per window', 'rate_limit', NULL),
('sms_rate_limit_window_seconds', '60', '60', 2, 'SMS window in seconds', 'rate_limit', NULL),
('sms_whitelist', '', '', 1, 'SMS whitelist phones (comma separated)', 'rate_limit', NULL),

-- SMS provider configuration (must be configured via admin dashboard)
('sms_provider', 'mock', 'mock', 1, 'SMS provider', 'sms', '["mock"]'::jsonb),
('sms_code_expires_in_seconds', '300', '300', 2, 'SMS code expiration time in seconds', 'sms', NULL),
('sms_code_length_digits', '6', '6', 2, 'SMS code length in digits', 'sms', NULL),

-- Admin CAPTCHA configuration
('admin_captcha_provider', 'turnstile', 'turnstile', 5, 'Admin captcha provider', 'captcha', '["none","turnstile"]'::jsonb),
('admin_captcha_threshold_failures', '1', '1', 2, 'Admin captcha trigger threshold (failures)', 'captcha', NULL),
('admin_captcha_mode', 'strict', 'strict', 5, 'Admin CAPTCHA verification mode: strict (block on any error) or fallback (allow on service errors)', 'captcha', '["strict", "fallback"]'::jsonb),
('admin_turnstile_site_key', '', '1x00000000000000000000AA', 1, 'Admin Turnstile site key', 'captcha', NULL),
('admin_turnstile_secret_key', '', '1x0000000000000000000000000000000AA', 1, 'Admin Turnstile secret key', 'captcha', NULL),

-- User CAPTCHA configuration
('captcha_threshold_failures', '3', '3', 2, 'User captcha trigger threshold (failures)', 'captcha', NULL),

-- Message rate limit configuration
('message_rate_limit_short_requests', '5', '5', 2, 'Max messages per short window', 'rate_limit', NULL),
('message_rate_limit_short_window_seconds', '10', '10', 2, 'Short window in seconds', 'rate_limit', NULL),
('message_rate_limit_long_requests', '20', '20', 2, 'Max messages per long window', 'rate_limit', NULL),
('message_rate_limit_long_window_seconds', '60', '60', 2, 'Long window in seconds', 'rate_limit', NULL),

-- Square rate limit configuration
('square_rate_limit_requests', '1', '1', 2, 'Square refresh requests per window', 'rate_limit', NULL),
('square_rate_limit_window_seconds', '10', '10', 2, 'Square refresh window in seconds', 'rate_limit', NULL),

-- Media upload configuration
('avatar_max_size_mb', '2', '2', 2, 'Maximum avatar file size in MB', 'media', NULL),
('avatar_allowed_formats', 'image/jpeg,image/png,image/webp', 'image/jpeg,image/png,image/webp', 1, 'Allowed avatar MIME types (comma-separated)', 'media', NULL),
('image_max_size_mb', '10', '10', 2, 'Maximum image file size in MB', 'media', NULL),
('image_allowed_formats', 'image/jpeg,image/png,image/webp,image/gif', 'image/jpeg,image/png,image/webp,image/gif', 1, 'Allowed image MIME types (comma-separated)', 'media', NULL),

-- Media upload quota configuration (✅ MVP P0)
('avatar_upload_daily_quota', '5', '5', 2, 'Maximum avatar uploads per user per day', 'media', NULL),
('avatar_upload_daily_size_quota_mb', '10', '10', 2, 'Maximum total avatar upload size per user per day (MB)', 'media', NULL),
('image_upload_daily_quota', '20', '20', 2, 'Maximum image uploads per user per day', 'media', NULL),
('image_upload_daily_size_quota_mb', '50', '50', 2, 'Maximum total image upload size per user per day (MB)', 'media', NULL),

-- Media upload rate limit configuration
('media_upload_rate_limit_requests', '10', '10', 2, 'Media upload requests per window', 'rate_limit', NULL),
('media_upload_rate_limit_window_seconds', '60', '60', 2, 'Media upload window in seconds', 'rate_limit', NULL)
ON CONFLICT (config_key) DO UPDATE SET
    config_value = EXCLUDED.config_value,
    default_value = EXCLUDED.default_value,
    config_type = EXCLUDED.config_type,
    description = EXCLUDED.description,
    group_name = EXCLUDED.group_name,
    allowed_values = EXCLUDED.allowed_values;

-- ============================================================================
-- Template Types Baseline
-- ============================================================================

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
    RAISE NOTICE 'Required system data loaded successfully for PRODUCTION environment!';
    RAISE NOTICE 'Admin users, system configs, and LLM configurations have been initialized.';
    RAISE NOTICE 'IMPORTANT: Change admin password and configure third-party services via admin dashboard!';
END $$;
