from typing import Dict, List, Callable, Any
import asyncio
import logging

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._process_task = None

    async def start(self):
        """启动事件总线"""
        if self._running:
            return

        logger.info("Starting event bus...")
        self._running = True
        # 创建新的处理任务
        self._process_task = asyncio.create_task(self._process_queue())
        logger.info("Event bus started successfully")

    async def stop(self):
        """停止事件总线"""
        if not self._running:
            return

        logger.info("Stopping event bus...")
        self._running = False
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        logger.info("Event bus stopped successfully")

    def subscribe(self, event_type: str, callback: Callable):
        """订阅特定类型的事件"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)
            logger.debug(f"Subscribed to event: {event_type}")

    def unsubscribe(self, event_type: str, callback: Callable):
        """取消订阅特定类型的事件"""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
                logger.debug(f"Unsubscribed from event: {event_type}")
            except ValueError:
                pass

    async def publish(self, event_type: str, data: Any):
        """发布事件到队列"""
        if not self._running:
            logger.warning("Event bus is not running, message ignored")
            return
        await self._message_queue.put((event_type, data))
        logger.debug(
            f"Published event: {event_type}, subscribers count: {len(self._subscribers.get(event_type, []))}"
        )

    async def _process_queue(self):
        """处理消息队列"""
        logger.info("Message queue processor started")
        while self._running:
            try:
                # 使用 wait_for 添加超时机制
                event_type, data = await asyncio.wait_for(
                    self._message_queue.get(), timeout=1.0  # 1秒超时
                )

                logger.debug(f"Processing event: {event_type}")
                if event_type in self._subscribers:
                    subscribers = self._subscribers[event_type].copy()
                    logger.debug(
                        f"Found {len(subscribers)} subscribers for event: {event_type}"
                    )
                    for callback in subscribers:
                        try:
                            await callback(data)
                        except Exception as e:
                            logger.error(
                                f"Error in subscriber callback for event {event_type}: {str(e)}"
                            )
                else:
                    logger.warning(f"No subscribers found for event: {event_type}")

                self._message_queue.task_done()

            except asyncio.TimeoutError:
                # 超时继续循环
                continue
            except asyncio.CancelledError:
                logger.info("Message queue processor cancelled")
                break
            except Exception as e:
                logger.error(f"Error in event bus processing: {str(e)}")
                # 出错后短暂等待后继续
                await asyncio.sleep(0.1)

        logger.info("Message queue processor stopped")


# 创建全局事件总线实例
event_bus = EventBus()


# 预定义的事件类型
class EventTypes:
    RECEIVED_MESSAGE = "received_message"
    SEND_MESSAGE = "send_message"
