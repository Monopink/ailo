import logging
from db_managers import db_manager

logger = logging.getLogger(__name__)


async def load_full_data(self) -> None:
    """从数据库加载 bot 所有数据"""
    pass


async def update_context(self) -> None:
    """保存上下文到数据库"""
    try:
        # 更新上下文
        await db_manager.update_bot_context(self.bot.id, self.context)

    except Exception as e:
        logger.error(f"Error saving context: {str(e)}")


async def update_memory(self) -> None:
    """保存记忆到数据库"""
    try:
        await db_manager.update_bot_memory(self.bot.id, self.memory)
    except Exception as e:
        logger.error(f"Error saving memory: {str(e)}")
