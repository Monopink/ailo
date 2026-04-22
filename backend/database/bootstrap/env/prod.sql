-- Production environment bootstrap data.

SET timezone = 'UTC';
SET client_encoding = 'UTF8';

-- ADMIN_BOOTSTRAP_PASSWORD_HASH is injected by scripts/deploy/provision.py.
INSERT INTO admin_users (username, password_hash, role, status) VALUES
('admin', '{{ADMIN_BOOTSTRAP_PASSWORD_HASH}}', 1, 1)
ON CONFLICT (username) DO NOTHING;

UPDATE system_configs AS sc
SET config_value = v.config_value,
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
        ('admin_captcha_mode', 'strict')
) AS v(config_key, config_value)
WHERE sc.config_key = v.config_key;

UPDATE llm_configs
SET extra_params = '{"memory_limits": {"core": 20, "recent": 30}}'::jsonb
WHERE name IN ('advanced', 'mock', 'mock-random');
