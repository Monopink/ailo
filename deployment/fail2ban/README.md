## 修改密码

``` shell
cd /opt/ailo-prod/ailo/deployment/scripts
./generate-basic-auth.sh prod admin
./generate-basic-auth.sh prod logs_admin --target logs
```

然后确保权限：

``` shell
chmod 644 /opt/ailo-prod/ailo/deployment/prod/secrets/.htpasswd \
/opt/ailo-prod/ailo/deployment/prod/secrets/.htpasswd_logs
```

## IP白名单

### 方案 1

`/etc/fail2ban/jail.d/ailo-nginx-admin-auth.local` 文件：

```
ignoreip = 127.0.0.1/8 ::1 123.456.123.456
```

### 方案 2

改模板源文件（下次重新 setup 会覆盖到 /etc）：

- `deployment/fail2ban/jail.d/ailo-nginx-admin-auth-prod.local`
- `deployment/fail2ban/setup-fail2ban.sh`

修改后生效命令：

``` shell
sudo systemctl restart fail2ban
sudo fail2ban-client status ailo-nginx-admin-auth-prod
```
