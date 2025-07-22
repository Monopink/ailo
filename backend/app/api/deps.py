from fastapi import HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError
from pydantic import ValidationError
from utils.logging import get_logger
from core.config import settings
from core.database import get_db
from models.user import User
from crud.user import user_crud
from schemas.user import TokenData

logger = get_logger(__name__)

# OAuth2 password bearer for unified authentication
reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login/password")


async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(reusable_oauth2)
) -> User:
    """
    Get current user from JWT token with full database object.
    Unified authentication dependency for all protected endpoints.

    Args:
        db: Database session
        token: JWT token from OAuth2 password bearer

    Returns:
        User: Full user database object

    Raises:
        HTTPException: If token is invalid or user not found
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
    user = await user_crud.get_user_by_entity_id(db, entity_id=token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
