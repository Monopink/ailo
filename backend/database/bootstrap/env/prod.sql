-- Production environment bootstrap data.

SET timezone = 'UTC';
SET client_encoding = 'UTF8';

-- ADMIN_BOOTSTRAP_PASSWORD_HASH is injected by scripts/deploy/provision.py.
INSERT INTO admin_users (username, password_hash, role, status) VALUES
('admin', '{{ADMIN_BOOTSTRAP_PASSWORD_HASH}}', 1, 1)
ON CONFLICT (username) DO NOTHING;

UPDATE system_configs AS sc
SET config_value = CASE
        WHEN sc.value_type = 2 THEN to_jsonb((btrim(v.config_value_text))::bigint)
        WHEN sc.value_type = 3 THEN
            CASE
                WHEN lower(btrim(v.config_value_text)) IN ('true', '1', 'yes', 'on') THEN 'true'::jsonb
                WHEN lower(btrim(v.config_value_text)) IN ('false', '0', 'no', 'off') THEN 'false'::jsonb
                ELSE NULL
            END
        WHEN sc.value_type = 4 THEN v.config_value_text::jsonb
        WHEN sc.value_type = 6 THEN
            CASE
                WHEN btrim(v.config_value_text) = '' THEN 'null'::jsonb
                ELSE to_jsonb(v.config_value_text)
            END
        ELSE to_jsonb(v.config_value_text)
    END,
    updated_at = NOW()
FROM (
    VALUES
        ('leancloud_im_server_url', 'https://chat.qiaoqiaoai.cn'),
        ('api_base_url', 'https://synapse.qiaoqiaoai.cn'),
        ('media_public_base_url', 'https://cortex.qiaoqiaoai.cn'),
        ('api_rate_limit_requests', '100'),
        ('admin_auth_rate_limit_requests', '20'),
        ('admin_auth_max_failures', '5'),
        ('admin_auth_lockout_duration_minutes', '60'),
        ('admin_auth_whitelist', ''),
        ('auth_password_rate_limit_short_requests', '3'),
        ('auth_password_rate_limit_long_requests', '10'),
        ('auth_password_max_failures', '3'),
        ('auth_password_failure_window_seconds', '1800'),
        ('auth_password_lockout_duration_seconds', '1800'),
        ('sms_rate_limit_requests', '1'),
        ('runtime_observation_rate_limit_requests', '30'),
        ('runtime_preflight_probe_rate_limit_requests', '10'),
        ('public_invite_intake_rate_limit_requests', '10'),
        ('sms_verify_rate_limit_requests', '5'),
        ('admin_captcha_mode', 'strict')
) AS v(config_key, config_value_text)
WHERE sc.config_key = v.config_key;

UPDATE llm_configs
SET extra_params = '{"memory_limits": {"core": 20, "recent": 30}}'::jsonb
WHERE name IN ('advanced', 'mock', 'mock-random');
