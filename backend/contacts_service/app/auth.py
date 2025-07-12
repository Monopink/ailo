"""
Authentication utilities for contacts_service
"""

import jwt
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .utils.logging import get_logger

logger = get_logger(__name__)

security = HTTPBearer()

# JWT settings - must match accounts_service settings
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Verify JWT token and return user info
    """
    try:
        token = credentials.credentials

        # Properly verify JWT token with secret key
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        if not payload.get("sub"):
            logger.warning("jwt_token_missing_subject", token_preview=token[:20] + "...")
            raise HTTPException(status_code=401, detail="Invalid token")

        logger.debug("jwt_token_verified", user_id=payload.get("sub"), entity_id=payload.get("entity_id"))

        return {
            "user_id": payload.get("sub"),
            "entity_id": payload.get("entity_id"),
            "phone": payload.get("phone"),
        }

    except jwt.ExpiredSignatureError:
        logger.warning("jwt_token_expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning("jwt_token_invalid", error=str(e))
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error("token_verification_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=401, detail="Token verification failed")


def get_current_user(user_info: dict = Depends(verify_token)) -> dict:
    """
    Get current user from token
    """
    return user_info
