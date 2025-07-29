import jwt

from admin.schemas.login import JWTPayload
from admin.settings.config import admin_settings


def create_access_token(*, data: JWTPayload):
    payload = data.model_dump().copy()
    encoded_jwt = jwt.encode(payload, admin_settings.SECRET_KEY, algorithm=admin_settings.JWT_ALGORITHM)
    return encoded_jwt
