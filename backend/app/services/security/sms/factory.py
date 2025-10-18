"""
SMS Provider Factory

Creates SMS provider instances based on configuration.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from services.system_config import get_config
from utils.logging import get_logger
from .base import SMSProvider
from .mock import MockSMSProvider

logger = get_logger(__name__)


async def create_sms_provider(db: AsyncSession) -> SMSProvider:
    """
    Create SMS provider based on configuration.
    
    Reads from system_configs:
    - sms_provider: 'mock' | (future: 'aliyun', 'tencent')
    
    Args:
        db: Database session
        
    Returns:
        SMS provider instance
        
    Raises:
        ValueError: If provider type is not supported
    """
    provider_type = await get_config(db, key="sms_provider", default="mock")
    
    if provider_type == "mock":
        logger.info("creating_mock_sms_provider")
        return MockSMSProvider()
    
    # Future providers
    # elif provider_type == "aliyun":
    #     return AliyunSMSProvider(...)
    # elif provider_type == "tencent":
    #     return TencentSMSProvider(...)
    
    else:
        error_msg = f"Unsupported SMS provider: {provider_type}"
        logger.error("unsupported_sms_provider", provider=provider_type)
        raise ValueError(error_msg)

