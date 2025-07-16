from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import get_password_hash
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def get_user_by_email(db: AsyncSession, *, email: str) -> User | None:
    """
    Look up a user by email.
    """
    if not email:
        return None
    result = await db.execute(select(User).filter(User.email == email))
    return result.scalars().first()


async def get_user_by_username(db: AsyncSession, *, username: str) -> User | None:
    """
    Look up a user by username.
    """
    if not username:
        return None
    result = await db.execute(select(User).filter(User.username == username))
    return result.scalars().first()


async def get_user_by_phone(db: AsyncSession, *, phone: str) -> User | None:
    """
    Look up a user by phone number.
    """
    result = await db.execute(select(User).filter(User.phone == phone))
    return result.scalars().first()


async def get_user_by_entity_id(db: AsyncSession, *, entity_id: str) -> User | None:
    """
    Look up a user by entity_id.
    """
    result = await db.execute(select(User).filter(User.entity_id == entity_id))
    return result.scalars().first()


async def create_user(db: AsyncSession, *, user_in: UserCreate) -> User:
    """
    Create a new user.
    """
    # Generate a unique numeric entity_id
    from ..utils.id_generator import generate_unique_entity_id
    from ..core.config import settings

    entity_id = await generate_unique_entity_id(db)

    db_obj = User(
        entity_id=entity_id,
        phone=user_in.phone,
        password_hash=get_password_hash(user_in.password),
        # Explicitly set these to None to avoid SQL constraints
        username=None,
        email=None,
        status="active",
        role="user",
        # Set contact limits from configuration
        contact_limit=settings.DEFAULT_CONTACT_LIMIT,
        search_display_limit=settings.DEFAULT_SEARCH_DISPLAY_LIMIT,
    )
    db.add(db_obj)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        # Log the actual error for developers but don't send to frontend
        logger.error("database_integrity_error", error=str(e), exc_info=True)

        # Check if it's a phone number uniqueness violation
        error_msg = str(e).lower()
        if "phone" in error_msg and ("unique" in error_msg or "duplicate" in error_msg):
            logger.warning("phone_number_already_registered", phone=user_in.phone)
            raise HTTPException(status_code=409, detail="Phone number already registered")
        else:
            # Generic error for other database issues
            logger.error("user_creation_failed", error_type="database_error")
            raise HTTPException(status_code=500, detail="System error during registration")
    await db.refresh(db_obj)
    return db_obj


async def update_password(db: AsyncSession, *, user: User, new_password: str) -> User:
    """
    Update user's password.
    """
    user.password_hash = get_password_hash(new_password)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
