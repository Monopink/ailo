from typing import Dict, List, Callable, Any
import asyncio
from .utils.logging import get_logger

logger = get_logger(__name__)


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

        logger.info("event_bus_starting")
        self._running = True
        # 创建新的处理任务
        self._process_task = asyncio.create_task(self._process_queue())
        logger.info("event_bus_started")

    async def stop(self):
        """停止事件总线"""
        if not self._running:
            return

        logger.info("event_bus_stopping")
        self._running = False
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        logger.info("event_bus_stopped")

    def subscribe(self, event_type: str, callback: Callable):
        """订阅特定类型的事件"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)
            logger.info("event_subscribed", event_type=event_type)

    def unsubscribe(self, event_type: str, callback: Callable):
        """取消订阅特定类型的事件"""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
                logger.info("event_unsubscribed", event_type=event_type)
            except ValueError:
                pass

    async def publish(self, event_type: str, data: Any):
        """发布事件到队列"""
        if not self._running:
            logger.warning("event_bus_not_running", event_type=event_type)
            return
        await self._message_queue.put((event_type, data))
        logger.info(
            "event_published",
            event_type=event_type,
            subscribers_count=len(self._subscribers.get(event_type, [])),
        )

    async def _process_queue(self):
        """处理消息队列"""
        logger.info("message_queue_processor_started")
        while self._running:
            try:
                # 使用 wait_for 添加超时机制
                event_type, data = await asyncio.wait_for(self._message_queue.get(), timeout=1.0)  # 1秒超时

                logger.info("processing_event", event_type=event_type)
                if event_type in self._subscribers:
                    subscribers = self._subscribers[event_type].copy()
                    logger.info("subscribers_found", event_type=event_type, count=len(subscribers))
                    for callback in subscribers:
                        try:
                            await callback(data)
                        except Exception as e:
                            logger.error(
                                "subscriber_callback_error",
                                event_type=event_type,
                                error=str(e),
                                exc_info=True,
                            )
                else:
                    logger.warning("no_subscribers", event_type=event_type)

                self._message_queue.task_done()

            except asyncio.TimeoutError:
                # 超时继续循环
                continue
            except asyncio.CancelledError:
                logger.info("message_queue_processor_cancelled")
                break
            except Exception as e:
                logger.error("event_bus_processing_error", error=str(e), exc_info=True)
                # 出错后短暂等待后继续
                await asyncio.sleep(0.1)

        logger.info("message_queue_processor_stopped")


# 创建全局事件总线实例
event_bus = EventBus()


# 预定义的事件类型
class EventTypes:
    RECEIVED_MESSAGE = "received_message"
    SEND_MESSAGE = "send_message"
