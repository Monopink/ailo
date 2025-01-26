import json
import logging
from typing import Dict, Any
from fastapi import WebSocket
from event_bus import event_bus, EventTypes

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        # 直接订阅 SEND_MESSAGE 事件
        event_bus.subscribe(EventTypes.SEND_MESSAGE, self._handle_processed_message)
        logger.info("WebSocketManager initialized and subscribed to events")

    async def connect(self, websocket: WebSocket, client_id: str):
        """
        处理新的 WebSocket 连接
        """
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"Client connected: {client_id}")

    async def disconnect(self, client_id: str):
        """
        处理 WebSocket 断开连接
        """
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        logger.info(f"Client disconnected: {client_id}")

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
                message['message_service'] = 'websocket'
                
                # 发布消息到事件总线
                logger.debug(f"Publishing message from client {client_id} to event bus")
                await event_bus.publish(EventTypes.MESSAGE_RECEIVED, message)
                logger.debug(f"Message published successfully for client {client_id}")
                
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
            # 检查消息是否来自 websocket 服务
            if message.get('message_service') != 'websocket':
                logger.debug(f"Ignoring non-websocket message: {message}")
                return
                
            to_id = message.get('to_id')
            if not to_id:
                logger.warning("Message missing to_id")
                return

            logger.debug(f"Handling processed websocket message to {to_id}: {message}")
            if to_id in self.active_connections:
                await self.send_message(to_id, message)
                logger.debug(f"Processed message sent successfully to client {to_id}")
            else:
                logger.warning(f"No active connection found for client {to_id}")
                
        except Exception as e:
            logger.error(f"Error handling processed message: {str(e)}", exc_info=True)

    async def broadcast(self, message: Dict[str, Any]):
        """
        广播消息给所有连接的客户端
        """
        for client_id in list(self.active_connections.keys()):
            await self.send_message(client_id, message)

# 创建全局 WebSocket 管理器实例
websocket = WebSocketManager()