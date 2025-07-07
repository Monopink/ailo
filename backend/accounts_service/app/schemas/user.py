from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime, date


# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    sub: Optional[str] = None


# Phone Schemas
class PhoneSchema(BaseModel):
    phone: str = Field(..., description="中国的手机号码, 不需要+86")


# User Schemas
class UserBase(BaseModel):
    phone: str
    username: Optional[str] = None
    email: Optional[str] = None


class UserCreate(BaseModel):
    phone: str = Field(..., description="中国的手机号码, 不需要+86")
    password: str = Field(..., min_length=8, description="密码，长度至少8位")
    code: str = Field(..., min_length=6, max_length=6, description="6位短信验证码")


class UserLoginPassword(BaseModel):
    phone: str = Field(..., description="中国的手机号码, 不需要+86")
    password: str = Field(..., description="密码")


class UserLoginCode(BaseModel):
    phone: str = Field(..., description="中国的手机号码, 不需要+86")
    code: str = Field(..., min_length=6, max_length=6, description="6位短信验证码")


class PasswordReset(BaseModel):
    phone: str = Field(..., description="中国的手机号码, 不需要+86")
    code: str = Field(..., min_length=6, max_length=6, description="6位短信验证码")
    new_password: str = Field(..., min_length=8, description="新密码，长度至少8位")


# Properties to return to client
class User(UserBase):
    entity_id: str
    status: str
    role: str
    is_verified: bool
    subscription_type: str

    class Config:
        from_attributes = True
