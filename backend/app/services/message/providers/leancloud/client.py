"""
LeanCloud REST API client functions.

This module provides pure functions for LeanCloud REST API calls.
All functions are stateless and return explicit results.
"""

from typing import Optional, Dict, Any
import httpx
from utils.logging import get_logger

logger = get_logger(__name__)


async def create_system_conversation(
    app_id: str,
    master_key: str,
    base_url: str,
    name: str = "系统对话"
) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Create LeanCloud system conversation (service conversation).
    
    Pure function that calls LeanCloud REST API to create a system conversation.
    
    Args:
        app_id: LeanCloud App ID
        master_key: LeanCloud Master Key
        base_url: LeanCloud base URL (e.g., https://zcuk19lc.lc-cn-n1-shared.com)
        name: System conversation name (default: "系统对话")
        
    Returns:
        Tuple of (success, conversation_id, error_message)
        - success: True if creation successful
        - conversation_id: LeanCloud conversation ID (objectId) if successful
        - error_message: Error message if failed
        
    Example:
        success, conv_id, error = await create_system_conversation(
            app_id="xxx",
            master_key="yyy",
            base_url="https://xxx.lc-cn-n1-shared.com",
            name="系统对话"
        )
    """
    url = f"{base_url}/1.2/rtm/service-conversations"
    headers = {
        "X-LC-Id": app_id,
        "X-LC-Key": f"{master_key},master",
        "Content-Type": "application/json"
    }
    body = {"name": name}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=body)
            
            if response.status_code == 201 or response.status_code == 200:
                data = response.json()
                conversation_id = data.get("objectId")
                if conversation_id:
                    logger.info(
                        "leancloud_system_conversation_created",
                        conversation_id=conversation_id,
                        name=name
                    )
                    return True, conversation_id, None
                else:
                    error_msg = "Response missing objectId field"
                    logger.error("leancloud_create_conversation_invalid_response", response=data)
                    return False, None, error_msg
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(
                    "leancloud_create_conversation_failed",
                    status_code=response.status_code,
                    response=response.text
                )
                return False, None, error_msg
                
    except httpx.TimeoutException as e:
        error_msg = f"Request timeout: {str(e)}"
        logger.error("leancloud_create_conversation_timeout", error=str(e))
        return False, None, error_msg
    except httpx.HTTPError as e:
        error_msg = f"HTTP error: {str(e)}"
        logger.error("leancloud_create_conversation_http_error", error=str(e))
        return False, None, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error("leancloud_create_conversation_unexpected_error", error=str(e))
        return False, None, error_msg


async def subscribe_user_to_conversation(
    app_id: str,
    master_key: str,
    base_url: str,
    conversation_id: str,
    client_id: str
) -> tuple[bool, Optional[str]]:
    """
    Subscribe user to LeanCloud system conversation.
    
    Args:
        app_id: LeanCloud App ID
        master_key: LeanCloud Master Key
        base_url: LeanCloud base URL
        conversation_id: System conversation ID
        client_id: User's client ID (qiao_id)
        
    Returns:
        Tuple of (success, error_message)
    """
    url = f"{base_url}/1.2/rtm/service-conversations/{conversation_id}/subscribers"
    headers = {
        "X-LC-Id": app_id,
        "X-LC-Key": f"{master_key},master",
        "Content-Type": "application/json"
    }
    body = {"client_id": client_id}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=body)
            
            if response.status_code == 200:
                logger.info(
                    "leancloud_user_subscribed",
                    conversation_id=conversation_id,
                    client_id=client_id
                )
                return True, None
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(
                    "leancloud_subscribe_failed",
                    conversation_id=conversation_id,
                    client_id=client_id,
                    status_code=response.status_code,
                    response=response.text
                )
                return False, error_msg
                
    except httpx.TimeoutException as e:
        error_msg = f"Request timeout: {str(e)}"
        logger.error("leancloud_subscribe_timeout", error=str(e))
        return False, error_msg
    except httpx.HTTPError as e:
        error_msg = f"HTTP error: {str(e)}"
        logger.error("leancloud_subscribe_http_error", error=str(e))
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error("leancloud_subscribe_unexpected_error", error=str(e))
        return False, error_msg


async def unsubscribe_user_from_conversation(
    app_id: str,
    master_key: str,
    base_url: str,
    conversation_id: str,
    client_id: str
) -> tuple[bool, Optional[str]]:
    """
    Unsubscribe user from LeanCloud system conversation.
    
    Args:
        app_id: LeanCloud App ID
        master_key: LeanCloud Master Key
        base_url: LeanCloud base URL
        conversation_id: System conversation ID
        client_id: User's client ID (qiao_id)
        
    Returns:
        Tuple of (success, error_message)
    """
    url = f"{base_url}/1.2/rtm/service-conversations/{conversation_id}/subscribers/{client_id}"
    headers = {
        "X-LC-Id": app_id,
        "X-LC-Key": f"{master_key},master"
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.delete(url, headers=headers)
            
            if response.status_code == 200:
                logger.info(
                    "leancloud_user_unsubscribed",
                    conversation_id=conversation_id,
                    client_id=client_id
                )
                return True, None
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(
                    "leancloud_unsubscribe_failed",
                    conversation_id=conversation_id,
                    client_id=client_id,
                    status_code=response.status_code,
                    response=response.text
                )
                return False, error_msg
                
    except httpx.TimeoutException as e:
        error_msg = f"Request timeout: {str(e)}"
        logger.error("leancloud_unsubscribe_timeout", error=str(e))
        return False, error_msg
    except httpx.HTTPError as e:
        error_msg = f"HTTP error: {str(e)}"
        logger.error("leancloud_unsubscribe_http_error", error=str(e))
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error("leancloud_unsubscribe_unexpected_error", error=str(e))
        return False, error_msg

