-- Required System Data - Test Environment
-- This file contains essential data required for the system to function
-- Must be loaded after schema initialization

-- Set timezone and encoding
SET timezone = 'UTC';
SET client_encoding = 'UTF8';

-- Success message for data loading start
DO $$
BEGIN
    RAISE NOTICE 'Loading required system data for TEST environment...';
END $$;

-- ============================================================================
-- Admin Users
-- ============================================================================

-- Insert default admin users
INSERT INTO admin_users (username, password_hash, role, status) VALUES
-- password: FXTa2ocgN3Evtc
('admin', '$2b$12$Lw0l4K8pffx8OAVU2lHTpeWv5MnsJyigJS4uDpbk4Q3n/h8OiUBUi', 1, 1),

-- password: eU2L8nRj87huRB
('manager', '$2b$12$AiMJcQZazxIpyaLl4R7kqOxI/g1UiFXmz6JVgy6jQTJz7fttrRtaO', 2, 1),

-- password: pKKKs8O1cxQznU
('viewer', '$2b$12$SisP2jdksO3FfhMQmraOj.OEmH17vmRXLdDeiBIjZJ2kbbgxqx8NG', 3, 1)
ON CONFLICT (username) DO NOTHING;

-- ============================================================================
-- System Configuration
-- ============================================================================

-- Insert default system configuration
INSERT INTO system_configs (config_key, config_value, default_value, config_type, description, group_name, allowed_values) VALUES
-- Business configurations
('default_contact_limit', '3', '3', 2, 'Default contact limit per user', 'business', NULL),
('contact_request_expiration', '259200', '259200', 2, 'Contact request expiration time (72 hours, in seconds)', 'business', NULL),
('square_page_size', '20', '20', 2, 'Square page size (items per page)', 'business', NULL),
('max_message_length', '49', '49', 2, 'Maximum message length in characters', 'business', NULL),

-- Authentication configurations
('jwt_token_expires_in', '1209600', '1209600', 2, 'JWT token expiration time in seconds (14 days)', 'auth', NULL),
('jwt_sliding_window', '604800', '604800', 2, 'JWT sliding window threshold in seconds (7 days, auto-renew if < this)', 'auth', NULL),
('jwt_algorithm', 'HS256', 'HS256', 1, 'JWT signing algorithm', 'auth', NULL),
('token_max_active_per_device', '1', '1', 2, 'Maximum active tokens per device type', 'auth', NULL),
('token_cleanup_after', '2592000', '2592000', 2, 'Clean up revoked tokens older than N seconds (30 days)', 'auth', NULL),

-- LeanCloud configurations
('leancloud_app_id', 'KTrHvz9TVtSZX1fhIuVanHhH-gzGzoHsz', '', 1, 'LeanCloud App ID', 'leancloud', NULL),
('leancloud_app_key', 'aBJfaLAFnVl1mna2hQ7jsff0', '', 1, 'LeanCloud App Key', 'leancloud', NULL),
('leancloud_base_url', 'https://ktrhvz9t.lc-cn-n1-shared.com', '', 1, 'LeanCloud Base URL', 'leancloud', NULL),
('leancloud_service_conversation_id', '', '', 1, 'LeanCloud system conversation ID for message routing', 'leancloud', NULL),
('leancloud_webhook_token', '', '', 1, 'Webhook security token for LeanCloud message callbacks (24-character URL-safe string)', 'leancloud', NULL),
('api_base_url', '', '', 1, 'Base URL for API (e.g., https://example.com)', 'system', NULL),

-- Message buffer configurations
('message_buffer_normal_wait', '3000', '3000', 2, 'Normal wait time in milliseconds for message buffering', 'message_buffer', NULL),
('message_buffer_typing_wait', '10000', '10000', 2, 'Long wait time in milliseconds when user is typing', 'message_buffer', NULL),
('message_buffer_typing_end_wait', '1000', '1000', 2, 'Short wait time in milliseconds after typing ends', 'message_buffer', NULL),
('message_buffer_no_typing_wait', '2000', '2000', 2, 'Wait time in milliseconds for clients without typing support', 'message_buffer', NULL),

-- AI context archive configurations
('ai_context_archive_time', '604800', '604800', 2, 'Archive AI contexts older than this many seconds (7 days)', 'ai_context', NULL),
('ai_context_archive_max_count', '50', '50', 2, 'Archive AI contexts when count exceeds this limit', 'ai_context', NULL),
('ai_context_archive_min_count', '10', '10', 2, 'Minimum contexts to keep, do not archive if below this count', 'ai_context', NULL),
('ai_context_archive_threshold', '80', '80', 2, 'Trigger immediate archive when count exceeds this threshold', 'ai_context', NULL),

-- API rate limit configuration
('api_rate_limit_requests', '100', '100', 2, 'API requests per window', 'rate_limit', NULL),
('api_rate_limit_window', '60', '60', 2, 'API window (seconds)', 'rate_limit', NULL),
('api_whitelist', '', '', 1, 'API whitelist IPs (comma separated)', 'rate_limit', NULL),

-- Admin authentication rate limit and security
('admin_auth_rate_limit_requests', '30', '30', 2, 'Admin auth requests per window', 'rate_limit', NULL),
('admin_auth_rate_limit_window', '60', '60', 2, 'Admin auth window (seconds)', 'rate_limit', NULL),
('admin_auth_max_failures', '10', '10', 2, 'Max admin failures before lockout', 'security', NULL),
('admin_auth_lockout_duration', '1800', '1800', 2, 'Admin lockout duration (seconds)', 'security', NULL),
('admin_auth_whitelist', '', '', 1, 'Admin whitelist IPs (comma separated)', 'security', NULL),

-- User authentication rate limit and security
('auth_rate_limit_requests', '10', '10', 2, 'User auth requests per window', 'rate_limit', NULL),
('auth_rate_limit_window', '3600', '3600', 2, 'User auth window (seconds)', 'rate_limit', NULL),
('auth_max_failures', '5', '5', 2, 'Max user failures before lockout', 'security', NULL),
('auth_lockout_duration', '900', '900', 2, 'User lockout duration (seconds)', 'security', NULL),

-- SMS rate limit configuration
('sms_rate_limit_requests', '1', '1', 2, 'SMS requests per window', 'rate_limit', NULL),
('sms_rate_limit_window', '60', '60', 2, 'SMS window (seconds)', 'rate_limit', NULL),
('sms_whitelist', '', '', 1, 'SMS whitelist phones (comma separated)', 'rate_limit', NULL),

-- SMS provider configuration
('sms_provider', 'mock', 'mock', 1, 'SMS provider', 'sms', '["mock"]'::jsonb),
('sms_code_expires_in', '300', '300', 2, 'SMS code expiration time in seconds', 'sms', NULL),
('sms_code_length', '6', '6', 2, 'SMS code length', 'sms', NULL),

-- Admin CAPTCHA configuration
('admin_captcha_provider', 'turnstile', 'turnstile', 5, 'Admin captcha provider', 'captcha', '["none","turnstile","aliyun"]'::jsonb),
('admin_captcha_threshold', '1', '1', 2, 'Admin captcha trigger threshold (failures)', 'captcha', NULL),
('admin_captcha_mode', 'strict', 'strict', 5, 'Admin CAPTCHA verification mode: strict (block on any error) or fallback (allow on service errors)', 'captcha', '["strict", "fallback"]'::jsonb),
('admin_turnstile_site_key', '0x4AAAAAAB4mlG1QV6muTpRg', '1x00000000000000000000AA', 1, 'Admin Turnstile site key', 'captcha', NULL),
('admin_turnstile_secret_key', '0x4AAAAAAB4mlLtoJ7O9ObSXGAadbdhA3bA', '1x0000000000000000000000000000000AA', 1, 'Admin Turnstile secret key', 'captcha', NULL),

-- User CAPTCHA configuration
('wxminipg_captcha_provider', 'aliyun', 'none', 5, 'User captcha provider', 'captcha', '["none","turnstile","aliyun"]'::jsonb),
('captcha_threshold', '3', '3', 2, 'User captcha trigger threshold (failures)', 'captcha', NULL),
('turnstile_site_key', '', '1x00000000000000000000AA', 1, 'User Turnstile site key', 'captcha', NULL),
('turnstile_secret_key', '', '1x0000000000000000000000000000000AA', 1, 'User Turnstile secret key', 'captcha', NULL),
('wxminipg_aliyun_captcha_scene_id', '', '', 1, 'Aliyun Captcha SceneId for user verification', 'captcha', NULL),

-- Message rate limit configuration
('message_rate_limit_short_requests', '5', '5', 2, 'Max messages per short window', 'rate_limit', NULL),
('message_rate_limit_short_window', '10', '10', 2, 'Short window (seconds)', 'rate_limit', NULL),
('message_rate_limit_long_requests', '20', '20', 2, 'Max messages per long window', 'rate_limit', NULL),
('message_rate_limit_long_window', '60', '60', 2, 'Long window (seconds)', 'rate_limit', NULL),

-- Square rate limit configuration
('square_rate_limit_requests', '1', '1', 2, 'Square refresh requests per window', 'rate_limit', NULL),
('square_rate_limit_window', '10', '10', 2, 'Square refresh window (seconds)', 'rate_limit', NULL)
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
INSERT INTO llm_configs (provider_id, name, model_name, temperature, max_tokens, timeout_seconds, max_retries, enable_streaming, enable_thinking, json_schema_mode, status, priority) VALUES
(1, 'advanced', 'ep-20250619205554-wwsr7', 0.7, 4000, 30, 3, 1, 0, 'strict', 1, 1),
(2, 'mock', 'mock-model-v1', 0.7, 2000, 5, 0, 0, 0, 'strict', 1, 999)
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- Data Loading Complete
-- ============================================================================

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Required system data loaded successfully for TEST environment!';
    RAISE NOTICE 'Admin users, system configs, and LLM configurations have been initialized.';
END $$;
