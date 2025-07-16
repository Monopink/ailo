from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User
from app.schemas.user import TokenData

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login/password")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get an async database session.
    """
    async with SessionLocal() as session:
        yield session


async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(reusable_oauth2)
) -> User:
    """
    Dependency to get the current user from a JWT token.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        token_data = TokenData(**payload)
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    if not token_data.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    user = await crud.user.get_user_by_entity_id(db, entity_id=token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
