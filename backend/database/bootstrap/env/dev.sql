-- Development environment bootstrap data.
-- Default admin password: admin123

SET timezone = 'UTC';
SET client_encoding = 'UTF8';

INSERT INTO admin_users (username, password_hash, role, status) VALUES
('admin', '$2b$12$i4kzuJnXuIQdxS3GgFXOh.JhvEjMntTakeqw4QKXah2zCpXpbwlJi', 1, 1),
('manager', '$2b$12$i4kzuJnXuIQdxS3GgFXOh.JhvEjMntTakeqw4QKXah2zCpXpbwlJi', 2, 1),
('viewer', '$2b$12$i4kzuJnXuIQdxS3GgFXOh.JhvEjMntTakeqw4QKXah2zCpXpbwlJi', 3, 1)
ON CONFLICT (username) DO NOTHING;

UPDATE system_configs AS sc
SET config_value = v.config_value,
    updated_at = NOW()
FROM (
    VALUES
        ('api_base_url', 'http://localhost:8000'),
        ('media_public_base_url', ''),
        ('leancloud_im_server_url', 'https://zcuk19lc.lc-cn-n1-shared.com'),
        ('admin_auth_whitelist', '127.0.0.1,::1')
) AS v(config_key, config_value)
WHERE sc.config_key = v.config_key;
