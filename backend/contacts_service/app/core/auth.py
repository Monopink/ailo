"""
Authentication utilities for contacts service
Used for JWT token validation and user extraction
"""

import jwt
from typing import Optional, Dict, Any
import structlog

logger = structlog.get_logger(__name__)

# JWT settings - should match accounts_service settings
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode JWT token and extract payload
    
    Args:
        token: JWT token string
        
    Returns:
        Token payload dict or None if invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("token_expired")
        return None
    except jwt.InvalidTokenError:
        logger.debug("invalid_token")
        return None
    except Exception as e:
        logger.debug("token_decode_error", error=str(e))
        return None
