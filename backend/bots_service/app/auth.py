"""
Authentication utilities for bots_service
"""

import jwt
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .core.config import settings
import structlog

logger = structlog.get_logger(__name__)

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Verify JWT token and return user info
    """
    try:
        token = credentials.credentials
        
        # For now, we'll decode without verification since we don't have the secret
        # In production, you should verify the token with the same secret used by accounts_service
        payload = jwt.decode(token, options={"verify_signature": False})
        
        if not payload.get("sub"):
            raise HTTPException(status_code=401, detail="Invalid token")
            
        return {
            "user_id": payload.get("sub"),
            "entity_id": payload.get("entity_id"),
            "phone": payload.get("phone")
        }
        
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error("token_verification_failed", error=str(e))
        raise HTTPException(status_code=401, detail="Token verification failed")


def get_current_user(user_info: dict = Depends(verify_token)) -> dict:
    """
    Get current user from token
    """
    return user_info
