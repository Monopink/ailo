import json
from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import WebSocket
from core.events import event_bus, EventTypes
from enums import IMServiceType
from utils.logging import get_logger

logger = get_logger(__name__)


class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        # Subscribe to SEND_MESSAGE event directly
        event_bus.subscribe(EventTypes.SEND_MESSAGE, self.handle_send_message)
        logger.info("websocket_manager_initialized", event_subscription=True)

    async def connect(self, websocket: WebSocket, client_id: str):
        """
        Handle a new WebSocket connection.
        """
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info("client_connected", client_id=client_id)

    async def disconnect(self, client_id: str):
        """
        Handle a WebSocket disconnection.
        """
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        logger.info("client_disconnected", client_id=client_id)

    async def receive_message(self, websocket: WebSocket, client_id: str):
        """
        Handle received messages.
        """
        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)

                # Validate required message fields
                required_fields = ["from_entity", "to_entity", "message_type"]
                if not all(field in message for field in required_fields):
                    logger.warning("message_missing_fields", client_id=client_id, message=message)
                    continue

                # Add message service information
                message["message_service"] = IMServiceType.WEBSOCKET.value

                # Ensure the message contains a timestamp
                if "message_time" not in message:
                    message["message_time"] = datetime.now(timezone.utc).isoformat()

                # Publish the message to the event bus
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
        Send a message to a specific client.
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
        Handle a processed message.
        """
        try:
            # Check if the message is from the websocket service
            if message.get("message_service") != IMServiceType.WEBSOCKET.value:
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
        Broadcast a message to all connected clients.
        """
        for client_id in list(self.active_connections.keys()):
            await self.send_message(client_id, message)


# Create a global WebSocket manager instance
websocket = WebSocketManager()
