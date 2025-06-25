import json
from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import WebSocket
from ..event_bus import event_bus, EventTypes
from ..utils.logging import get_logger

logger = get_logger("says.services.websocket")


class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        # 直接订阅 SEND_MESSAGE 事件
        event_bus.subscribe(EventTypes.SEND_MESSAGE, self.handle_send_message)
        logger.info("websocket_manager_initialized", event_subscription=True)

    async def connect(self, websocket: WebSocket, client_id: str):
        """
        处理新的 WebSocket 连接
        """
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info("client_connected", client_id=client_id)

    async def disconnect(self, client_id: str):
        """
        处理 WebSocket 断开连接
        """
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        logger.info("client_disconnected", client_id=client_id)

    async def receive_message(self, websocket: WebSocket, client_id: str):
        """
        处理接收到的消息
        """
        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)

                # 验证必要的消息字段
                required_fields = ["from_entity", "to_entity", "message_type"]
                if not all(field in message for field in required_fields):
                    logger.warning("message_missing_fields", client_id=client_id, message=message)
                    continue

                # 添加消息服务信息
                message["message_service"] = "websocket"

                # 确保消息包含时间戳
                if "message_time" not in message:
                    message["message_time"] = datetime.now(timezone.utc).isoformat()

                # 发布消息到事件总线
                logger.info(
                    "publishing_message",
                    client_id=client_id,
                    from_entity=message.get("from_entity"),
                    to_entity=message.get("to_entity"),
                    message_type=message.get("message_type"),
                )
                await event_bus.publish(EventTypes.RECEIVED_MESSAGE, message)

        except Exception as e:
            logger.error("message_processing_error", client_id=client_id, error=str(e), exc_info=True)
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
                logger.error("message_sending_error", client_id=client_id, error=str(e), exc_info=True)
                await self.disconnect(client_id)

    async def handle_send_message(self, message: Dict[str, Any]):
        """
        处理已处理的消息
        """
        try:
            # 检查消息是否来自 websocket 服务
            if message.get("message_service") != "websocket":
                logger.info(
                    "ignoring_non_websocket_message", message_service=message.get("message_service")
                )
                return

            to_entity = message.get("to_entity")
            if not to_entity:
                logger.warning("message_missing_to_entity")
                return

            logger.info(
                "handling_processed_message", to_entity=to_entity, message_type=message.get("message_type")
            )

            if to_entity in self.active_connections:
                await self.send_message(to_entity, message)
                logger.info("message_sent_successfully", client_id=to_entity)
            else:
                logger.warning("no_active_connection", client_id=to_entity)

        except Exception as e:
            logger.error("processed_message_error", error=str(e), exc_info=True)

    async def broadcast(self, message: Dict[str, Any]):
        """
        广播消息给所有连接的客户端
        """
        for client_id in list(self.active_connections.keys()):
            await self.send_message(client_id, message)


# 创建全局 WebSocket 管理器实例
websocket = WebSocketManager()
