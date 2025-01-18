from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import json
import asyncio

from database import db_manager

router = APIRouter()

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

class MessageSender:
    def __init__(self):
        self.connections = {}
    
    def register_connection(self, user_id: str, websocket):
        self.connections[user_id] = websocket
    
    def remove_connection(self, user_id: str):
        if user_id in self.connections:
            del self.connections[user_id]
    
    async def send_message(self, user_id: str, message: str):
        if user_id in self.connections:
            try:
                await self.connections[user_id].send_text(json.dumps({
                    "content": message,
                    "timestamp": datetime.now().isoformat()
                }))
            except Exception as e:
                print(f"Error sending message to {user_id}: {e}")

# 创建全局实例
message_sender = MessageSender()

@router.post("/message", response_model=MessageResponse)
async def transfer_message(message: MessageRequest, background_tasks: BackgroundTasks):
    """
    处理接收到的消息并转发给相应的bot
    """
    try:
        # 生成消息ID
        message_id = f"msg_{int(datetime.now().timestamp() * 1000)}"
        
        # 异步处理消息
        background_tasks.add_task(
            process_message,
            message_id,
            message.user_id,
            message.bot_id,
            message.content,
            message.message_type,
            message.metadata
        )
        
        return MessageResponse(
            message_id=message_id,
            status="accepted",
            timestamp=datetime.now(),
            metadata={"type": message.message_type}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process message: {str(e)}"
        )

async def process_message(
    message_id: str,
    user_id: str,
    bot_id: str,
    content: str,
    message_type: str,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    异步处理消息的具体逻辑
    """
    try:
        # 记录消息到数据库
        await db_manager.save_message(
            from_user=user_id,
            to_user=bot_id,
            content=content
        )
        
        # 转发消息给bot处理
        await bot_manager.process_message(
            user_id=user_id,
            bot_id=bot_id,
            message=content
        )
        
    except Exception as e:
        print(f"Error processing message {message_id}: {e}")
        # 发送错误通知给用户
        await message_sender.send_message(
            user_id,
            json.dumps({
                "error": "Failed to process message",
                "message_id": message_id
            })
        )

@router.get("/message/{message_id}")
async def get_message_status(message_id: str):
    """
    获取消息处理状态
    """
    try:
        # TODO: 实现消息状态查询逻辑
        return {
            "message_id": message_id,
            "status": "processed",
            "timestamp": datetime.now()
        }
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Message not found: {str(e)}"
        )

@router.post("/batch-message")
async def batch_transfer_messages(messages: list[MessageRequest], background_tasks: BackgroundTasks):
    """
    批量处理消息
    """
    try:
        message_ids = []
        for message in messages:
            message_id = f"msg_{int(datetime.now().timestamp() * 1000)}"
            message_ids.append(message_id)
            
            background_tasks.add_task(
                process_message,
                message_id,
                message.user_id,
                message.bot_id,
                message.content,
                message.message_type,
                message.metadata
            )
        
        return {
            "message_ids": message_ids,
            "status": "accepted",
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process batch messages: {str(e)}"
        )

@router.post("/scheduled-message")
async def schedule_message(
    message: MessageRequest,
    schedule_time: datetime,
    background_tasks: BackgroundTasks
):
    """
    安排定时消息
    """
    try:
        message_id = f"scheduled_{int(datetime.now().timestamp() * 1000)}"
        
        # 保存定时消息到数据库
        await db_manager.save_scheduled_message(
            from_user=message.user_id,
            to_user=message.bot_id,
            content=message.content,
            send_at=schedule_time
        )
        
        return {
            "message_id": message_id,
            "scheduled_time": schedule_time,
            "status": "scheduled"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to schedule message: {str(e)}"
        )

@router.delete("/message/{message_id}")
async def cancel_message(message_id: str):
    """
    取消定时消息
    """
    try:
        # TODO: 实现取消定时消息的逻辑
        return {
            "message_id": message_id,
            "status": "cancelled",
            "timestamp": datetime.now()
        }
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Message not found or cannot be cancelled: {str(e)}"
        )

@router.get("/health")
async def check_transfer_health():
    """
    检查消息转发系统的健康状态
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "pending_messages": 0  # TODO: 实现待处理消息计数
    }