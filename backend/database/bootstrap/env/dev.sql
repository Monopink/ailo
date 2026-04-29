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
        ('api_base_url', 'http://localhost:8000'),
        ('media_public_base_url', ''),
        ('leancloud_im_server_url', 'https://zcuk19lc.lc-cn-n1-shared.com'),
        ('admin_auth_whitelist', '127.0.0.1,::1')
) AS v(config_key, config_value_text)
WHERE sc.config_key = v.config_key;
