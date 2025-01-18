from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import json

class MessageRequest(BaseModel):
    user_id: str
    bot_id: str
    content: str
    message_type: Optional[str] = "text"
    metadata: Optional[Dict[str, Any]] = None

class MessageResponse(BaseModel):
    message_id: str
    status: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

# 配置允许的bot_ids
ALLOWED_BOT_IDS = [
    "9001",  # 示例bot id
    "9002",
    "9003"
]

router = APIRouter()
bot_manager = None

def init_bot_manager(manager):
    global bot_manager
    bot_manager = manager

@router.post("/message", response_model=MessageResponse)
async def transfer_message(message: MessageRequest, background_tasks: BackgroundTasks):
    """
    处理接收到的消息并转发给相应的bot
    """
    try:
        # 验证bot_id是否在允许列表中
        if message.bot_id not in ALLOWED_BOT_IDS:
            raise HTTPException(
                status_code=400,
                detail=f"Bot ID {message.bot_id} is not supported"
            )

        # 生成消息ID
        message_id = f"msg_{int(datetime.now().timestamp() * 1000)}"
        
        # 转发消息给bot_manager处理
        if bot_manager is None:
            raise HTTPException(
                status_code=500,
                detail="Bot manager not initialized"
            )

        # 使用background_tasks异步处理消息
        background_tasks.add_task(
            bot_manager.process_message,
            user_id=message.user_id,
            bot_id=message.bot_id,
            message=message.content
        )
        
        return MessageResponse(
            message_id=message_id,
            status="accepted",
            timestamp=datetime.now(),
            metadata={"type": message.message_type}
        )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process message: {str(e)}"
        )

@router.get("/supported-bots")
async def get_supported_bots():
    """
    获取支持的bot列表
    """
    return {
        "supported_bots": ALLOWED_BOT_IDS,
        "total": len(ALLOWED_BOT_IDS)
    }

@router.get("/health")
async def check_transfer_health():
    """
    检查消息转发系统的健康状态
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "supported_bots": len(ALLOWED_BOT_IDS)
    }
