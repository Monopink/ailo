-- Required System Data - Shared Baseline
-- This file contains essential data required for the system to function
-- Must be loaded after schema initialization

-- Set timezone and encoding
SET timezone = 'UTC';
SET client_encoding = 'UTF8';

-- Success message for data loading start
DO $$
BEGIN
    RAISE NOTICE 'Loading required system data for SHARED baseline...';
END $$;

-- ============================================================================
-- System Configuration
-- ============================================================================
--
-- IMPORTANT: All config_key values MUST follow the naming convention
-- See: docs/spec/system-configs/naming.md
--
-- Insert default system configuration
INSERT INTO system_configs (
    config_key,
    config_value,
    default_value,
    value_type,
    config_shape,
    config_scope,
    description,
    group_name,
    allowed_values
)
SELECT
    seed.config_key,
    CASE
        WHEN seed.config_value_text ~ '^\s*\[' THEN seed.config_value_text::jsonb
        WHEN seed.value_type = 2 THEN to_jsonb((btrim(seed.config_value_text))::bigint)
        WHEN seed.value_type = 3 THEN
            CASE
                WHEN lower(btrim(seed.config_value_text)) IN ('true', '1', 'yes', 'on') THEN 'true'::jsonb
                WHEN lower(btrim(seed.config_value_text)) IN ('false', '0', 'no', 'off') THEN 'false'::jsonb
                ELSE NULL
            END
        WHEN seed.value_type = 6 THEN
            CASE
                WHEN btrim(seed.config_value_text) = '' THEN 'null'::jsonb
                ELSE to_jsonb(seed.config_value_text)
            END
        WHEN seed.value_type = 4 THEN seed.config_value_text::jsonb
        ELSE to_jsonb(seed.config_value_text)
    END AS config_value,
    CASE
        WHEN seed.value_type = 2 THEN to_jsonb((btrim(seed.default_value_text))::bigint)
        WHEN seed.value_type = 3 THEN
            CASE
                WHEN lower(btrim(seed.default_value_text)) IN ('true', '1', 'yes', 'on') THEN 'true'::jsonb
                WHEN lower(btrim(seed.default_value_text)) IN ('false', '0', 'no', 'off') THEN 'false'::jsonb
                ELSE NULL
            END
        WHEN seed.value_type = 6 THEN
            CASE
                WHEN btrim(seed.default_value_text) = '' THEN 'null'::jsonb
                ELSE to_jsonb(seed.default_value_text)
            END
        WHEN seed.value_type = 4 THEN seed.default_value_text::jsonb
        ELSE to_jsonb(seed.default_value_text)
    END AS default_value,
    seed.value_type,
    CASE
        WHEN seed.config_value_text ~ '^\s*\[' THEN 2
        ELSE 1
    END AS config_shape,
    'system' AS config_scope,
    seed.description,
    seed.group_name,
    seed.allowed_values
FROM (
VALUES
-- Contacts configurations
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
('default_nickname_prefix', '无名敲客_', '无名敲客_', 1, 'Default prefix for system-generated profile nickname', 'profile', NULL),
('default_nickname_suffix_length', '6', '6', 2, 'Random uppercase suffix length for system-generated profile nickname (>=1)', 'profile', NULL),
('username_reserved_words', '["admin","root","system","support","operator","moderator","service","official","help","security","qiaoqiaoai"]', 'admin', 1, 'Reserved usernames (lowercase), JSON array', 'username', NULL),

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

-- AI conversation archive configurations
('ai_conversation_archive_enabled', 'true', 'true', 3, 'Enable AI conversation items archive job', 'ai_conversation', NULL),
('ai_conversation_archive_retention_days', '14', '14', 2, 'Archive AI conversation items older than this many days', 'ai_conversation', NULL),
('ai_conversation_archive_keep_recent_count', '200', '200', 2, 'Per conversation, keep this many recent items in hot table', 'ai_conversation', NULL),
('ai_conversation_archive_batch_size', '1000', '1000', 2, 'Maximum items archived per archive job round', 'ai_conversation', NULL),
('ai_conversation_context_max_messages', '20', '20', 2, 'AI conversation context message limit', 'ai_conversation', NULL),
('ai_conversation_context_time_window_days', '30', '30', 2, 'AI conversation context time window in days', 'ai_conversation', NULL),
('ai_llm_min_contract_retry_enabled', 'true', 'true', 3, 'Enable minimal-contract retry for AI LLM responses', 'ai_conversation', NULL),
('ai_llm_min_contract_retry_max_attempts', '3', '3', 2, 'Maximum attempts for minimal-contract retry (>=1)', 'ai_conversation', NULL),
('ai_llm_min_contract_retry_backoff_ms', '300', '300', 2, 'Fixed backoff interval in milliseconds for minimal-contract retry (>=0)', 'ai_conversation', NULL),

-- Alerting configurations
('alerting_cleanup_enabled', 'true', 'true', 3, 'Enable alert_events cleanup worker', 'alerting', NULL),
('alerting_cleanup_interval_seconds', '3600', '3600', 2, 'Cleanup interval in seconds for alert_events (>=1)', 'alerting', NULL),
('alerting_default_retention_days', '30', '30', 2, 'Default retention days for alert_events (>=0)', 'alerting', NULL),
('alerting_retention_days_debug', '7', '7', 2, 'Retention days for DEBUG (10) alert_events', 'alerting', NULL),
('alerting_retention_days_info', '14', '14', 2, 'Retention days for INFO (20) alert_events', 'alerting', NULL),
('alerting_retention_days_warning', '30', '30', 2, 'Retention days for WARNING (30) alert_events', 'alerting', NULL),
('alerting_retention_days_error', '90', '90', 2, 'Retention days for ERROR (40) alert_events', 'alerting', NULL),
('alerting_retention_days_critical', '180', '180', 2, 'Retention days for CRITICAL (50) alert_events', 'alerting', NULL),

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

-- Runtime and invitation intake rate limit configuration
('runtime_observation_rate_limit_requests', '60', '60', 2, 'Runtime observation requests per window', 'runtime', NULL),
('runtime_observation_rate_limit_window_seconds', '60', '60', 2, 'Runtime observation window in seconds', 'runtime', NULL),
('runtime_preflight_probe_rate_limit_requests', '20', '20', 2, 'Runtime preflight probe requests per window', 'runtime', NULL),
('runtime_preflight_probe_rate_limit_window_seconds', '60', '60', 2, 'Runtime preflight probe window in seconds', 'runtime', NULL),
('mp_weixin_review_deadline_at', '', '', 6, 'UTC deadline for mp_weixin review cycle; null or expired means non-review period', 'review', NULL),
('mp_weixin_review_build_ids', '[]', '[]', 1, 'Build IDs used for mp_weixin reviewer detection', 'review', NULL),
('mp_weixin_review_build_time_from', '', '', 6, 'Lower UTC bound for mp_weixin reviewer build time matching', 'review', NULL),
('mp_weixin_review_build_time_to', '', '', 6, 'Upper UTC bound for mp_weixin reviewer build time matching', 'review', NULL),
('mp_weixin_release_build_ids', '[]', '[]', 1, 'Release build IDs used for mp_weixin simulator reviewer detection', 'review', NULL),
('mp_weixin_review_ip_blacklist', '[]', '[]', 1, 'Reviewer IP blacklist for mp_weixin reviewer detection', 'review', NULL),
('public_invite_intake_rate_limit_requests', '20', '20', 2, 'Public invitation intake requests per window', 'invite', NULL),
('public_invite_intake_rate_limit_window_seconds', '60', '60', 2, 'Public invitation intake window in seconds', 'invite', NULL),
('sms_verify_rate_limit_requests', '10', '10', 2, 'SMS verification attempts per window', 'sms', NULL),
('sms_verify_rate_limit_window_seconds', '60', '60', 2, 'SMS verification attempt window in seconds', 'sms', NULL),
('security_user_auto_suspend_enabled', 'true', 'true', 3, 'Enable automatic user suspension on high-risk attacks', 'security_attack', NULL),
('security_rule_version', '2026-05-02', '2026-05-02', 1, 'Current attack-rule version used by enforcement pipeline', 'security_attack', NULL),
('security_ip_block_high_ttl_seconds', '86400', '86400', 2, 'TTL (seconds) for high-risk IP block when threshold reached', 'security_attack', NULL),
('security_ip_block_medium_ttl_seconds', '3600', '3600', 2, 'TTL (seconds) for medium-risk IP block when threshold reached', 'security_attack', NULL),
('security_ip_high_risk_threshold_count', '8', '8', 2, 'High-risk IP hit count threshold', 'security_attack', NULL),
('security_ip_high_risk_threshold_window_seconds', '300', '300', 2, 'High-risk IP threshold window in seconds', 'security_attack', NULL),
('security_ip_medium_risk_threshold_count', '20', '20', 2, 'Medium-risk IP hit count threshold', 'security_attack', NULL),
('security_ip_medium_risk_threshold_window_seconds', '600', '600', 2, 'Medium-risk IP threshold window in seconds', 'security_attack', NULL),

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
('avatar_max_size_mb', '1', '1', 2, 'Maximum avatar file size in MB', 'media', NULL),
('avatar_allowed_formats', '["image/jpeg","image/png","image/webp"]', 'image/jpeg', 1, 'Allowed avatar MIME types', 'media', NULL),

-- Media upload quota configuration (✅ MVP P0)
('avatar_upload_daily_quota', '5', '5', 2, 'Maximum avatar uploads per user per day', 'media', NULL),
('avatar_upload_daily_size_quota_mb', '10', '10', 2, 'Maximum total avatar upload size per user per day (MB)', 'media', NULL),

-- Media upload rate limit configuration
('media_upload_rate_limit_requests', '10', '10', 2, 'Media upload requests per window', 'media', NULL),
('media_upload_rate_limit_window_seconds', '60', '60', 2, 'Media upload window in seconds', 'media', NULL),

-- Operation configurations
('invite_share_command_texts', '["来敲敲AI {{code}} {{link}}"]', '来敲敲AI {{code}} {{link}}', 1, 'Invite share command text templates', 'operation', NULL),
('invite_share_card_titles', '["来敲敲AI，对话敲多新奇有趣"]', '来敲敲AI，对话敲多新奇有趣', 1, 'Invite share card title templates', 'operation', NULL)
) AS seed(config_key, config_value_text, default_value_text, value_type, description, group_name, allowed_values)
ON CONFLICT (config_key) DO NOTHING;

-- Align config scope defaults for security-sensitive keys.
UPDATE system_configs
SET config_scope = 'security'
WHERE config_key IN (
    'leancloud_im_webhook_token',
    'admin_auth_whitelist',
    'sms_whitelist'
);

-- Align config scope defaults for operation keys.
UPDATE system_configs
SET config_scope = 'operation'
WHERE config_key IN (
    'invite_share_command_texts',
    'invite_share_card_titles',
    'default_nickname_prefix',
    'default_nickname_suffix_length'
)
   OR group_name = 'contacts';

-- Align review-cycle keys to system scope.
UPDATE system_configs
SET config_scope = 'system'
WHERE config_key IN (
    'mp_weixin_review_deadline_at',
    'mp_weixin_review_build_ids',
    'mp_weixin_review_build_time_from',
    'mp_weixin_review_build_time_to',
    'mp_weixin_release_build_ids',
    'mp_weixin_review_ip_blacklist'
);

-- Drop deprecated operation invite-share keys.
DELETE FROM system_configs
WHERE config_key IN (
    'operation_invite_share_command_text',
    'operation_invite_share_card_title',
    'operation_invite_share_text',
    'operation_invite_share_card_image_url'
);


-- ============================================================================
-- LLM Providers and Configurations
-- ============================================================================

-- Insert basic LLM providers
INSERT INTO llm_providers (id, name, display_name, api_key_env, base_url, default_model, supports_streaming, supports_json_schema, supports_thinking) VALUES
(1, 'doubao', 'Doubao Production', 'DOUBAO_API_KEY', 'https://ark.cn-beijing.volces.com/api/v3', 'doubao-seed-1-6-250615', 1, 1, 1),
(2, 'mock', 'Mock LLM (Testing)', NULL, NULL, 'mock-mirror', 0, 1, 0)
ON CONFLICT (display_name) DO NOTHING;

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
(2, 'mock', 'mock-mirror', 0.7, 2000, 5, 'disabled', 0.70, 0.00, 0.00, '[]'::jsonb, 'strict', 1, 999, '{"memory_limits": {"core": 30, "recent": 50}}'::jsonb),
(2, 'mock-random', 'mock-random', 0.7, 2000, 5, 'disabled', 0.70, 0.00, 0.00, '[]'::jsonb, 'strict', 1, 1000, '{"memory_limits": {"core": 30, "recent": 50}}'::jsonb)
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- Data Loading Complete
-- ============================================================================

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Required system data loaded successfully for SHARED baseline!';
    RAISE NOTICE 'System configs and LLM configurations have been initialized.';
END $$;
