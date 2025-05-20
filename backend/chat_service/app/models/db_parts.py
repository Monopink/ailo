import logging
from db_managers import db_manager
from typing import Optional

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


async def update_relationship(
    self,
    new_type: Optional[str] = None,
    new_level: Optional[str] = None,
    new_style: Optional[str] = None,
) -> None:
    """更新关系信息

    Args:
        new_type: 新的关系类型
        new_level: 新的关系等级
        new_style: 新的关系风格
    """
    try:
        # 更新内存中的关系字段
        if new_type:
            self.relationship_type = new_type
        if new_level:
            self.relationship_level = new_level
        if new_style:
            self.relationship_style = new_style

        # 直接更新数据库，不构建字典
        await db_manager.update_bot_relationship(
            self.bot.id,
            relationship_type=self.relationship_type,
            relationship_level=self.relationship_level,
            relationship_style=self.relationship_style,
        )

        # 刷新系统上下文
        self._refresh_system_context()

        logger.debug(
            f"Updated relationship for bot {self.bot.id}: type={self.relationship_type}, level={self.relationship_level}"
        )
    except Exception as e:
        logger.error(f"Error updating relationship: {str(e)}", exc_info=True)
        raise
