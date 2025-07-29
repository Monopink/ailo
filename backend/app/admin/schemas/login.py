from datetime import datetime

from pydantic import BaseModel, Field


class CredentialsSchema(BaseModel):
    username: str = Field(..., description="用户名称", example="admin")
    password: str = Field(..., description="密码", example="123456")


class JWTOut(BaseModel):
    access_token: str
    username: str
    token_type: str = "bearer"


class JWTPayload(BaseModel):
    user_id: int
    username: str
    role: str
    exp: datetime
