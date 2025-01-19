from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class BaseService(ABC):
    """
    所有服务类的基类，定义了服务的基本接口和共同功能
    """
    def __init__(self):
        self.started: bool = False
        self.start_time: Optional[datetime] = None
        self.service_name: str = self.__class__.__name__
        self._config: Dict[str, Any] = {}

    @abstractmethod
    async def start(self) -> bool:
        """
        启动服务
        返回: 启动是否成功
        """
        if self.started:
            logger.warning(f"{self.service_name} already started")
            return False
        
        self.started = True
        self.start_time = datetime.now()
        logger.info(f"{self.service_name} started at {self.start_time}")
        return True

    @abstractmethod
    async def stop(self) -> bool:
        """
        停止服务
        返回: 停止是否成功
        """
        if not self.started:
            logger.warning(f"{self.service_name} not running")
            return False
        
        self.started = False
        logger.info(f"{self.service_name} stopped")
        return True

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        服务健康检查
        返回: 健康状态信息
        """
        return {
            'service': self.service_name,
            'status': 'running' if self.started else 'stopped',
            'uptime': (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        }

    def configure(self, config: Dict[str, Any]) -> None:
        """
        配置服务
        参数:
            config: 配置字典
        """
        self._config.update(config)
        logger.info(f"{self.service_name} configured with {config}")

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        参数:
            key: 配置键
            default: 默认值
        返回: 配置值
        """
        return self._config.get(key, default)

    @property
    def is_running(self) -> bool:
        """
        服务是否正在运行
        """
        return self.started

    async def handle_error(self, error: Exception) -> None:
        """
        处理服务错误
        参数:
            error: 异常对象
        """
        logger.error(f"{self.service_name} encountered error: {str(error)}")

    async def process_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理消息的基本方法
        参数:
            message: 输入消息
        返回: 处理结果
        """
        try:
            if not self.is_running:
                raise RuntimeError(f"{self.service_name} is not running")
            
            # 子类应该重写这个方法来实现具体的消息处理逻辑
            return None
            
        except Exception as e:
            await self.handle_error(e)
            return None