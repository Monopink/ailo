"""In-memory WebSocket connection manager.

This module intentionally keeps only process-local state for active WebSocket connections.
If you deploy multiple workers/instances, WebSocket fan-out needs a shared pubsub hub.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final

from fastapi import WebSocket

from app.utils.logging import get_logger

logger = get_logger(__name__)


_SEND_TIMEOUT_SECONDS = 5.0
_QUEUE_MAXSIZE = 200


@dataclass(slots=True)
class _SendItem:
    frame: Mapping[str, object]
    result: asyncio.Future[bool]


class _WebSocketConnection:
    """A single WebSocket connection with serialized sending."""

    def __init__(
        self,
        *,
        endpoint_id: int,
        ws: WebSocket,
        on_send_queue_full: Callable[[int], None] | None = None,
    ) -> None:
        self.endpoint_id = endpoint_id
        self.ws = ws
        self._queue: asyncio.Queue[_SendItem] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._sender_task: asyncio.Task[None] | None = None
        self._closed = asyncio.Event()
        self._on_send_queue_full = on_send_queue_full

    def start(self) -> None:
        if self._sender_task is not None:
            return
        self._sender_task = asyncio.create_task(self._sender_loop())

    async def close(self) -> None:
        if self._closed.is_set():
            return
        self._closed.set()

        if self._sender_task is not None:
            self._sender_task.cancel()

        # Fail pending senders quickly.
        try:
            while True:
                item = self._queue.get_nowait()
                if not item.result.done():
                    item.result.set_result(False)
        except asyncio.QueueEmpty:
            pass

        try:
            await self.ws.close()
        except Exception:  # pragma: no cover - best effort close
            logger.debug("ws_close_failed", endpoint_id=self.endpoint_id, exc_info=True)

    def is_closed(self) -> bool:
        return self._closed.is_set()

    async def send_json(self, frame: Mapping[str, object], *, timeout_seconds: float) -> bool:
        """Send a JSON frame, waiting for the actual socket write."""
        if self.is_closed():
            return False

        loop = asyncio.get_running_loop()
        fut: asyncio.Future[bool] = loop.create_future()

        try:
            self._queue.put_nowait(_SendItem(frame=frame, result=fut))
        except asyncio.QueueFull:
            if self._on_send_queue_full is not None:
                self._on_send_queue_full(self.endpoint_id)
            else:
                logger.warning("ws_send_queue_full", endpoint_id=self.endpoint_id)
            return False

        try:
            return await asyncio.wait_for(fut, timeout=timeout_seconds)
        except TimeoutError:
            logger.warning("ws_send_timeout", endpoint_id=self.endpoint_id)
            # Force close to avoid leaking a stuck connection.
            await self.close()
            return False

    async def _sender_loop(self) -> None:
        try:
            while not self.is_closed():
                item = await self._queue.get()
                if item.result.done():
                    continue

                try:
                    await asyncio.wait_for(
                        self.ws.send_json(item.frame),
                        timeout=_SEND_TIMEOUT_SECONDS,
                    )
                    item.result.set_result(True)
                except Exception:
                    item.result.set_result(False)
                    logger.warning(
                        "ws_send_failed",
                        endpoint_id=self.endpoint_id,
                        exc_info=True,
                    )
                    await self.close()
                    return
        except asyncio.CancelledError:
            return


class WebSocketConnectionManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._connections: dict[int, _WebSocketConnection] = {}
        self._send_queue_full_count = 0

    def has(self, endpoint_id: int) -> bool:
        conn = self._connections.get(endpoint_id)
        return conn is not None and not conn.is_closed()

    def connection_count(self) -> int:
        return sum(1 for conn in self._connections.values() if not conn.is_closed())

    def drain_send_queue_full_count(self) -> int:
        count = self._send_queue_full_count
        self._send_queue_full_count = 0
        return count

    def _record_send_queue_full(self, endpoint_id: int) -> None:
        self._send_queue_full_count += 1
        logger.warning("ws_send_queue_full", endpoint_id=endpoint_id)

    async def register(self, endpoint_id: int, ws: WebSocket) -> None:
        """Register (or replace) an active websocket for the endpoint."""
        async with self._lock:
            old = self._connections.get(endpoint_id)
            if old is not None:
                await old.close()

            conn = _WebSocketConnection(
                endpoint_id=endpoint_id,
                ws=ws,
                on_send_queue_full=self._record_send_queue_full,
            )
            conn.start()
            self._connections[endpoint_id] = conn

    async def unregister(self, endpoint_id: int) -> None:
        async with self._lock:
            conn = self._connections.pop(endpoint_id, None)
        if conn is not None:
            await conn.close()

    async def send_json(self, endpoint_id: int, frame: Mapping[str, object]) -> bool:
        conn = self._connections.get(endpoint_id)
        if conn is None or conn.is_closed():
            return False
        return await conn.send_json(frame, timeout_seconds=_SEND_TIMEOUT_SECONDS)


ws_manager: Final[WebSocketConnectionManager] = WebSocketConnectionManager()
