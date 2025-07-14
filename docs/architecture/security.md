# 安全设计

## 认证与授权

### JWT Token 管理

```python
# Token生成 (accounts_service)
token_data = {
    "sub": user.entity_id,
    "exp": datetime.utcnow() + timedelta(hours=24)
}
access_token = jwt.encode(token_data, SECRET_KEY, algorithm="HS256")
```

### 服务间认证

```python
# 内部服务调用认证
headers = {
    "Authorization": f"Bearer {jwt_token}",
    "X-Internal-Service-Key": INTERNAL_SERVICE_KEY
}
```

### Token验证流程

```python
# 每个服务独立验证Token
async def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        return user_id
    except JWTError:
        raise HTTPException(401, "Invalid token")
```

## API安全策略

### 无数据库ID暴露

- **原则**: 永不暴露数据库自增ID
- **实现**: 所有API响应使用entity_id
- **格式**: `qqid_{type}{number}`
- **验证**: 前端id字段映射到后端entity_id

### 输入验证

```python
# 使用Pydantic严格验证
class MessageRequest(BaseModel):
    content: str = Field(..., max_length=1000)
    to_entity_id: str = Field(..., regex=r"^qqid_[a-z]\d+$")
```

### 输出过滤

```python
# 响应数据过滤敏感信息
def filter_user_response(user_data):
    return {
        "id": user_data.entity_id,  # 不暴露数据库ID
        "phone": mask_phone(user_data.phone),  # 手机号脱敏
        "status": user_data.status
        # 不包含password_hash等敏感字段
    }
```

## 数据安全

### 敏感数据处理

```python
# 密码哈希
password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

# 手机号脱敏显示
def mask_phone(phone: str) -> str:
    return f"{phone[:3]}****{phone[-4:]}"
```

### 数据库安全

- **连接加密**: 使用SSL连接MySQL
- **权限最小化**: 每个服务使用独立数据库用户
- **敏感字段**: password_hash等字段不出现在API响应中

### 消息加密

```python
# LeanCloud消息传输前加密
encrypted_content = encrypt_message(message_content, encryption_key)
await leancloud_client.send_message(
    conversation_id=conv_id,
    content=encrypted_content
)
```

## 访问控制

### 联系人关系验证

```python
async def check_contact_permission(user_id: str, contact_id: str):
    # 验证是否为联系人关系
    contact = await get_contact_relationship(user_id, contact_id)
    if not contact:
        raise HTTPException(403, "Not authorized to access this contact")
```

### 消息发送权限

```python
async def validate_message_permission(from_id: str, to_id: str):
    # 1. 检查联系人关系
    if not await check_contact_relationship(from_id, to_id):
        return False, "NOT_CONTACTS"
    
    # 2. 检查机器人状态
    if is_bot(to_id) and not await check_bot_active(to_id):
        return False, "BLOCKED_BY_USER"
        
    return True, None
```

### 资源访问控制

```python
# 用户只能访问自己的数据
@require_auth
async def get_user_contacts(current_user: str):
    # current_user从JWT token解析
    contacts = await get_contacts_by_user(current_user)
    return contacts
```

## 网络安全

### CORS配置

```python
# 严格的CORS设置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # 指定允许的域名
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"]
)
```

### 请求限制

```python
# 短信验证码频率限制
@rate_limit("5/minute")
async def send_sms_code(phone: str):
    # 限制每分钟最多5次请求
    pass

# 登录尝试限制  
@rate_limit("10/hour")
async def login(phone: str, password: str):
    # 限制每小时最多10次登录尝试
    pass
```

### 请求验证

```python
# 验证请求来源
async def verify_webhook_signature(request: Request):
    signature = request.headers.get("X-LC-Signature")
    body = await request.body()
    expected = hmac.new(WEBHOOK_SECRET, body, hashlib.sha1).hexdigest()
    
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(401, "Invalid webhook signature")
```

## 错误处理安全

### 错误信息过滤

```python
# 不暴露内部错误信息
try:
    result = await database_operation()
except SQLAlchemyError as e:
    logger.error("database_error", error=str(e))
    # 返回通用错误信息，不暴露SQL错误
    raise HTTPException(500, "Internal server error")
```

### 日志安全

```python
# 敏感信息不记录到日志
logger.info("user_login", 
    user_id=user.entity_id,
    # 不记录密码、token等敏感信息
    ip_address=request.client.host
)
```

## 开发环境安全

### 测试数据隔离

- 开发环境使用独立数据库
- 测试账号与生产数据完全隔离
- 定期清理测试数据

### 配置管理

```python
# 敏感配置通过环境变量管理
DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
LEANCLOUD_APP_KEY = os.getenv("LEANCLOUD_APP_KEY")
```

### 代码安全

- 敏感信息不提交到版本控制
- 使用.env文件管理本地配置
- 定期更新依赖包，修复安全漏洞

## 监控与审计

### 安全事件监控

```python
# 记录安全相关事件
logger.warning("failed_login_attempt",
    phone=phone,
    ip_address=request.client.host,
    user_agent=request.headers.get("User-Agent")
)
```

### 访问日志

```python
# 记录API访问日志
logger.info("api_access",
    endpoint=request.url.path,
    method=request.method,
    user_id=current_user.entity_id,
    response_status=response.status_code
)
```
