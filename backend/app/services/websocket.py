import asyncio
import json
import logging
from typing import Dict, Any
from fastapi import WebSocket
from event_bus import event_bus, EventTypes
from database import DatabaseManager
from message_router import MessageRouter

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.db_manager = DatabaseManager()
        self.message_router = MessageRouter(self.db_manager)
        
    async def connect(self, websocket: WebSocket, client_id: str):
        """
        处理新的 WebSocket 连接
        """
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"Client connected: {client_id}")
        
        # 订阅相关事件
        event_bus.subscribe(
            f"{EventTypes.MESSAGE_PROCESSED}_{client_id}",
            self._handle_processed_message
        )

    async def disconnect(self, client_id: str):
        """
        处理 WebSocket 断开连接
        """
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        logger.info(f"Client disconnected: {client_id}")
        
        # 取消事件订阅
        event_bus.unsubscribe(
            f"{EventTypes.MESSAGE_PROCESSED}_{client_id}",
            self._handle_processed_message
        )

    async def receive_message(self, websocket: WebSocket, client_id: str):
        """
        处理接收到的消息
        """
        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # 添加消息源信息
                message['from_id'] = client_id
                message['source'] = 'websocket'
                
                # 发布消息到事件总线
                await event_bus.publish(EventTypes.MESSAGE_RECEIVED, message)
                
                # 路由消息到对应的模型
                response = await self.message_router.route_message(message)
                
                # 发送响应
                if response:
                    await self.send_message(response['to_id'], response)
                
        except Exception as e:
            logger.error(f"Error processing message from client {client_id}: {str(e)}")
            await self.disconnect(client_id)

    async def send_message(self, client_id: str, message: Dict[str, Any]):
        """
        发送消息到指定客户端
        """
        if client_id in self.active_connections:
            try:
                websocket = self.active_connections[client_id]
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message to client {client_id}: {str(e)}")
                await self.disconnect(client_id)

    async def _handle_processed_message(self, message: Dict[str, Any]):
        """
        处理已处理的消息
        """
        try:
            await self.send_message(message['to_id'], message)
        except Exception as e:
            logger.error(f"Error handling processed message: {str(e)}")

    async def broadcast(self, message: Dict[str, Any]):
        """
        广播消息给所有连接的客户端
        """
        for client_id in list(self.active_connections.keys()):
            await self.send_message(client_id, message)

# 创建全局 WebSocket 管理器实例
websocket_manager = WebSocketManager()