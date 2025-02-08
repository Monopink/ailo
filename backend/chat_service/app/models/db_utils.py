import logging
from db_managers import db_manager

logger = logging.getLogger(__name__)


async def load_full_data(self) -> None:
    """从数据库加载 bot 所有数据"""
    pass


"""
    try:
        bot_data = await db_manager.get_bot_data(self.bot.id, self.bot.user_id)
        if bot_data:
            self.context = bot_data.get('context', {})
            self.relationship_type = bot_data.get('relationship_type')
            self.relationship_score = bot_data.get('relationship_score', 0)
            self.memory = bot_data.get('memory', '')
            self.style = bot_data.get(f"{self.relationship_type}_style", '') if bot_data and self.relationship_type else ''
            logger.info(f"Loaded full data for bot {self.bot.id}")
    except Exception as e:
        logger.error(f"Error loading bot full data: {str(e)}")
"""


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
